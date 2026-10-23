#!/usr/bin/env python3
"""Read-only AX56U image/ELF checks. Never mount or execute firmware code."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import subprocess
import zlib


def require(condition, message):
    if not condition:
        raise ValueError(message)


def crc32(data):
    return zlib.crc32(data) ^ 0xFFFFFFFF


def readelf(path, *options):
    return subprocess.run(
        ["readelf", *options, str(path)], check=True, capture_output=True,
        text=True, errors="replace",
    ).stdout


def image_audit(path, staging):
    raw = path.read_bytes()
    expected, version, chip, flash, flags = struct.unpack("<5I", raw[-20:])
    require(expected == crc32(raw[:-20]), "Whole-image CRC mismatch")
    require((version, chip, flash) == (0x5732, 0x47622, 3), "Wrong WFI target")
    start = 0 if raw[:4] == b"UBI#" else 1024 * 1024
    payload = raw[start:-20]
    require(len(payload) % 131072 == 0, "UBI eraseblock alignment")
    volumes = defaultdict(dict)
    volume_names = {}
    for offset in range(0, len(payload), 131072):
        block = payload[offset:offset + 131072]
        require(block[:4] == b"UBI#", f"EC magic at {offset}")
        require(struct.unpack_from(">I", block, 60)[0] == crc32(block[:60]), "EC CRC")
        vid_offset, data_offset = struct.unpack_from(">II", block, 16)
        require((vid_offset, data_offset) == (2048, 4096), "Wrong NAND geometry")
        vid = block[vid_offset:vid_offset + 64]
        require(vid[:4] == b"UBI!", "VID magic")
        require(struct.unpack_from(">I", vid, 60)[0] == crc32(vid[:60]), "VID CRC")
        volume, logical = struct.unpack_from(">II", vid, 8)
        require(logical not in volumes[volume], "Duplicate logical eraseblock")
        data = block[data_offset:]
        if vid[5] == 2:
            size = struct.unpack_from(">I", vid, 20)[0]
            require(struct.unpack_from(">I", vid, 32)[0] == crc32(data[:size]), "Static data CRC")
        volumes[volume][logical] = data
    for table in volumes[2147479551].values():
        for index in range(128):
            record = table[index * 172:(index + 1) * 172]
            reserved = struct.unpack_from(">I", record)[0]
            if reserved:
                require(struct.unpack_from(">I", record, 168)[0] == crc32(record[:168]), "Volume table CRC")
                length = struct.unpack_from(">H", record, 14)[0]
                name = record[16:16 + length].decode()
                require(index not in volume_names or volume_names[index] == name, "Volume table mismatch")
                volume_names[index] = name
    root = volumes[0]
    require(sorted(root) == list(range(len(root))), "Rootfs logical eraseblock gap")
    ubifs = b"".join(root[index] for index in sorted(root))
    inodes, directory, file_data = {}, defaultdict(dict), defaultdict(dict)
    counts = Counter()
    offset = 0
    while True:
        offset = ubifs.find(b"\x31\x18\x10\x06", offset)
        if offset < 0:
            break
        if offset % 8:
            offset += 4
            continue
        checksum, sequence, size, kind = struct.unpack_from("<IQIB", ubifs, offset + 4)
        require(24 <= size <= 128 * 1024 and offset + size <= len(ubifs), "UBIFS node length")
        node = ubifs[offset:offset + size]
        require(checksum == crc32(node[8:]), f"UBIFS node CRC at {offset}")
        counts[kind] += 1
        if kind in (0, 1, 2):
            inode, key = struct.unpack_from("<II", node, 24)
        if kind == 0:
            inodes[inode] = {
                "size": struct.unpack_from("<Q", node, 48)[0],
                "mode": struct.unpack_from("<I", node, 104)[0],
                "inline": node[160:],
            }
        elif kind == 2:
            child = struct.unpack_from("<Q", node, 40)[0]
            length = struct.unpack_from("<H", node, 50)[0]
            directory[inode][node[56:56 + length].decode()] = child
        elif kind == 1:
            uncompressed, compression = struct.unpack_from("<IH", node, 40)
            content = node[48:]
            require(compression in (0, 2), "Unsupported UBIFS compressor")
            if compression == 2:
                content = zlib.decompress(content, -15)
            require(len(content) == uncompressed, "UBIFS decoded block length")
            file_data[inode][key & 0x1FFFFFFF] = content
        offset += (size + 7) // 8 * 8
    paths, seen, pending = {}, set(), [("", 1)]
    while pending:
        name, inode = pending.pop()
        paths[name] = inode
        if inode in seen:
            continue
        seen.add(inode)
        for child_name, child in directory[inode].items():
            pending.append((name + "/" + child_name, child))
    checked = []
    selected = (
        "/sbin/rc", "/usr/sbin/httpd", "/usr/sbin/nt_center",
        "/usr/lib/libshared.so", "/usr/bin/asd", "/www/js/httpApi.js",
        "/www/js/asus_policy.js", "/www/QIS_wizard.htm",
        "/www/Advanced_Privacy.asp", "/www/Advanced_FirmwareUpgrade_Content.asp",
        "/www/Advanced_ASUSDDNS_Content.asp", "/www/Advanced_Smart_Home_Alexa.asp",
        "/www/Advanced_Smart_Home_IFTTT.asp", "/www/state.js", "/www/mobile/js/handler.js",
    )
    for name in selected:
        require(name in paths, "Missing image file: " + name)
        inode = paths[name]
        require(stat.S_ISREG(inodes[inode]["mode"]), "Expected regular file: " + name)
        chunks = file_data[inode]
        require(sorted(chunks) == list(range(len(chunks))), "File data gap: " + name)
        content = b"".join(chunks[index] for index in sorted(chunks))[:inodes[inode]["size"]]
        require(len(content) == inodes[inode]["size"], "Short file: " + name)
        require(content == (staging / name.lstrip("/")).read_bytes(), "Image/staging mismatch: " + name)
        checked.append({"path": name, "sha256": hashlib.sha256(content).hexdigest()})
    require(inodes[paths["/etc"]]["inline"] == b"tmp/etc", "Unexpected /etc link")
    return {
        "path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
        "wfi_crc": hex(expected), "wfi_flags": flags, "boot_prefix_bytes": start,
        "ubi_blocks": len(payload) // 131072, "volumes": volume_names,
        "ubifs_nodes": sum(counts.values()), "inodes": len(inodes),
        "verified_image_files": checked,
    }


def guest_resolve(root, path):
    pending, done, hops = list(path.parts), [], 0
    while pending:
        part = pending.pop(0)
        if part in ("/", "."):
            continue
        if part == "..":
            if done:
                done.pop()
            continue
        candidate = root.joinpath(*done, part)
        if candidate.is_symlink():
            hops += 1
            require(hops <= 50, "Symlink cycle")
            target = Path(os.readlink(candidate))
            if target.is_absolute():
                done = []
            pending = list(target.parts) + pending
        else:
            done.append(part)
    return root.joinpath(*done)


def elf_audit(root):
    files = []
    for directory, _, names in os.walk(root, followlinks=False):
        for name in names:
            path = Path(directory) / name
            if path.is_symlink():
                continue
            with path.open("rb") as handle:
                if handle.read(4) == b"\x7fELF":
                    files.append(path)

    def inspect(path):
        text = readelf(path, "-dW", "--dyn-syms", "-lW")
        exports, imports = set(), set()
        for line in text.splitlines():
            match = re.match(r"\s*\d+:\s+[0-9a-f]+\s+\d+\s+\S+\s+(\S+)\s+\S+\s+(\S+)\s+(\S+)", line)
            if match:
                binding, section, symbol = match.groups()
                symbol = symbol.split("@")[0]
                if section != "UND":
                    exports.add(symbol)
                elif binding == "GLOBAL":
                    imports.add(symbol)
        return str(path.relative_to(root)), {
            "needed": re.findall(r"\(NEEDED\).*?\[(.*?)\]", text),
            "rpaths": [part for value in re.findall(r"\((?:RPATH|RUNPATH)\).*?\[(.*?)\]", text) for part in value.split(":")],
            "exports": exports, "imports": imports,
            "interpreter": re.findall(r"Requesting program interpreter: (.*?)\]", text),
        }

    with ThreadPoolExecutor(max_workers=8) as pool:
        entries = dict(pool.map(inspect, files))
    missing = []
    providers = {}
    for source, entry in entries.items():
        for name in entry["needed"]:
            if name in providers:
                continue
            directories = [path.replace("${ORIGIN}", "/" + str(Path(source).parent)).replace("$ORIGIN", "/" + str(Path(source).parent)) for path in entry["rpaths"]]
            # The inventory check also covers plugins loaded by a host whose
            # RPATH is inherited. Executable symbol closure is checked below.
            directories += [path for candidate in entries.values() for path in candidate["rpaths"] if "$" not in path]
            directories += ["lib", "usr/lib"]
            for directory in dict.fromkeys(directories):
                resolved = guest_resolve(root, Path(directory) / name)
                relative = str(resolved.relative_to(root))
                if relative in entries:
                    providers[name] = relative
                    break
            else:
                missing.append(name)
    require(not missing, "Missing runtime libraries: " + repr(sorted(set(missing))))
    checked = {}
    # Plugins can legitimately import symbols from their loading executable.
    # Check every dynamically interpreted executable, not plugins in isolation.
    for name, entry in entries.items():
        if not entry["interpreter"]:
            continue
        for interpreter in entry["interpreter"]:
            require(guest_resolve(root, Path(interpreter)).is_file(), "Missing ELF interpreter")
        closure, pending = set(), [name]
        while pending:
            current = pending.pop()
            if current in closure:
                continue
            closure.add(current)
            pending.extend(providers[dep] for dep in entries[current]["needed"])
        exports = set().union(*(entries[item]["exports"] for item in closure))
        imports = set().union(*(entries[item]["imports"] for item in closure))
        unresolved = sorted(imports - exports)
        require(not unresolved, name + " unresolved symbols: " + repr(unresolved))
        checked[name] = len(closure)
    shared = entries["usr/lib/libshared.so"]
    require("get_ASUS_privacy_policy" in shared["exports"], "Missing notification consent compatibility export")
    return {"elf_files": len(entries), "executables_checked": len(checked), "unresolved": [],
            "notification_consent_export": True}


def module_audit(staging, kernel):
    modules = list((staging / "lib/modules").rglob("*.ko"))

    def symbols(path):
        text = readelf(path, "-sW")
        return set(re.findall(r"\s__ksymtab_(\S+)", text)), set(re.findall(r"\sGLOBAL\s+\S+\s+UND\s+(\S+)", text))

    exports, _ = symbols(kernel)
    require(exports, "Kernel lacks export symbols; supply unstripped vmlinux")
    with ThreadPoolExecutor(max_workers=8) as pool:
        records = list(pool.map(symbols, modules))
    exports.update(set().union(*(exported for exported, _ in records)))
    versions = Counter()
    for module, (_, imported) in zip(modules, records):
        require(not imported - exports, str(module) + " missing kernel/module symbols")
        text = readelf(module, "-p", ".modinfo")
        versions.update(line.split("vermagic=", 1)[1].strip() for line in text.splitlines() if "vermagic=" in line)
    require(len(versions) == 1 and sum(versions.values()) == len(modules), "Inconsistent module versions")
    return {"modules": len(modules), "vermagic": dict(versions), "unresolved": []}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    report = {
        "image": image_audit(arguments.image, arguments.staging),
        "elf": elf_audit(arguments.staging),
        "kernel_modules": module_audit(arguments.staging, arguments.kernel),
        "limitations": ["Offline structural and symbol-name checks only; library-name inventory includes packaged RPATH locations, not a full dynamic-loader/versioned-ABI simulation; no target execution, mounting, flashing, hardware or exploitability certification"],
    }
    arguments.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
