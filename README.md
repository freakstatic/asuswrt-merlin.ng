# Unofficial RT-AX56U Asuswrt-Merlin 3006 port

> [!WARNING]
> **This is NOT the official Asuswrt-Merlin repository.** This is an independent
> community fork maintained by [freakstatic](https://github.com/freakstatic).
> It is not maintained, approved, or endorsed by Asuswrt-Merlin or ASUS.
>
> The official upstream repository is
> **[RMerl/asuswrt-merlin.ng](https://github.com/RMerl/asuswrt-merlin.ng)**.
>
> **USE AT YOUR OWN RISK.** This firmware is experimental. Flashing it may brick
> your router, erase settings, or disrupt your network. Safety, functionality,
> security, and successful recovery are not guaranteed.

## Version branch

This branch, **`rt-ax56u-3006.102.10_alpha2`**, contains the experimental RT-AX56U
compatibility port based on upstream commit
`bf4f84bb430fb9e3bcc482847f97b3201a1959f1`. It is not an official RT-AX56U release.
The separate 3004.388.12_2 port remains on `rt-ax56u-3004.388.12_2`.

See the [3006 port notes](docs/rt-ax56u-3006-port.md) for source identity,
compatibility limitations, build boundaries, image tagging, and test scope.
Host regression tests and the offline auditor are described in
[`tests/ax56u/README.md`](tests/ax56u/README.md).

The maintainer reports successful device testing, with all tested features
working. This is not a complete test matrix, independent verification, or a
guarantee for another device. No universal flashing or recovery procedure is
asserted here. Confirm the exact hardware and supported image format first.

These changes contain source, tests, and documentation, not a firmware binary,
toolchain, replacement proprietary objects, or private build material.
For fork-specific problems, follow [SUPPORT.md](SUPPORT.md), not upstream's
official-release support channels.

## Attribution

Based on [Asuswrt-Merlin](https://github.com/RMerl/asuswrt-merlin.ng) and ASUSWRT.
Credit belongs to the upstream authors and contributors for their work.
Existing licenses and copyright notices are unchanged.
