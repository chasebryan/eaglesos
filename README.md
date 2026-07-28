<!--
     Copyright 2024, UNSW
     Copyright 2026, Chase Bryan
     SPDX-License-Identifier: CC-BY-SA-4.0
-->

# EaglesOS

**EaglesOS** is a native x86_64 operating-system project maintained by Chase
Bryan. It begins as a fork of [LionsOS](https://github.com/au-ts/lionsos) and
keeps the seL4 microkernel as its host kernel.

> **Status:** architecture bootstrap. The pinned seL4/Microkit/sDDF substrate
> has built and booted a non-VT-x x86_64 QEMU probe, but no top-level EaglesOS
> x86 system, installer, supported physical-hardware image, or finished release
> exists. EaglesOS currently makes no product-specific claim of security,
> performance, hardware support, or formal verification.

## Purpose

EaglesOS is intended to become a full-fledged, installable operating system
that can replace the owner's Linux distribution on a supported x86_64
computer. It is not a Linux rebrand: seL4 boots the machine and enforces the
capability and isolation model.

The initial priorities are to:

- preserve a trusted, reproducible inherited baseline on AArch64;
- establish QEMU `q35` as the native x86_64 runtime spine;
- upgrade to Microkit 2.3/seL4 16 before VT-x or physical DMA work;
- build process, resource, storage, network, userland, desktop, installation,
  update and recovery layers behind explicit acceptance gates;
- qualify one Lenovo ThinkPad T490 hardware profile before broader PC support;
- preserve explicit component boundaries and least-authority design;
- measure divergence from upstream at every release; and
- attach every security or verification statement to evidence that applies to
  the exact EaglesOS revision being described.

The authoritative direction and milestone gates are in the
[EaglesOS x86_64 product plan](docs/PRODUCT_PLAN.md). The core architecture
decision is [ADR-0001](docs/adr/0001-x86_64-general-purpose-architecture.md).
The original [takeover assessment](docs/TAKEOVER_PLAN.md) remains as the
historical repository audit and prioritized inherited-risk record.

## Upstream baseline

EaglesOS was created on July 28, 2026 from:

| Field | Baseline |
| --- | --- |
| Upstream | `au-ts/lionsos` |
| Branch | `main` |
| Commit | `4a5656a32574049817f62054832abeae85861ff5` |
| Commit date | July 15, 2026 (UTC) |
| Foundation | seL4 Microkit and the inherited LionsOS component architecture |

The upstream commit history, copyright notices, SPDX identifiers, license
texts, and authorship records are intentionally retained.

EaglesOS is not affiliated with or endorsed by UNSW, the Trustworthy Systems
group, LionsOS, the seL4 Foundation, or upstream contributors. Security,
performance, and verification results published for upstream LionsOS do not
automatically apply after EaglesOS changes the inherited source.

## Compatibility during bootstrap

Inherited paths and programmatic identifiers such as `include/lions` remain in
place initially. Renaming those interfaces without a compatibility plan would
create unnecessary breakage and obscure whether the upstream baseline still
builds. Identity changes therefore begin at the project boundary; internal
renaming will occur only through tested, reviewable changes.

## Licensing

Licensing remains file-specific and is identified by each file's SPDX header.
The root [LICENSE](LICENSE) contains the BSD 2-Clause license. Documentation is
generally licensed under CC BY-SA 4.0 as described in
[LICENSE.md](LICENSE.md). When those summaries and an individual SPDX header
differ, the individual file header controls.

## Next gate

The next architecture gate is `X0`: a first-class, bounded
`x86_64_generic` QEMU boot test with retained serial logs, Microkit reports,
tool versions and image hashes. The following gate upgrades Microkit to 2.3 and
seL4 16 before any VT-x guest or supported physical-DMA work.

Until the product plan's runtime, hardware, lifecycle and recovery gates are
complete, this repository is development source—not a bootable EaglesOS
installation release.
