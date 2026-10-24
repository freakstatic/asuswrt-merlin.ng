# AX56U host-side regression checks

Run from the project root (uses the host C compiler, not the router toolchain):

```sh
python3 tests/ax56u/integration_checks.py
python3 tests/ax56u/image_tag.test.py
node tests/ax56u/ui_legacy_consent.test.js
sh tests/ax56u/validation_run.sh
VALIDATION_SANITIZE=1 sh tests/ax56u/validation_run.sh
```

`CC=clang` or another host compiler can be selected. Only the portable header
and test source are compiled; no firmware program is executed. Temporary host
test binaries use the system temporary directory (`TMPDIR` can override it) and
are removed afterward. UI requests and NVRAM are mocked; no router is contacted.

## Deliberate scope and compatibility

`release/src/router/shared/ax56u_compat_validation.h` is header-only.
It requires ordinary libc networking functions and no vendor libraries. RC and
HTTPD already include the shared header directory; no shared-library object,
export, or `shared.h`/`shared/Makefile` change is required for these validators.
The corresponding RC/HTTPD Makefiles include explicit header dependencies.
The separate legacy-consent shim is compiled into `libshared` for AX56U only.

- Both AX56U bandwidth-rule consumers validate the complete five-field record
  before tokenizing it or passing an address to a parser. Malformed records are
  skipped, not repaired, and are never emitted. Enable is exactly `0` or `1`;
  priority is decimal `0..31` (the existing UI's 32 slots, marks `30..61`). Rates
  are fully consumed decimal numbers in `1..10240000` kbit, bounded by the
  existing parent class. Fractional kbit values are retained because the UI
  stores Mb/s multiplied by 1024, e.g. `0.001` Mb/s becomes `1.024` kbit.
- IPv4 and MAC syntax is strict; IPv4 wildcards, CIDR `/1..30`, short ranges,
  and full ordered IPv4 ranges are normalized to checked addresses. `wlX.Y`
  interface syntax is accepted only for bounded decimal units/subunits. These
  entries remain non-client rules, as in the old implementation; actual guest
  shaping is separate. AiMesh MAC-to-IP resolution is retained, with its returned
  IP checked. WAN/guest interfaces and guest ceilings in this generated script
  are also checked before shell interpolation.
- AX56U automatic IPsec certificate generation checks WAN IPv4 with
  `inet_pton`, checks full DDNS names before the 128-byte destination copy,
  and restricts the device CN to ASCII letters/digits, `.`, `_`, `-`, and
  internal spaces (maximum 63 bytes). Shell-expansion characters, quotes,
  control characters and DN separators are rejected. Every variable string
  interpolated by this generator is covered; its paths/file names are static
  macros, and lifetime is a fully parsed decimal `0..36500` days (`0`/empty
  keeps the old 2200-day default). Invalid input aborts generation. The new
  script must open, close successfully, and receive mode 0700 before execution.
- Other models retain their existing private helpers and parsing behavior.
  No claim of full private-validator equivalence or full 12_2 security parity
  is made. The separate, older configurable certificate import/generator paths
  are outside this narrow fallback and were not changed.

## What the private URL hook actually does

Source for `httpd_reject_url` was not found. Static ARM disassembly of the
available 12_2 `httpd/prebuild/RT-AX58U/web_hook.o` **does** establish this function's
behavior (not execution): at `.text+0x71d8`, size `0x34`, it compares its argument
with `AiMesh_Node_FirmwareUpgrade.asp` using `strcmp`; only an exact match calls
`is_noFwManual()` and returns its nonzero result as 1. Other URLs return 0.
The relocation at `0x7208` points to `.LC181`, section `.rodata.str1.1+0x979`,
which contains that exact page name.

Object SHA-256:
`e96eab3ca75e1a4c7018ec0a2293a6b7c4dffebdab69a3eaaa75dd890c96bb1b`.

The retained AX56U `libwebapi/prebuild/RT-AX56U/priv_webapi.o` already exports
`is_noFwManual` (`.text+0x146c`); its SHA-256 is
`2f2ae0de0ba15803c918c2b66c0b33042efb8e53b3c152a21870aba7e605de6d`.
The source fallback reproduces the observed exact-page gate while retaining
that available capability API. It does **not** link the missing
`httpd_reject_url` or invent a filesystem/extension blacklist. Login, QIS,
ordinary firmware pages, CGI/API routes and static assets remain accepted.
The HTTPD caller supplies a query-stripped page, as it did for the private hook.
This is a manual-firmware capability restriction, not a generic injection,
traversal or authentication sanitizer. The review's mere omission of the hook
does not establish a broader URL-security fix.

The narrow observation above was recovered read-only using ARM `objdump`, `nm`,
`readelf`, and an exact relocation-backed string read. No target code was run,
and no object from another router model is linked into this build.

The tests cover valid existing inputs, numeric limits/overflow/partial parses,
bad record cardinality, IPv4/MAC/range/interface syntax, shell substitutions,
quotes/control characters/DN injection and the observed URL capability gate.
They do not replace a clean firmware build, QoS/IPsec integration tests, or
router testing; these host tests perform none of those operations.

## Offline image audit

`audit_firmware.py` reads an image and its matching final build tree. It checks
whole-image CRC, UBI/UBIFS records, selected image files against staging,
declared ELF library names and strong-symbol closure, and module symbol names
and vermagic. It does not mount, execute, or flash firmware.
It also reads version exports from the packaged `libshared.so` without loading
that library, and checks the ASUS image tail against their legacy numeric
projection. A stale vendor extension such as `24353` is rejected when the
runtime extension is `2-ax56u1`.

The image-tag tests require Python 3 and host `make`. They use synthetic
NAND/WFI fixtures and a fake host vendor writer, not router executables.
They cover both 3004 and 3006 version projections, the two 3004 image formats,
both extension widths, CRC regeneration, preservation of non-tag bytes and
CFEROM prefixes, malformed inputs, atomic output replacement, and AX56U-only
make-rule selection. The real adapter retains the unchanged model-specific
vendor host writer; no proprietary input is replaced.

It requires Python 3 and host `readelf`. For example, from the repository root:

```sh
sdk=release/src-rt-5.02axhnd.675x
python3 tests/ax56u/audit_firmware.py \
  --image "$sdk/targets/947622GW/RT-AX56U_3004_388.12_2-ax56u1_pureubi.w" \
  --staging "$sdk/targets/947622GW/fs" \
  --kernel "$sdk/kernel/linux-4.1/vmlinux" \
  --output /tmp/ax56u-verification.json
```

These checks are not a full dynamic-loader/ABI simulation, kernel mount/fsck,
security certification, or hardware boot/recovery test.
