<!--
     Copyright 2026, Chase Bryan
     SPDX-License-Identifier: CC-BY-SA-4.0
-->

# EaglesOS x86_64 product plan

Status: authoritative working product plan

Decision date: July 28, 2026

Target: a native x86_64 general-purpose operating system with seL4 as the host
kernel

## Product decision

EaglesOS will become a full-fledged, installable x86_64 operating system. seL4
will boot the machine, enforce the capability model, isolate services and
applications, and remain the host kernel. EaglesOS will not be a themed Linux
distribution.

The inherited LionsOS appliance systems are useful components and test
fixtures, not the final product architecture. Their strongest ideas remain
binding:

- explicit authority and isolation;
- small, inspectable services rather than a privileged monolith;
- performance measured on the exact released revision;
- modular drivers and application runtimes;
- security and verification claims bounded by reproducible evidence; and
- deliberate support for known hardware rather than nominal support for every
  machine.

“Replace a Linux distribution” is a release outcome, not a bootstrap claim.
EaglesOS reaches that outcome only when it can install, boot, update, recover,
run the owner's required daily workloads, and protect persistent user data on a
supported computer.

## Definition of the product

### Required properties

- Native x86_64 execution on seL4; Linux is never the host kernel.
- A real process and resource model with isolated address spaces, lifecycle,
  reclaim, credentials, and fault containment.
- Persistent multi-user storage, networking, a base command-line environment,
  graphical sessions, input, audio, and power management.
- Reproducible installation media, signed updates, rollback, recovery, package
  provenance, and a published support contract.
- One fully supported physical computer before attempting generic-PC support.
- A stable native API and an explicit compatibility strategy for existing
  applications.

### Compatibility policy

Native ELF programs and WASI applications are first-class execution models.
MicroPython remains useful for system tooling and constrained applications.

An optional Linux virtual machine may later be used as an untrusted
compatibility island while native support grows. It must never become the
EaglesOS host, trusted service fabric, update authority, or sole path to a
usable system. The current x86 Microkit virtual-machine limit of one vCPU also
makes such a guest unsuitable as the final desktop architecture.

Whether a release may contain any Linux guest code is an explicit release
decision. It does not block the native x86 bootstrap or native userland work.

### Support tiers

| Tier | Contract |
| --- | --- |
| Tier 1 virtual | QEMU `q35`, `x86_64_generic`, deterministic runtime gates and retained evidence on every merge |
| Tier 1 hardware | Lenovo ThinkPad T490 hardware profile after read-only bring-up and driver qualification |
| Regression | QEMU `qemu_virt_aarch64` remains an inherited behavior and portability gate |
| Experimental | Other x86 computers, VT-x guests, showcase systems, and unqualified boards |

“x86_64” initially means the published QEMU machine and the selected T490
profile. It does not mean arbitrary PCs.

## Evidence that the foundation is viable

The architecture risk is lower than the top-level EaglesOS examples suggest:

- seL4 supports 64-bit PC99 systems.
- Microkit 2.2.0 contains `x86_64_generic` and
  `x86_64_generic_vtx` board packages.
- The pinned sDDF revision contains an x86_64 compiler target, PC99 serial,
  HPET, PCI virtio block/network, NVMe experiments, and QEMU `q35` launch
  support.
- The pinned musl fork and libmicrokitco contain x86_64 support.

On July 28, 2026, the pinned non-VT-x stack built and booted the sDDF serial
system under QEMU 9.2.4. The observed path was:

```text
SeaBIOS -> seL4 PC99 boot -> ACPI/APIC discovery -> user space
        -> CapDL initializer -> Microkit monitor
        -> PC99 serial driver/virtualizer -> two isolated clients
```

Required boot markers and both clients' prompts were observed before a bounded
20-second termination. The generated image identities were:

| Artifact | SHA-256 |
| --- | --- |
| `loader.img` | `631453224238def65f5d5943937e678a1bc45dc8ced6b16d59acaa1bea284588` |
| `sel4_32.elf` | `540e2fa69cabee1a7b68976caaf18cf29e6a34094e422b4bafb65948ce45fd18` |
| `sel4.elf` | `bbe85aff961356875e43483cceea95e29c00bc2225da18c5f4beb08c8aeb5763` |

