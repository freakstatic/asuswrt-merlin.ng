#!/usr/bin/env python3
"""AX56U NAND128 tag adapter. Never mount, execute, or flash firmware bytes.

Keep the shipped model-specific writer's WFI flags and boot-image handling,
but replace its compiled-in ASUS version fields before recomputing the CRC.
The legacy numeric fields use decimal prefixes: 102.10 -> 102, alpha2 -> 0.
Full version strings remain in the packaged libshared, not invented tag fields.
"""
import argparse
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import zlib


def require(condition, message):
    if not condition:
        raise ValueError(message)


def crc32(data):
    return zlib.crc32(data) ^ 0xFFFFFFFF


def numeric_prefix(value, maximum):
    match = re.match(r"[0-9]+", value)
    number = int(match[0]) if match else 0
    require(number <= maximum, "Version number exceeds legacy tag field")
    return number


def read_version(path):
    text = path.read_text()
    values = {}
    for name in ("RT_VERSION", "RT_SERIALNO", "RT_EXTENDNO", "RT_BUILD_NAME"):
        matches = re.findall(r'^#define\s+' + name + r'\s+"([^"\\]*)"\s*$', text, re.M)
        require(len(matches) == 1, "Missing or ambiguous version macro: " + name)
        values[name] = matches[0]
    require(values["RT_BUILD_NAME"] == "RT-AX56U", "This tag adapter is AX56U-only")
    require(re.fullmatch(r"[0-9]+(?:\.[0-9]+){3}", values["RT_VERSION"]), "Invalid firmware version")
    version = [int(part) for part in values["RT_VERSION"].split(".")]
    require(all(part <= 255 for part in version), "Firmware version byte overflow")
    require(re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", values["RT_SERIALNO"]), "Invalid build number")
    require(values["RT_EXTENDNO"] and re.fullmatch(r"[A-Za-z0-9_.+-]+", values["RT_EXTENDNO"]), "Invalid extension")
    values["version_bytes"] = bytes(version)
    values["build_number"] = numeric_prefix(values["RT_SERIALNO"], 0xFFFF)
    values["extension_number"] = numeric_prefix(values["RT_EXTENDNO"], 0xFFFFFFFF)
    return values


def validate_input(raw):
    require(len(raw) >= 131072 and len(raw) % 131072 == 0, "NAND128 image alignment")
    require(raw[:4] == b"UBI#" or raw[1024 * 1024:1024 * 1024 + 4] == b"UBI#", "Expected pure-UBI image")
    require(raw[-131072:-131068] == b"UBI#", "Missing final UBI eraseblock")
    vid_offset, data_offset = struct.unpack_from(">II", raw, len(raw) - 131072 + 16)
    require((vid_offset, data_offset) == (2048, 4096), "Wrong NAND geometry")
    vid = len(raw) - 131072 + vid_offset
    require(raw[vid:vid + 4] == b"UBI!" and struct.unpack_from(">I", raw, vid + 8)[0] == 0,
            "ASUS tail must occupy rootfs-volume padding")
    require(raw[-64:] == b"\xff" * 64, "Refusing to replace non-erased firmware data")


def retag(raw, image, version):
    validate_input(raw)
    require(len(image) == len(raw) + 20, "Unexpected vendor writer output length")
    checksum, revision, chip, flash, _ = struct.unpack("<5I", image[-20:])
    require((revision, chip, flash) == (0x5732, 0x47622, 3), "Wrong WFI format/target")
    require(checksum == crc32(image[:-20]), "Vendor output CRC mismatch")
    require(image[:-84] == raw[:-64], "Vendor writer changed bytes outside the ASUS tail")
    tag = bytearray(image[-84:-20])
    require(tag[8:20].split(b"\0", 1)[0] == b"RT-AX56U" and tag[63] == 1, "Unexpected ASUS tail layout")
    tag[:4] = version["version_bytes"]
    struct.pack_into("<HH", tag, 4, version["build_number"], version["extension_number"] & 0xFFFF)
    struct.pack_into("<I", tag, 28, version["extension_number"])
    result = bytearray(image)
    result[-84:-20] = tag
    struct.pack_into("<I", result, len(result) - 20, crc32(memoryview(result)[:-20]))
    return result


def package(arguments, hosttools):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endian", choices=["little"], required=True)
    parser.add_argument("--chip", choices=["47622"], required=True)
    parser.add_argument("--flashtype", choices=["NAND128"], required=True)
    parser.add_argument("--pmc", choices=["0", "1"])
    parser.add_argument("--btrm", choices=["0", "1"])
    parser.add_argument("--ddrtype", choices=["DDR3", "DDR4"])
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(arguments)
    require(not args.output.is_symlink(), "Output must not be a symlink")
    require(not args.output.exists() or not args.input.samefile(args.output), "Input and output must differ")
    version = read_version(hosttools.parent / "router/shared/version.h")
    vendor = hosttools / "prebuilt/RT-AX56U/addvtoken"
    raw = args.input.read_bytes()
    validate_input(raw)
    options = ["--endian", args.endian, "--chip", args.chip, "--flashtype", args.flashtype]
    for name in ("pmc", "btrm", "ddrtype"):
        if getattr(args, name) is not None:
            options += ["--" + name, getattr(args, name)]
    fd, name = tempfile.mkstemp(prefix=".ax56u-wfi-", dir=args.output.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        subprocess.run([str(vendor), *options, str(args.input), str(temporary)], check=True)
        result = retag(raw, temporary.read_bytes(), version)
        with temporary.open("wb") as handle:
            handle.write(result)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o644)
        os.replace(temporary, args.output)
    finally:
        temporary.unlink(missing_ok=True)
    print("AX56U final tag: {RT_VERSION}, numeric build {build_number}, extension {extension_number}; "
          "full runtime {RT_SERIALNO}_{RT_EXTENDNO}".format(**version))
    print("AX56U final WFI CRC: 0x%08x" % struct.unpack_from("<I", result, len(result) - 20)[0])


if __name__ == "__main__":
    try:
        package(sys.argv[1:], Path(__file__).resolve().parent)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        sys.exit("AX56U image packaging failed: " + str(error))
