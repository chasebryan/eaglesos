<!--
     Copyright 2026, Chase Bryan
     SPDX-License-Identifier: CC-BY-SA-4.0
-->

# ADR-0001: x86_64 general-purpose architecture

Status: accepted

Date: July 28, 2026

## Context

EaglesOS inherits LionsOS, a set of statically composed seL4 Microkit systems
for embedded and cyberphysical workloads. The inherited repository supplies
valuable filesystem, network, runtime, driver and isolation components, but it
does not provide a general process model, multi-user system, desktop, package
manager, installer, update system, or broad PC hardware support.

The product requirement is now explicit:

> EaglesOS must run natively on the owner's x86_64 computer, keep seL4 as its
> host kernel, and grow into a full-fledged operating system capable of
> replacing the owner's Linux distribution.

This supersedes the initial appliance-only product recommendation in the
takeover assessment.

The selected first physical profile is a Lenovo ThinkPad T490 with an Intel
i5-8365U, UEFI, VT-x/EPT, VT-d, Intel UHD 620, I219-LM Ethernet, Intel CNVi
Wi-Fi, Samsung NVMe and Intel xHCI.

The available foundation already supports a meaningful x86 bootstrap:

- seL4 supports 64-bit PC99.
- Microkit packages `x86_64_generic` and `x86_64_generic_vtx`.
- sDDF supplies PC99 serial, HPET and QEMU-oriented PCI virtio network/block
  paths.
- A pinned non-VT-x serial system has built and booted through QEMU `q35`.

The hard problem is therefore the operating-system service and hardware stack,
not an x86 port of the seL4 kernel.

## Decision

### 1. seL4 is the native host kernel

EaglesOS boots seL4 directly on x86_64. A Linux kernel will not host EaglesOS,
provide the trusted system services, or define the native application model.

Kernel verification claims will name the exact seL4 configuration and exclude
unverified boot, MCS, IOMMU, driver, Microkit, service and application code
unless separate evidence applies.

### 2. QEMU q35 is the Tier 1 integration machine

`x86_64_generic` on QEMU `q35` is the always-available target. It must have
bounded runtime gates for boot, timer, network, storage, native POSIX and WASM.

The existing AArch64 QEMU system remains a regression profile while x86 reaches
parity. It is not the destination hardware profile.

### 3. The ThinkPad T490 is the first physical profile

EaglesOS supports one known computer before claiming generic-PC support.
Physical bring-up begins as a read-only live image from removable media. It
must enumerate platform data and provide a safe diagnostic console without
writing the internal disk.

Hardware is promoted incrementally: discovery and interrupt routing, IOMMU,
NVMe, wired networking, USB/HID, display, audio, then power management and
optional Wi-Fi. Each promotion requires hardware-in-loop acceptance and
recovery evidence.

### 4. Microkit remains the initial trusted-service fabric

Static Microkit protection domains remain the bootstrap environment for
platform, driver, storage, network, identity, logging and update services. This
preserves explicit authority and reuses the inherited component model.

A process/resource manager will initially control a bounded pool of
preallocated application domains. It will prototype:

- isolated address spaces;
- capability and physical-memory allocation;
- native ELF and WASI loading;
- process identity and lifecycle;
- fault handling, termination, restart and full reclaim;
- names/service discovery; and
- manifest-declared authority.

At the C0 checkpoint, measured limits decide whether this model is sufficient
or whether EaglesOS replaces the bootstrap with a more general seL4 root
server. The decision cannot be deferred beyond dynamic-process work, and it
cannot be made without a working prototype.

### 5. Native ELF and WASI are first-class

Native programs using the published EaglesOS libc/POSIX profile and sandboxed
WASI programs are stable product surfaces. MicroPython remains a supported
system-tool and constrained-application runtime where it is a good fit.

The system must define unsupported behavior honestly. Stubbed operations such
as successful no-op memory protection are not a compatibility contract.

### 6. Linux may only be an optional compatibility island

An x86 Linux guest may later provide transitional application or driver
compatibility. It is untrusted, replaceable, least-authority, and never the
host. Native system services and a usable native console/desktop cannot depend
solely on it.

This option remains an explicit release-policy decision because “seL4 host”
does not necessarily mean “no Linux code anywhere.” Choosing a zero-Linux
release increases the native driver and application-porting scope but does not
change the host architecture.

### 7. Microkit 2.3/seL4 16 is required before VT-x or physical DMA

The pinned Microkit 2.2 stack is allowed only for the non-VT-x inherited
baseline. seL4 16 fixes a critical VT-x 64-bit guest escape present in the
embedded seL4 15 kernel. Microkit 2.3 also changes x86 IOMMU and system
description behavior.

No VT-x guest or supported physical DMA work may use Microkit 2.2. The upgrade
is a separately reviewed and fully requalified milestone.

### 8. Physical boot uses a Multiboot2 live/recovery path first

Microkit produces a 64-bit kernel ELF, a 32-bit boot-compatible kernel ELF and
an initial-task boot module. EaglesOS will package these with a Multiboot2
bootloader into hybrid BIOS/UEFI media.

SeaBIOS and OVMF QEMU gates precede physical boot. Installation to an internal
disk is a later product operation with explicit target confirmation, rollback
and recovery.

### 9. Distribution mechanisms are capability-aware

