# RT-AX56U host-side regression checks

Run from the source root with the host compiler and Node.js:

```sh
python3 tests/ax56u/integration_checks.py
python3 tests/ax56u/image_tag.test.py
VALIDATION_SANITIZE=1 python3 tests/ax56u/integration_checks.py
node tests/ax56u/ui_legacy_consent.test.js
sh tests/ax56u/validation_run.sh
VALIDATION_SANITIZE=1 sh tests/ax56u/validation_run.sh
```

`CC=clang` or another host C compiler can be selected. These checks compile
only portable source/test code or an extracted applet stub; UI HTTP calls and
NVRAM are mocked. They do not compile or execute router binaries and do not
contact a router. `TMPDIR` can be set to control temporary files.

The portable validator tests cover decimal/rate parsing, QoS addresses and
records, interface names, IPsec identifiers, and lifetime limits. Integration
checks assert that the model-scoped source guards and validator calls remain in
place, and exercise the unsupported mesh-update stub and legacy consent adapter.
They also compile and test the AX56U argv-based safe-command fallback, including
rejection of shell operators and shell execution (directly or through wrappers),
while allowing the legitimate `ethswctl -c pause` option. The switch utility in
these tests is a fake host executable, never the router's utility.
The extracted DS-Lite branch and source-owned IPv6 router-address helper are
tested together with mocked per-WAN settings: prefix-only DHCPv6-PD, configured
router addresses, rejection of unusable local addresses, and the retained
non-native RA-address path. `VALIDATION_SANITIZE=1` enables ASan/UBSan for these
integration tests as well as the separate portable validation runner.
The UI harness covers consent read/write, failure/read-back behavior, QIS/DDNS
gates, withdrawal, unsupported security UI, non-AX56U behavior, and JavaScript
syntax including localized disclosure strings.
QIS entry points also cover both management-app user agents and direct
`apply.Policy()` calls, without silently granting legacy consent or changing
the PPv2 flow on other models.

The image-tag tests use synthetic NAND/WFI fixtures and a fake host vendor
writer. They check current-header version encoding, both numeric extension
widths, CRC regeneration, preservation of all non-tag bytes, rejection of
unexpected targets/layouts, atomic output replacement, and the AX56U-only make
rule. They never execute a router binary or modify a real image.

For a produced image, `audit_firmware.py` performs read-only structural checks;
its inputs and limitations are described in
[`docs/rt-ax56u-3006-port.md`](../../docs/rt-ax56u-3006-port.md). It neither
mounts nor executes firmware content.
It also compares the ASUS tail against the full version exported by the
packaged `libshared.so`, using the legacy tag's documented numeric projection.
