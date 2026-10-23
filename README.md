# Unofficial RT-AX56U Asuswrt-Merlin fork

> [!WARNING]
> **This is NOT the official Asuswrt-Merlin repository.** This is an independent
> community fork maintained by [freakstatic](https://github.com/freakstatic) for
> experimental RT-AX56U compatibility work. It is not maintained, approved, or
> endorsed by the upstream Asuswrt-Merlin project or ASUS.
>
> The official upstream repository is
> **[RMerl/asuswrt-merlin.ng](https://github.com/RMerl/asuswrt-merlin.ng)**.
>
> **USE AT YOUR OWN RISK.** This firmware is experimental. Flashing it may brick
> your router, erase settings, or disrupt your network. There is no guarantee of
> safety, functionality, security, or successful recovery.

## RT-AX56U version branch

Version-specific RT-AX56U work belongs on
**[`rt-ax56u-3004.388.12_2`](https://github.com/freakstatic/asuswrt-merlin.ng/tree/rt-ax56u-3004.388.12_2)**,
based on the upstream `3004.388.12_2` tag. The `main` branch is not the RT-AX56U
3004.388.12_2 port or a firmware release. Do not assume that building `main`
produces this port.

## Experimental firmware warning

- A successful build or a reported successful flash is not a guarantee of safety,
  full functionality, security parity, or compatibility with another device.
- Use only a release that explicitly identifies your exact router model, hardware
  revision, and flashing procedure. Do not assume every branch or build artifact
  in this fork supports the RT-AX56U.
- Incorrect firmware or flashing procedures can make a router unusable and may
  require hardware-assisted recovery. Back up your settings and understand your
  recovery options before flashing. You assume the risks of using unofficial firmware.
- Report fork-specific problems to this fork's maintainer, not to upstream as if
  they were problems with an official Asuswrt-Merlin release.

Upstream authors retain credit for their work. The upstream information below is
preserved for attribution; its support links and supported-device list do not
imply upstream support for this fork or its RT-AX56U modifications.

---

## Original upstream README

asuswrt-merlin New Gen (version 382.xx and higher)
==================================================

#### Support is available via the forums at [SNBForums](https://www.snbforums.com/forums/asuswrt-merlin.42/).

Asuswrt-Merlin is an enhanced version of Asuswrt, the firmware used by Asus's modern routers.

The goal of this project is to fix issues and bring some minor functionality adjustments to the 
original Asus firmware.  While some features do get added, this is not the main focus of this project.  
It is not meant to replace existing projects such as Tomato or DD-WRT, but rather to offer an alternative 
for people who prefer the original firmware featureset.

This is the new development branch, originally based on Asus's 
3.0.0.4.382_xxxx firmware release.  Development of the 380.xx 
legacy branch has been dropped.

Please consult the Wiki for an up-to-date list of supported models:

https://github.com/RMerl/asuswrt-merlin.ng/wiki/Supported-Devices
