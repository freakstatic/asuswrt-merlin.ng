#!/usr/bin/env python3
"""Portable packaging regressions. Vendor calls use a fake host tag writer."""
import importlib.util
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
HOSTTOOLS = ROOT / "release/src-rt-5.02axhnd.675x/hostTools"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


writer = load("ax56u_addvtoken", HOSTTOOLS / "ax56u_addvtoken.py")
audit = load("ax56u_audit", ROOT / "tests/ax56u/audit_firmware.py")


def raw_ubi(boot_prefix=False):
    block = bytearray(b"\xff" * 131072)
    block[:4] = b"UBI#"
    struct.pack_into(">II", block, 16, 2048, 4096)
    block[2048:2052] = b"UBI!"
    struct.pack_into(">I", block, 2056, 0)
    return (b"B" * (1024 * 1024) if boot_prefix else b"") + block


def old_tag():
    tag = bytearray(64)
    tag[:4] = bytes([3, 0, 0, 4])
    struct.pack_into("<HH", tag, 4, 388, 24353)
    tag[8:20] = b"RT-AX56U".ljust(12, b"\0")
    struct.pack_into("<I", tag, 28, 24353)
    tag[63] = 1
    return tag


def vendor_image(raw, tag=None, chip=0x47622, flash=3, flags=2):
    body = raw[:-64] + (tag if tag is not None else old_tag())
    return body + struct.pack("<5I", writer.crc32(body), 0x5732, chip, flash, flags)


class ImageTagTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ax56u-tag-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.hosttools = self.root / "hostTools"
        self.header = self.root / "router/shared/version.h"
        self.header.parent.mkdir(parents=True)
        self.hosttools.mkdir()
        self.write_header()
        self.runtime = {"rt_version": "3.0.0.6", "rt_serialno": "102.10",
                        "rt_extendno": "alpha2", "rt_buildname": "RT-AX56U"}

    def write_header(self, serial="102.10", extension="alpha2", model="RT-AX56U", version="3.0.0.6"):
        self.header.write_text('\n'.join('#define %s "%s"' % (name, value) for name, value in (
            ("RT_VERSION", version), ("RT_SERIALNO", serial),
            ("RT_EXTENDNO", extension), ("RT_BUILD_NAME", model))) + '\n')

    def test_current_version_and_crc(self):
        for prefix in (False, True):
            with self.subTest(boot_prefix=prefix):
                raw = raw_ubi(prefix)
                old = vendor_image(raw)
                new = writer.retag(raw, old, writer.read_version(self.header))
                self.assertEqual(len(new), len(old))
                self.assertEqual(new[:-84], old[:-84])
                self.assertEqual(new[-16:], old[-16:])
                self.assertEqual(new[-84:-80], bytes([3, 0, 0, 6]))
                self.assertEqual(struct.unpack_from("<HH", new, len(new) - 80), (102, 0))
                self.assertEqual(struct.unpack_from("<I", new, len(new) - 56)[0], 0)
                self.assertEqual(struct.unpack_from("<I", new, len(new) - 20)[0], writer.crc32(new[:-20]))
                self.assertNotEqual(old[-20:-16], new[-20:-16])
                result = audit.asus_tag_audit(new[-84:-20], self.runtime)
                self.assertEqual(result["buildno"], 102)
                self.assertEqual(result["extendno32"], 0)

    def test_numeric_extension_and_unrelated_tag_fields(self):
        self.write_header(extension="70000-ax56u1")
        raw = raw_ubi()
        tag = old_tag()
        tag[20:28] = b"hardware"
        tag[32:63] = bytes(range(31))
        new = writer.retag(raw, vendor_image(raw, tag), writer.read_version(self.header))
        self.assertEqual(new[-64:-56], b"hardware")
        self.assertEqual(new[-52:-21], bytes(range(31)))
        self.runtime["rt_extendno"] = "70000-ax56u1"
        fields = audit.asus_tag_audit(new[-84:-20], self.runtime)
        self.assertEqual(fields["extendno16"], 70000 & 0xFFFF)
        self.assertEqual(fields["extendno32"], 70000)

    def test_old_tag_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "does not match"):
            audit.asus_tag_audit(old_tag(), self.runtime)

    def test_3004_version_and_boot_prefix(self):
        self.write_header(version="3.0.0.4", serial="388.12", extension="2-ax56u1")
        runtime = {"rt_version": "3.0.0.4", "rt_serialno": "388.12",
                   "rt_extendno": "2-ax56u1", "rt_buildname": "RT-AX56U"}
        with self.assertRaisesRegex(ValueError, "does not match"):
            audit.asus_tag_audit(old_tag(), runtime)
        for boot_prefix, flags in ((False, 2), (True, 6)):
            with self.subTest(boot_prefix=boot_prefix):
                raw = raw_ubi(boot_prefix)
                old = vendor_image(raw, flags=flags)
                new = writer.retag(raw, old, writer.read_version(self.header))
                self.assertEqual(len(new), len(old))
                self.assertEqual(new[:-84], old[:-84])
                self.assertEqual(new[-16:], old[-16:])
                fields = audit.asus_tag_audit(new[-84:-20], runtime)
                self.assertEqual(fields["version"], "3.0.0.4")
                self.assertEqual(fields["buildno"], 388)
                self.assertEqual(fields["extendno16"], 2)
                self.assertEqual(fields["extendno32"], 2)
                self.assertEqual(struct.unpack_from("<I", new, len(new) - 20)[0],
                                 writer.crc32(new[:-20]))
                self.assertEqual(struct.unpack_from("<I", new, len(new) - 4)[0], flags)
                if boot_prefix:
                    self.assertEqual(new[:1024 * 1024], old[:1024 * 1024])

    def test_make_rule_keeps_other_model_writer(self):
        for model in ("RT-AX56U", "RT-AX58U"):
            result = subprocess.run(
                ["make", "--no-print-directory", "--dry-run", "--always-make", "addvtoken", "BUILD_NAME=" + model],
                cwd=HOSTTOOLS, check=True, capture_output=True, text=True,
            ).stdout
            if model == "RT-AX56U":
                self.assertIn("cp -f ax56u_addvtoken.py addvtoken", result)
                self.assertIn("cp -f ../router/shared/version.h .", result)
            else:
                self.assertIn("cp -f ./prebuilt/RT-AX58U/addvtoken .", result)
                self.assertNotIn("ax56u_addvtoken.py", result)

    def test_corrupt_or_wrong_target_outputs_are_rejected(self):
        raw = raw_ubi()
        corrupt = bytearray(vendor_image(raw))
        corrupt[5000] ^= 1
        altered = bytearray(raw)
        altered[5000] ^= 1
        for image in (bytes(corrupt), vendor_image(raw, chip=0x4908),
                      vendor_image(raw, flash=1), vendor_image(altered), b"short"):
            with self.subTest(length=len(image)):
                with self.assertRaises(ValueError):
                    writer.retag(raw, image, writer.read_version(self.header))

    def test_non_erased_or_wrong_volume_padding_is_rejected(self):
        wrong_volume = bytearray(raw_ubi())
        struct.pack_into(">I", wrong_volume, 2056, 10)
        occupied = bytearray(raw_ubi())
        occupied[-1] = 0
        for raw in (wrong_volume, occupied, b"short", b"\0" * 131072):
            with self.assertRaises(ValueError):
                writer.validate_input(raw)

    def test_invalid_version_fields_are_rejected(self):
        cases = ({"serial": "65536"}, {"serial": "102x"},
                 {"extension": "4294967296"}, {"extension": ""},
                 {"version": "3.0.0.256"}, {"version": "3.0.6"}, {"model": "RT-AX58U"})
        for case in cases:
            with self.subTest(case=case):
                self.write_header(**case)
                with self.assertRaises(ValueError):
                    writer.read_version(self.header)

    def install_fake_vendor(self, corrupt=False):
        path = self.hosttools / "prebuilt/RT-AX56U/addvtoken"
        path.parent.mkdir(parents=True)
        path.write_text('''#!/usr/bin/env python3
from pathlib import Path
import struct, sys, zlib
raw = Path(sys.argv[-2]).read_bytes()
tag = bytearray(64)
tag[:4] = bytes([3, 0, 0, 4])
struct.pack_into("<HH", tag, 4, 388, 24353)
tag[8:20] = b"RT-AX56U".ljust(12, b"\\0")
struct.pack_into("<I", tag, 28, 24353)
tag[63] = 1
body = raw[:-64] + tag
out = body + struct.pack("<5I", zlib.crc32(body) ^ 0xffffffff, 0x5732, 0x47622, 3, 2)
Path(sys.argv[-1]).write_bytes(''' + ('b"corrupt"' if corrupt else 'out') + ')\n')
        path.chmod(0o755)

    def package_args(self):
        return ["--endian", "little", "--chip", "47622", "--flashtype", "NAND128",
                "--btrm", "1", str(self.root / "raw.img"), str(self.root / "output.w")]

    def test_package_reads_current_header_and_preserves_input(self):
        self.install_fake_vendor()
        raw = raw_ubi()
        (self.root / "raw.img").write_bytes(raw)
        writer.package(self.package_args(), self.hosttools)
        self.assertEqual((self.root / "raw.img").read_bytes(), raw)
        first = (self.root / "output.w").read_bytes()
        audit.asus_tag_audit(first[-84:-20], self.runtime)
        self.write_header(extension="2-ax56u1")
        writer.package(self.package_args(), self.hosttools)
        self.runtime["rt_extendno"] = "2-ax56u1"
        audit.asus_tag_audit((self.root / "output.w").read_bytes()[-84:-20], self.runtime)
        self.assertEqual(list(self.root.glob(".ax56u-wfi-*")), [])

    def test_failed_package_keeps_existing_output(self):
        self.install_fake_vendor(corrupt=True)
        (self.root / "raw.img").write_bytes(raw_ubi())
        (self.root / "output.w").write_bytes(b"previous image")
        with self.assertRaises(ValueError):
            writer.package(self.package_args(), self.hosttools)
        self.assertEqual((self.root / "output.w").read_bytes(), b"previous image")
        self.assertEqual(list(self.root.glob(".ax56u-wfi-*")), [])

    def test_input_output_alias_is_rejected(self):
        raw = raw_ubi()
        (self.root / "raw.img").write_bytes(raw)
        args = self.package_args()
        args[-1] = args[-2]
        with self.assertRaises(ValueError):
            writer.package(args, self.hosttools)
        self.assertEqual((self.root / "raw.img").read_bytes(), raw)


if __name__ == "__main__":
    unittest.main()