A separate read-only audit also booted the pinned sDDF HPET timer system and
observed repeated timeout delivery. These probes prove the dependency
substrate, not an EaglesOS x86 product image. No top-level EaglesOS example
currently declares x86_64 support.

## Mandatory dependency upgrade

The pinned Microkit 2.2.0 SDK embeds seL4 15.0.0. It is acceptable only for the
short-lived, non-VT-x baseline probe.

seL4 16.0.0 fixes a critical x86_64 VT-x virtual-machine escape affecting seL4
13 through 15 when 64-bit guests are enabled. Microkit 2.3.0 moves to seL4 16
and adds x86 IOMMU configuration, runtime boot information, and x86 virtual
machine fixes. Therefore:

- EaglesOS must not enable `x86_64_generic_vtx` on Microkit 2.2.
- EaglesOS must not run a Linux compatibility guest on Microkit 2.2.
- EaglesOS must upgrade and requalify Microkit 2.3 before physical DMA, IOMMU,
  or VT-x work becomes supported.
- The upgrade must account for Microkit 2.3's breaking x86 IOMMU, IOAPIC,
  PCI-address, VCPU, and system-description changes.

Authoritative references:

- [Microkit 2.3.0 release notes](https://docs.sel4.systems/releases/microkit/2.3.0.html)
- [seL4 16.0.0 security notes](https://docs.sel4.systems/releases/sel4/16.0.0.html)
- [Microkit x86 boot and CPU requirements](https://docs.sel4.systems/projects/microkit/manual/2.3.0/)
- [seL4 platform matrix](https://docs.sel4.systems/Hardware/)
- [seL4 verified configurations](https://docs.sel4.systems/projects/sel4/verified-configurations.html)

## Selected physical profile

The first hardware profile is the current development host, a Lenovo ThinkPad
T490 (20N3):

| Area | Detected hardware |
| --- | --- |
| CPU | Intel Core i5-8365U, 8 logical CPUs |
| Firmware | UEFI |
| Isolation | VT-x/EPT and active VT-d/IOMMU groups |
| Graphics | Intel UHD 620, PCI `8086:3ea0` |
| Wired network | Intel I219-LM, PCI `8086:15bd` |
| Wireless | Intel CNVi, PCI `8086:9df0` |
| Storage | Samsung NVMe, PCI `144d:a808` |
| USB | Intel xHCI, PCI `8086:9ded` |

The CPU exposes the `pat`, `xsave`, `fpu`, `sse`, `pdpe1gb`, and
`fsgsbase` features required by Microkit's generic x86 configuration.

This inventory makes the T490 a viable target; it does not make it supported.
Native GPU/display, Ethernet, Wi-Fi, NVMe discovery, USB/HID, audio, ACPI power,
battery, suspend, and thermal services remain product work.

The first physical image will be a read-only live preview. It must not write to
the internal disk until storage discovery, IOMMU policy, recovery, and explicit
operator confirmation have been tested under emulation and on disposable
media.

## Architecture

The accepted direction is recorded in
[ADR-0001](adr/0001-x86_64-general-purpose-architecture.md).

```text
seL4 x86_64 host kernel
└── static Microkit trusted core
    ├── boot, platform and resource management
    ├── device and DMA brokers
    ├── storage/VFS, network, identity, time and logging services
    ├── process/application manager
    └── isolated application domains
        ├── native ELF programs
        ├── WASI programs
        ├── MicroPython tools
        └── optional untrusted Linux compatibility VM
```

Microkit remains the bootstrap and trusted-service composition layer while the
dynamic application model is prototyped. A defined architecture checkpoint
will decide whether preallocated application slots are sufficient or whether
EaglesOS needs a more general seL4 root server. That decision must be based on
working lifecycle/reclaim tests, not preference.

## Reusable assets and missing foundations

| Area | Reusable now | Missing for the product |
| --- | --- | --- |
| Kernel/isolation | seL4, Microkit PDs, capabilities, queues and notifications | Dynamic resource ownership, process creation, reclaim and service supervision |
| x86 platform | PC99 boot, COM1, HPET, `q35`, PCI virtio patterns | General ACPI/PCI discovery, MSI routing, SMP policy, hotplug and physical-machine qualification |
| Memory | Isolated static mappings and a simple `mmap` arena | Pager, real protection changes, reclaim, file mappings, guard pages, ASLR and quotas |
| Storage | Block queues, virtio block, GPT/FAT/NFS components | Multi-client VFS, Unix semantics, crash-resilient root FS, encryption, mounts and recovery |
| Network | virtio-net, lwIP, DHCP/DNS plumbing and TCP tests | Real NIC/Wi-Fi, UDP/IPv6 parity, TLS policy, multi-process broker and stable configuration |
| Runtimes | Native musl bridge, MicroPython and WAMR/WASI | ELF loader, ABI contract, threads, signals, dynamic linker and broad application compatibility |
| Identity/security | seL4 capability isolation | CSPRNG, users/groups, credentials, login, secret storage, audit, secure boot and signed updates |
| Services | Individual static components | Init/supervision, names, devices, time, configuration, health, restart and power services |
| Graphics/input/audio | Experimental framebuffer and virtio-GPU pieces | PCI display path, compositor, xHCI/HID, sessions, GUI toolkit, audio and accessibility |
| Lifecycle | Reproducible source/toolchain work in progress | Installer, packages, atomic updates, rollback, rescue, backup, SBOM and support policy |
| Observability | Serial logging and test sentinels | Structured logs, crash records, metrics, tracing, watchdogs and diagnostics |

## Confirmed inherited blockers

These defects remain release blockers regardless of target architecture:

| Finding | Required response |
| --- | --- |
| Filesystem allocator scans beyond its 511-entry metadata contract | Derive capacities from the queue/mapping and add exhaustion/invalid-free tests |
| NFS path arrays have reversed dimensions; rename/callback lifecycle is incorrect | Repair layout, ownership, in-flight accounting and one-completion behavior |
| FAT accepts paths larger than its stack buffer and mishandles invalid/EOD operations | Bound paths, return explicit errors and guarantee one completion |
| MicroPython filesystem paths/transfers violate buffer and cleanup ownership | Bound or chunk I/O, repair the double free and test all failure paths |
| I2C, framebuffer and firewall bindings omit boundary validation | Validate sizes/arithmetic/interfaces and add malformed-input tests |
| POSIX `accept` and descriptor dispatch can overwrite/call missing operations | Respect caller lengths, validate operations and add negative tests |
| `getrandom()` uses `rand()` | Add a defined CSPRNG/entropy service or fail clearly |
| PID, UID/GID, memory protection and syscall behavior are hard-coded stubs | Replace them through the process/identity/VM milestones |

The detailed initial audit remains in the
[takeover assessment](TAKEOVER_PLAN.md).

## Delivery rules

1. Every supported claim requires a bounded automated gate and retained
   evidence for an exact commit and dependency graph.
2. QEMU `q35` is the always-available x86 integration spine; physical hardware
   is a separate support tier.
3. AArch64 remains a regression target until an explicit deprecation decision.
4. Fix unsafe shared protocols before scaling them to dynamic multi-process
   use.
5. Do not enable VT-x or physical DMA on a dependency version with known
   critical defects.
6. Add one hardware profile at a time. “Generic PC” is not a test plan.
7. Keep kernel-verification claims distinct from unverified Microkit, MCS,
   boot, IOMMU, driver, service and application code.
8. Installation and hardware probes are non-destructive by default.
9. Prefer small reviewable changes with positive, negative and timeout
   conditions over broad ports.
10. Linux compatibility, if used, remains isolated and replaceable; it cannot
    define the trusted EaglesOS architecture.

## Milestones and exit gates

Milestones are evidence gates, not date promises.

### F0 — Trusted reproducible foundation

Deliverables:

- secure GitHub workflow boundaries and truthful build/runtime labels;
- recursively materialized, pinned dependencies;
- a canonical Nix toolchain with an executable WASI SDK;
- a toolchain doctor, source checks and development guide;
- focused fixes for confirmed safety/lifecycle blockers; and
- bounded AArch64 POSIX, WASM and FileIO runtime evidence to preserve inherited
  behavior.

Exit:

- fresh clones can reproduce the toolchain and dependency identities;
- all source and license checks pass;
- known P0 memory-safety bugs have regression coverage;
- AArch64 runtime gates have explicit success/failure/timeout contracts.

### X0 — First-class x86_64 boot gate

Turn the proven sDDF timer or serial probe into an EaglesOS-owned gate.

Exit:

- `x86_64_generic` builds through the canonical root interface;
- QEMU `q35` reaches user space and the Microkit monitor;
- serial or HPET client work is observed at least three times;
- QEMU is cleaned up as a process group on pass, failure and timeout;
- logs, reports, QEMU version and image hashes are retained; and
- the toolchain doctor verifies `qemu-system-x86_64` and both x86 SDK boards.

### U0 — Microkit 2.3 and seL4 16 baseline

Upgrade the SDK in a separate reviewed change and adapt the pinned sDDF/system
descriptions to the new x86 IOMMU and IRQ contracts.

Exit:

- all F0 and X0 gates pass on Microkit 2.3;
- no release path references the vulnerable 2.2 VT-x configuration;
- DMA-capable systems declare reviewed IOMMU mappings;
- the exact SDK hashes, seL4 version and breaking-change adaptations are
  recorded.

### X1 — Native x86 POSIX core

Port the core POSIX system using PC99 serial and HPET before adding devices.

Exit:

- native x86 libc startup, memory, time and descriptor-core tests pass;
- architecture-independent PID and syscall contracts replace stale stubs;
- debug and release images pass without AArch64 regressions.

### X2 — x86 networking

Add virtio-net PCI, DHCP, DNS and socket coverage with loopback-only host
forwarding.

Exit:

- deterministic DHCP plus client/server tests pass;
- PCI BAR/IRQ assumptions are explicit and tested;
- QEMU processes cannot expose services beyond the declared test interface;
- failures, reconnects, malformed input and queue exhaustion are covered.

### X3 — x86 storage and FileIO

Add virtio-block PCI, a fresh deterministic disk, FAT/FileIO and the repaired
filesystem protocol.

Exit:

- functional FileIO and boundary suites pass from a new disk;
- simultaneous network and block PCI layout is validated;
- every dequeued command receives exactly one completion;
- interrupted tests cannot contaminate the next run.

### X4 — x86 WASM parity

Make WAMR target and LLVM object-format selection architecture-aware.

Exit:

- WAMR builds for x86_64 without the inherited forced `AARCH64` target;
- WASM core, file, client and server suites pass;
- WASI network and filesystem authority is declared and enforced.

### B0 — Bootable developer preview

Produce a GRUB Multiboot2 hybrid BIOS/UEFI live image and validate it under
SeaBIOS and OVMF.

Exit:

- released media boots QEMU through both firmware paths;
- the image reaches a diagnostic console with network and storage tests;
- it is reproducible, checksummed, signed and accompanied by licenses/SBOM;
- live mode performs no undeclared writes.

### H0 — ThinkPad T490 read-only preview

Boot the same lineage from removable media on the selected hardware.

Exit:

- EaglesOS reports CPU, memory, ACPI, PCI and boot information;
- a framebuffer or other safe diagnostic console is usable;
- reboot and failure recovery work reliably;
- the internal disk remains untouched and the run leaves an evidence record.

### C0 — Resource and process core

Implement capability/memory allocation, isolated address spaces, loaders,
process identity, argv/environment, lifecycle, faults, reclaim, naming and
restart supervision.

Exit:

- multiple untrusted programs launch from a manifest;
- each receives only declared authority;
- exit, forced termination and crash reclaim all resources;
- one process can be restarted without rebooting unrelated services;
- the Microkit-slot versus general-root-server checkpoint is decided from the
  prototype evidence.

### C1 — Unix personality and base userland

Add real virtual-memory protection, threads, spawn/exec/wait, signals, pipes,
polling, TTY/PTY, credentials, clocks, VFS semantics, a shell and core tools.

Exit:

- a published syscall/POSIX profile passes conformance and stress tests;
- concurrent isolated users and processes are enforced;
- a native program can be compiled and executed on EaglesOS;
- unsupported semantics return explicit errors rather than false success.

### S0 — Durable system services

Add crash-resilient storage, network/config/time/logging services, CSPRNG,
identity, permissions, secrets, health and supervision.

Exit:

- power-loss and fault-injection recovery preserve system/user data;
- concurrent storage plus DHCP/DNS/TCP/UDP/TLS tests pass;
- two-user isolation and audit tests pass;
- the service fabric survives a 24-hour fault/soak run.

### H1 — Supported T490 hardware profile

Implement ACPI/PCI discovery, APIC/MSI, SMP, IOMMU-safe DMA, NVMe, I219-LM
wired networking, xHCI/HID, display, audio and power services for the selected
machine. Wi-Fi may be a later sub-gate if firmware/driver licensing or
complexity would otherwise block the wired profile.

Exit:

- the T490 boots from installed media to a persistent multi-user console;
- storage, wired networking, keyboard/pointing devices and clean shutdown work;
- DMA isolation, suspend/resume or explicit non-support, thermal and recovery
  behavior are documented and tested.

### D0 — Native desktop

Add a compositor/window server, graphical login and session manager, terminal,
clipboard, fonts, basic toolkit, input routing, audio and accessibility
foundations.

Exit:

- graphical login launches multiple isolated native/WASI applications;
- terminal, editor, network and audio workflows survive logout/login;
- a compositor or application crash does not require a system reboot.

### R0 — Distribution lifecycle

Add signed packages/images, dependency resolution, USB installer, atomic
updates, rollback, rescue, backup/restore, SBOM/provenance and support policy.

Exit:

- a blank test disk can be installed without manual partition surgery;
- interrupted installation/update recovers or rolls back;
- user data survives update and recovery tests;
- release artifacts can be independently reproduced and verified.

### V1 — Linux-replacement release

Define and execute the owner's real daily-workload acceptance matrix.

Exit:

- EaglesOS performs those workloads on the supported T490;
- EaglesOS can build EaglesOS;
- sustained desktop, hardware, storage, network and update tests pass;
- recovery and migration documentation is proven from released media.

## Immediate execution package

Published work:

1. PR #2: initial takeover assessment and planning entry point.
2. PR #3: hardened CI trust boundaries and truthful source checks.
3. PR #4: portable WASI SDK, reproducible toolchain doctor and development
   guide.

Next ordered changes:

1. Update PR #2 with this product plan and ADR.
2. Add X0 as a bounded, artifact-producing x86 boot gate.
3. Upgrade to Microkit 2.3/seL4 16 and rerun all foundation/x86 gates.
4. Fix confirmed filesystem and boundary-safety defects in focused PRs.
5. Add the common AArch64/x86 runtime harness and complete X1 through X4.
6. Produce B0 only after the runtime and safety gates are green.

No installer, VT-x guest, or internal-disk test precedes these gates.

## Release naming

- **x86 Developer Preview:** X0 through X4 are runtime-green in QEMU.
- **Bootable Developer Preview:** B0 hybrid live media is reproducible.
- **T490 Hardware Preview:** H0 boots safely from removable media.
- **EaglesOS Alpha:** C0/C1 provide a usable native multi-process console.
- **EaglesOS Beta:** S0/H1/D0 provide the selected-machine desktop.
- **EaglesOS 1.0:** R0 and the owner's V1 acceptance matrix are complete.

These names communicate evidence. They are not calendar commitments.

## Open architecture decisions

1. Are preallocated Microkit application slots sufficient, or does C0 require a
   general seL4 root server?
2. May supported releases contain an optional Linux compatibility guest, or
   must they contain no Linux code?
3. Which native package/application ABI is stable first: musl/POSIX, WASI, or a
   deliberately paired contract?
4. Which crash-resilient filesystem becomes the root and user-data store?
5. What graphics strategy is credible for Intel UHD 620 without importing an
   oversized trusted driver?
6. Which T490 features are mandatory for the first hardware tier, especially
   Wi-Fi, audio and suspend?
7. Which service and protocol properties become the first user-space formal
   verification targets?

These decisions must be resolved before the milestone they affect. They do not
block X0.