Processes, packages and services declare authority in manifests. Install and
update operations cannot silently expand a component's device, filesystem,
network or IPC authority.

Package signatures, provenance and versions are necessary but insufficient:
the reviewable authority delta is part of the transaction and release record.

## Trust architecture

```text
+---------------------------------------------------------------+
| Isolated applications                                         |
| native ELF | WASI | MicroPython | optional Linux guest        |
+---------------------------- capability interfaces ------------+
| Process/resource manager | session and compatibility services |
+---------------------------------------------------------------+
| VFS/storage | network | identity | time | logging | update     |
+---------------------------------------------------------------+
| device brokers: PCI/IOMMU | NVMe | NIC | USB/HID | GPU/audio  |
+---------------------------------------------------------------+
| Microkit trusted-service fabric and explicit system graph      |
+---------------------------------------------------------------+
| seL4 x86_64 host kernel                                        |
+---------------------------------------------------------------+
| QEMU q35 or supported ThinkPad T490 hardware                   |
+---------------------------------------------------------------+
```

No diagram box is trusted merely because it is low in the picture. The threat
model and capability graph must state which properties depend on each service.
Drivers and compatibility guests should be isolated and restartable wherever
the device and DMA model permit.

## Consequences

### Positive

- seL4 remains the actual operating-system kernel.
- The plan reuses proven x86 Microkit/sDDF work instead of starting with a raw
  kernel port.
- QEMU provides a deterministic path to native network, storage and runtime
  parity.
- One exact physical profile bounds the otherwise unmanageable PC-driver
  problem.
- Static trusted services preserve reviewability while dynamic application
  management is developed behind a measured checkpoint.
- Optional Linux compatibility does not contaminate the host architecture.

### Costs and risks

- This is a multi-year operating-system program, not a packaging project.
- Dynamic memory/capability management grows the trusted computing base and is
  not supplied by current EaglesOS.
- The inherited filesystem and POSIX layers need safety and semantic repairs
  before multi-process use.
- Physical x86 support requires ACPI/PCI discovery, IOMMU-safe DMA and several
  substantial native drivers.
- Intel UHD graphics, Wi-Fi, audio and suspend may dominate the T490 schedule.
- Microkit's current x86 VM limitations constrain compatibility-guest
  performance.
- seL4's kernel proofs do not prove EaglesOS user-space services or VT-x/IOMMU
  configurations.

## Rejected alternatives

### Rebrand an existing Linux distribution

Rejected because Linux would remain the host kernel and seL4 would not define
the system's isolation or authority model.

### Keep EaglesOS appliance-only

Rejected because it contradicts the selected general-purpose x86 product.
Appliance examples remain valuable regression fixtures.

### Claim generic x86 PC support immediately

Rejected because the inherited path assumes QEMU `q35`, legacy COM1, HPET and
fixed PCI locations. Support must be earned on one hardware profile.

### Port every inherited example before proving x86 boot

Rejected because it mixes architecture, device and application failures. The
ordered X0–X4 gates isolate serial/timer, POSIX, network, storage and WASM.

### Enable VT-x on Microkit 2.2

Rejected due to the critical seL4 13–15 x86_64 guest-escape defect and missing
Microkit 2.3 x86 IOMMU/VM fixes.

### Put the whole desktop in one privileged protection domain

Rejected because it discards the capability boundaries and fault containment
that justify seL4.

## Required checkpoints

| Checkpoint | Decision evidence |
| --- | --- |
| X0 | Native x86 Microkit boot and device-event gate is deterministic |
| U0 | Microkit 2.3/seL4 16 passes all inherited and x86 gates |
| C0 | Preallocated slots versus a general root server is decided from lifecycle/reclaim stress |
| B0 | Multiboot2 BIOS/UEFI media boots without undeclared writes |
| H0 | T490 live preview enumerates hardware and recovers safely |
| H1 | Native driver/IOMMU set meets the published T490 contract |
| D0 | Native desktop is usable without making a Linux guest trusted |
| R0 | Install/update/rollback preserve authority and user data |
| V1 | Owner's daily workloads pass on released media |

## References

- [EaglesOS product plan](../PRODUCT_PLAN.md)
- [Microkit 2.3.0 release notes](https://docs.sel4.systems/releases/microkit/2.3.0.html)
- [seL4 16.0.0 release and security notes](https://docs.sel4.systems/releases/sel4/16.0.0.html)
- [Microkit 2.3 x86 manual](https://docs.sel4.systems/projects/microkit/manual/2.3.0/)
- [seL4 supported platforms](https://docs.sel4.systems/Hardware/)
- [seL4 verified configurations](https://docs.sel4.systems/projects/sel4/verified-configurations.html)
- [GRUB Multiboot2 module command](https://www.gnu.org/software/grub/manual/grub/html_node/multiboot2_005fmodule.html)

## Review triggers

Revisit this ADR if:

- Microkit's dynamic child/resource facilities materially change;
- x86 virtual machines gain a production-quality multi-vCPU path;
- the T490 cannot reach a safe usable console without an unacceptable trusted
  driver;
- the application ABI decision makes the hybrid process model infeasible;
- a non-Linux compatibility system provides a better bounded path; or
- lifecycle/reclaim evidence requires a general seL4 root server.
