# RT-AX56U: unofficial 3006 compatibility port

> [!WARNING]
> **UNOFFICIAL — USE AT YOUR OWN RISK.** This port is not maintained, approved,
> or endorsed by Asuswrt-Merlin or ASUS. Incorrect firmware or flashing methods
> can brick a router, erase settings, or disrupt a network. A build or offline
> audit does not establish safe flashing, complete functionality, security parity,
> or successful recovery.

## Source and target

- Upstream: [RMerl/asuswrt-merlin.ng](https://github.com/RMerl/asuswrt-merlin.ng).
- Selected official source commit: `bf4f84bb430fb9e3bcc482847f97b3201a1959f1`.
- Version branch: `rt-ax56u-3006.102.10_alpha2`; runtime version
  `3.0.0.6 / 102.10 / alpha2`. This is not an official RT-AX56U release.
- Target: RT-AX56U, `947622GW`, BCM47622/ARM, Linux 4.1, NAND pure-UBI.
- The port reuses only the RT-AX56U-specific vendor inputs already shipped in
  this source tree. It does not substitute another model's private objects.
  The 65 checked RC/shared/HTTPD/libwebapi AX56U prebuilds match the selected
  upstream commit. Build-generated header/configuration changes, binary outputs,
  and local/private workspace material are not part of the port commits.

## Port scope

- Add RT-AX56U-only guards for newer private hooks absent from its retained
  vendor objects. Other models keep their original code paths.
- Keep the legacy `ASUS_EULA` flow for the RT-AX56U. The UI reads back saves,
  routes setup/service prompts to the legacy disclosure, and supports withdrawal
  without inventing PPv2 consent, a PPv2 version, or a timestamp. AWS IoT PPv2
  update/reset actions are disabled for this model so the legacy boolean cannot
  be misinterpreted as a PPv2 version.
- Hide the unsupported security-update switch and return an explicit error for
  the unavailable mesh firmware-update applet.
- Validate RT-AX56U QoS rule fields, shell-interpolated interfaces/rates, and
  IPsec certificate identifiers before generating commands/scripts.
- Preserve shipped Broadcom `cevent` prebuilt executables during `make clean`.
- Do not port the 3004 `httpd_reject_url` or WAN-mapping API changes: those hooks
  are absent from this 3006 source path.

This is a compatibility port, not a claim that every 3006 feature is available.
Mesh firmware updates through the unsupported applet are not available. Local
host tests do not qualify AiMesh, ISP-specific modes, WAN failover, VPN/QoS
combinations, hardware acceleration, boot, recovery, or persistence.

## Host-only checks

From the source root, run:

```sh
python3 tests/ax56u/integration_checks.py
python3 tests/ax56u/image_tag.test.py
VALIDATION_SANITIZE=1 python3 tests/ax56u/integration_checks.py
node tests/ax56u/ui_legacy_consent.test.js
sh tests/ax56u/validation_run.sh
VALIDATION_SANITIZE=1 sh tests/ax56u/validation_run.sh
```

These checks use the host compiler/Node runtime, mocks, and source inspection;
they do not execute firmware code or contact a router. `TMPDIR` can redirect
temporary test files. More detail is in [`tests/ax56u/README.md`](../tests/ax56u/README.md).

## Build and offline audit

Build only with the matching licensed Broadcom AX HND toolchain.
Use a compatible upstream build environment with its host dependencies,
including Python 3 for the AX56U image-tag adapter. The command below records
the prepared environment used for testing; it is not a complete clean-build
dependency-installation recipe. Generated StrongSwan outputs, local shims,
toolchains, and build intermediates are not published with these changes.
`release/src-rt/platform.mak` hard-codes the AX56U compiler under
`/opt/toolchains`; when using the local cache, override `CROSS_COMPILE` on the
make command line. From `release/src-rt-5.02axhnd.675x`:

```sh
toolchain_base=/path/to/toolchain-cache/brcm-arm-hnd
toolchain=$toolchain_base/crosstools-arm-gcc-5.5-linux-4.1-glibc-2.26-binutils-2.28.1
export TOOLCHAIN_BASE="$toolchain_base" SHELL=/bin/bash
export LD_LIBRARY_PATH="$toolchain/lib:$toolchain/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PATH="$PWD/../src/router/quagga:$PATH"
make -j1 SHELL=/bin/bash rt-ax56u HOST_EXTRACFLAGS=-fcommon \
  CROSS_COMPILE="$toolchain/usr/bin/arm-buildroot-linux-gnueabi-" \
  MAKEINFO=/bin/true
```

Before correcting the ASUS image tag, the 2026-10-24 local rebuild produced
`targets/947622GW/RT-AX56U_3006_102.10_alpha2_pureubi.w` (81,002,516 bytes,
SHA-256 `5b648b84719f00550cebdf73af989c892c6f89c90ffd1015a35d6dc93e74e0bf`).
The NOR image path was skipped because the corresponding CFE binary is
unavailable; the pure-UBI image was built. This host lacked `autopoint`,
`makeinfo`, and `gperf`, so the build used bundled gettext support, a
documentation-only `MAKEINFO=/bin/true` shim, and local StrongSwan gperf 3.1
outputs only after verifying byte-identical keyword lists and header templates.
It also used Quagga's generated local `libtool` on `PATH`, the cached toolchain,
and `HOST_EXTRACFLAGS=-fcommon`. Clean generated Autotools templates were kept
from triggering incompatible host-tool regeneration; only their timestamps
were advanced, not their contents. No host packages were installed. The log
still contains vendor `repo`-not-found and missing Broadcom private-object
warnings; the successful build does not resolve their impact on runtime
functionality.
Build intermediates are spread through the platform tree. Do not commit
generated objects, images, logs, certificates, or toolchain files. Do not flash
or change router settings as part of this work.

The read-only audit passed against the rebuilt image and final assembled root
filesystem (`fs`), not the package-layer `fs.install`: some system libraries
are relocated during filesystem assembly. It verified the WFI/UBI/UBIFS
structure, 15 selected image-to-rootfs file hashes, dependency and symbol-name
closure for 257 of 767 ELF files, the legacy consent export, and all 160 kernel
modules with consistent `4.1.52 SMP preempt mod_unload ARMv7 p2v8` vermagic and
no unresolved symbols. The strengthened auditor also passed for the corrected
image identified below. Raw build logs and local verification reports are not
included in the source commits.

```sh
python3 tests/ax56u/audit_firmware.py \
  --image release/src-rt-5.02axhnd.675x/targets/947622GW/RT-AX56U_3006_102.10_alpha2_pureubi.w \
  --staging release/src-rt-5.02axhnd.675x/targets/947622GW/fs \
  --kernel release/src-rt-5.02axhnd.675x/kernel/linux-4.1/vmlinux \
  --output /tmp/ax56u-3006-audit.json
```

The audit checks image/UBI/UBIFS structure, selected image-to-staging files,
ELF dependency and symbol-name closure, the legacy consent export, and kernel
module symbols/vermagic. It also checks the ASUS tag against the version read
from the packaged `libshared.so`, rather than trusting the image filename.
These are offline structural checks, not device tests,
a complete dynamic-loader/ABI model, a security certification, or an installation
guide.

## Validation status

Host integration, UI, portable validation, and sanitizer checks pass in the
current working tree. The firmware build and offline structural audit passed for
the pure-UBI image above. The NOR image was skipped because its CFE input is
absent, and the audit is not a device or hardware validation. The maintainer
subsequently reported successful testing on a router, with all tested features
working. That report was not independently observed, and the exact hardware
revision, flashing method, and detailed feature/test matrix have not been
recorded. It is not a guarantee of complete functionality, security, recovery,
or compatibility with another device. No router was contacted, flashed, or
reconfigured by the automated tooling.

### Post-review source fixes included in the audited image

The image above was rebuilt after these source fixes:

- Allow ordinary utility `-c` options in the safe-command fallback while still
  rejecting shell executables/applets, including shell paths passed to wrappers.
- Use the source-owned per-WAN IPv6 router-address helper for native DHCPv6
  DS-Lite. Prefix-only delegation no longer requires an unrelated RA address;
  unusable local addresses fail closed before tunnel creation.
- Route management-app and direct QIS policy callers through the legacy consent
  disclosure on AX56U, preserving explicit acceptance and non-AX56U behavior.

Regression tests cover these paths, including ASan/UBSan for the C helpers.
The offline audit establishes image structure and selected file consistency; it
does not validate these behaviors on a router; the separate maintainer report
above is limited hardware-test evidence, not a complete qualification.

### Current-version ASUS image tag

The shipped AX56U host `addvtoken` executable contains a compiled-in
`3.0.0.4 / 388 / 24353` ASUS tag. Copying a newer `version.h` beside that
executable does not change its embedded version. For AX56U only, the host-tool
make rule now installs `ax56u_addvtoken.py` as the packaging entry point. It
retains the original model-specific vendor tool for WFI packing, validates its
output, updates the ASUS version fields from the current source version header,
and recomputes the whole-image WFI CRC. Other models retain their existing rule;
no proprietary prebuilt is modified or replaced with another model's binary.

The existing tag layout has integer-only build/extension fields. Following its
decimal-prefix encoding, runtime `3.0.0.6 / 102.10 / alpha2` is represented as
tag version `3.0.0.6`, build `102`, extension `0`; the full `102.10_alpha2` remains
in the firmware. A numeric extension is stored in both its 16-bit legacy and
32-bit fields. No new field or fabricated numeric alpha-version encoding is
introduced.

The corrected pure-UBI image was regenerated from the already rebuilt and
verified raw UBI payload; no target recompilation was needed for this metadata
fix. Only the version tag and WFI CRC changed. Its SHA-256 is:

```text
2f65f1d2962416a5e8c4d46e4962775c5ca0a2bdea76a2a25f3e5fbcd31c2e05
```

The stronger offline audit and host/tag/UI/sanitizer regressions passed. These
automated results do not establish updater acceptance, hardware behavior,
flash safety, or recovery. No router was contacted or flashed by these checks.
