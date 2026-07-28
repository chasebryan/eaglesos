<!--
     Copyright 2026, Chase Bryan
     SPDX-License-Identifier: CC-BY-SA-4.0
-->

# Initial EaglesOS takeover assessment

Status: historical assessment; product direction superseded on July 28, 2026

Assessment date: July 28, 2026

Assessed revision: `70ebca6` (`main`), based on LionsOS
`4a5656a32574049817f62054832abeae85861ff5`

## Supersession notice

After this initial repository assessment, the product owner selected a native
x86_64 general-purpose operating system with seL4 as the host kernel. That
direction supersedes this document's appliance-only product recommendation,
near-term non-goals, AArch64-first destination, milestone roadmap, first
execution package, release progression, and open product decisions.

The source audit, inherited-risk findings, dependency inventory and safety
analysis below remain useful historical evidence. Current implementation and
release decisions are governed by:

- the [authoritative x86_64 product plan](PRODUCT_PLAN.md); and
- [ADR-0001: x86_64 general-purpose architecture](adr/0001-x86_64-general-purpose-architecture.md).

## Initial executive decision (superseded)

EaglesOS should not try to become a conventional desktop or server operating
system. The inherited project is a compact systems-construction framework that
composes isolated seL4 Microkit protection domains into embedded appliance
images. Its most credible product direction is:

> EaglesOS is a reproducible, modular seL4/Microkit operating-system platform
> and SDK for embedded, IoT, and cyberphysical appliances, shipping supported
> reference systems with evidence-backed security, performance, and
> verification claims.

The immediate next move is **baseline qualification**, not new features and not
a repository-wide rename. We must first make the inherited source build, boot,
run tests, and produce auditable evidence on one canonical virtual target.

The practical acceptance spine will be `qemu_virt_aarch64` with the POSIX,
WASM, and FileIO conformance systems. The Webserver will become the first-run
demonstration. Firewall and Kitty remain showcase systems until their safety,
runtime, and operational dependencies are productized. The standalone VMM is
experimental until it is either repaired or deliberately retired.

## Mission carried forward

The plan preserves the goals stated by LionsOS before the fork:

- target embedded, IoT, and cyberphysical systems;
- remain adaptable through explicit, modular component boundaries;
- make least authority and isolation visible in system composition;
- pursue performance without turning the system into an opaque monolith;
- keep designs small enough to understand and eventually verify; and
- attach security, performance, and formal-verification statements to evidence
  produced from the exact EaglesOS revision being released.

EaglesOS adds the product work the inherited repository does not yet provide:
reproducible builds, supported profiles, executable acceptance tests, a stable
developer experience, release artifacts, update and support policies, and
honest lifecycle documentation.

## Product boundaries

### Intended users and workloads

- Systems engineers building networked embedded appliances on seL4 Microkit.
- Researchers who need explicit protection-domain boundaries and inspectable
  system descriptions.
- Application developers using a constrained native/POSIX, MicroPython, or
  WASM/WASI execution environment.
- Hardware teams integrating a deliberately supported AArch64 board profile.

### Near-term non-goals

- A general-purpose multi-user Unix, desktop OS, or Linux replacement.
- Complete POSIX compatibility.
- A package manager, dynamic service manager, or arbitrary runtime composition.
- Immediate renaming of `include/lions`, `LIONSOS`, wire-format magic values,
  historical assets, or other compatibility-sensitive identifiers.
- Claiming that every board or example named in a Makefile is supported.
- Inheriting upstream security, verification, or benchmark claims without
  reproducing them on EaglesOS.

### Product surfaces

| Surface | Definition | Initial status |
| --- | --- | --- |
| EaglesOS Core | Composition conventions, filesystem protocol, native support libraries, and integration with Microkit/sDDF | Inherited, unstable |
| EaglesOS Runtimes | Native musl/POSIX subset, MicroPython, and WAMR/WASI | Inherited, experimental |
| EaglesOS SDK | Reproducible toolchain, root build/test interface, component templates, documentation, and reports | Not yet present |
| EaglesOS QEMU Profile | Canonical AArch64 virtual target used for every merge and release | Proposed Tier 1 |
| EaglesOS Hardware Profile | One selected board with continuous physical access and hardware-in-loop evidence | Not yet selected |
| Showcase systems | Webserver, Firewall, and Kitty demonstrations | Inherited, not production profiles |

## What is in the repository

The assessed baseline contained 271 tracked paths and eight git submodules.
Before this plan, the EaglesOS-specific change was limited to project identity
and provenance in the root README; the implementation remains the inherited
LionsOS baseline.

| Area | Responsibility |
| --- | --- |
| `include/lions/` | Public filesystem, POSIX, firewall, and framebuffer interfaces |
| `lib/fs/` | Shared filesystem client helpers and server descriptor/memory support |
| `lib/libc/posix/` | musl syscall bridge for memory, I/O, files, sockets, and time |
| `lib/sock/` | lwIP-backed TCP implementation used by native/MicroPython/WASM components |
| `components/fs/` | FAT and NFS filesystem server protection domains |
| `components/micropython/` | MicroPython port with filesystem, network, I2C, framebuffer, and firewall bindings |
| `components/wamr/` | WAMR/WASI protection-domain runtime |
| `examples/` | Seven independent system compositions and applications |
| `ci/` | Per-example build scripts; currently no aggregate runtime gate |
| `flake.nix` | Four-host development shell and pinned SDK/tool downloads |

### Dependency boundary

| Dependency | Role | Source form |
| --- | --- | --- |
| seL4 Microkit 2.2.0 | Kernel-facing SDK, libraries, image tool, and boards | Hashed download in Nix |
| sDDF | Drivers, virtualizers, queues, lwIP integration, board metadata | Pinned submodule |
| libmicrokitco | Cooperative threads used by runtimes and tests | Pinned submodule |
| musllibc | Base C library | Pinned submodule |
| MicroPython | Python runtime | Pinned submodule |
| WAMR | WebAssembly/WASI runtime | Pinned submodule |
| libnfs | NFS client implementation | Pinned submodule |
| libvmm | Virtual-machine support | Pinned submodule |
| Microdot | MicroPython web framework | Pinned submodule |
| FatFs R0.15 | FAT implementation | Vendored in `dep/ff15` |
| sdfgen 0.28.1 | Python system-description generator | Locked Nix input; apt lane pins only the top-level Python package |
| WASI SDK 27 | WASM compiler toolchain | Hashed download in Nix |

Five direct submodules and sdfgen are hosted by AU-TS. That is an independence
risk, but it is not a reason to fork everything immediately. Dependencies
should remain pinned and tracked; an EaglesOS-owned fork is justified only when
an accepted fix, security response, release cadence, or API requirement cannot
be met upstream.

## Current architecture

### Build and composition flow

```text
board definition + DTB + component sources
                    |
                    v
            per-system Makefile
                    |
          +---------+----------+
          |                    |
          v                    v
 component ELF protection   Python sdfgen
       domains             metaprogram
          |                    |
          +---------+----------+
                    v
      static system graph + serialized configs
                    |
        config sections injected into ELFs
                    |
                    v
              Microkit image tool
                    |
                    v
        board-specific image + report file
```

At runtime, Microkit notifications signal work and shared memory carries queue
entries and bulk data. Drivers and virtualizers largely come from sDDF. The
repository supplies filesystem services, runtime ports, the POSIX/socket shim,
firewall functions, and application compositions.

The filesystem protocol is representative: clients and servers exchange fixed
64-byte command/completion records through shared ring buffers and use a
separate shared data area for paths and file contents. System metaprograms map
only the required memory regions and notification channels into each
protection domain.

### Architectural strengths

- Static, reviewable system topology rather than hidden runtime discovery.
- Clear process/protection-domain boundaries and explicit shared resources.
- Separately replaceable drivers, services, runtimes, and applications.
- Multiple application models: native, MicroPython, and WASM/WASI.
- QEMU targets and machine-readable test sentinels already exist.
- Pinned gitlinks and hashed Nix SDK downloads provide a useful reproducibility
  foundation.

### Architectural debt

- No canonical EaglesOS system, root build command, stable SDK, or component
  compatibility contract exists.
- Each example independently repeats board selection, build variables,
  metaprogram conventions, object-section injection, and CI selection.
- Public headers mix protocol, data structure, and large inline implementation
  details.
- Shared-memory protocols have fixed compile-time capacities but no version
  negotiation, compatibility declaration, or systematic saturation behavior.
- Assertions frequently turn bad input or exhausted capacity into a component
  crash rather than a recoverable error.
- There is no maintained threat model, authority map, proof artifact, or
  performance baseline.

## Existing systems and honest support status

The following table describes declarations and current automation. It is not a
support claim.

| System | Purpose | Declared targets | Current CI behavior |
| --- | --- | --- | --- |
| FileIO | MicroPython plus FAT functional tests and benchmark | MaaXBoard, QEMU AArch64 | Debug builds only; no runtime verdict |
| Firewall | Dual-interface ICMP/TCP/UDP router/filter with web management | i.MX8MP IoT Gate, QEMU AArch64 | IoT Gate debug/release builds; Docker runtime suite is not integrated |
| Kitty | NFC point-of-sale showcase with NFS and graphics VM | Odroid C4, QEMU AArch64 | Debug builds only; client currently fails source compilation |
| POSIX test | Native memory, time, file, descriptor, and TCP tests | MaaXBoard, QEMU AArch64 | QEMU debug build; test program is not run |
| WASM test | Similar conformance paths through WAMR/WASI | MaaXBoard, QEMU AArch64 | QEMU debug build; test program is not run |
| Webserver | MicroPython async HTTP server backed by NFS | Odroid C4, MaaXBoard, QEMU AArch64 | Odroid/QEMU debug/release builds; no request test |
| VMM | Linux VM with broad Odroid C4 passthrough | Odroid C4 | Disabled in aggregate CI |

Platform support and system maturity are separate dimensions. A system does not
become supported merely because it has a QEMU build.

Initial platform classification:

| Platform profile | Gate | Initial status |
| --- | --- | --- |
| Core QEMU profile: `qemu_virt_aarch64` plus POSIX, WASM, and FileIO in debug/release | Every merge builds and runs acceptance; every release includes artifacts and evidence | Proposed Tier 1 after M2 |
| QEMU reference application: Webserver | Core QEMU gate plus a deterministic, self-contained HTTP acceptance test | Proposed Tier 1 after M3 |
| Physical AArch64 profile | Continuous hardware access, deployment/recovery automation, runtime and soak evidence | No board selected |
| Other platform combinations | Best-effort build information only | Experimental |

Initial system maturity:

| Maturity | Systems | Meaning |
| --- | --- | --- |
| Conformance spine | POSIX test, WASM test, FileIO | Release-blocking once M2 is complete |
| Reference candidate | Webserver | Must become self-contained before promotion |
| Showcase | Firewall, Kitty | Non-blocking demonstrations until separately promoted |
| Experimental | Standalone VMM | No compatibility or release guarantee |

Odroid C4, MaaXBoard, or i.MX8MP IoT Gate may become the physical profile only
after ownership, lab access, recovery, deployment, runtime, and soak-test
requirements are defined and automated.

## Assessment findings

### Confirmed P0 correctness blockers

These defects were confirmed by direct source inspection. Their system-level
impact still has to be measured in the relevant isolated protection domains.

| Finding | Evidence | Required response |
| --- | --- | --- |
| Filesystem helper allocation walks beyond metadata | `lib/fs/helpers/helpers.c:20-68` lets the request allocator scan 2,044 metadata entries although request IDs/metadata stop at 511, while buffer allocate/free assume 2,044 entries backed by only 511 metadata records | Tie request capacity to the queue; derive buffer capacity from the mapped shared region; make metadata sizes agree and add static/runtime assertions plus exhaustion tests |
| NFS path buffers have reversed dimensions | `components/fs/nfs/op.c:41,143-146` creates 4,096 two-byte rows while callers need two 4,096-byte buffers | Correct layout; test maximum paths and rename isolation |
| NFS lifecycle loses or hangs requests | `components/fs/nfs/op.c:203,568,775` has empty deinitialization, copies the old rename path twice, and allocates the wrong continuation in a callback | Repair callback ownership, in-flight accounting/backpressure, and one-completion-per-command behavior |
| FAT open can overflow its stack path | `components/fs/fat/op.c:132` allocates 256 bytes while `fs_copy_client_path()` accepts up to 4,095 bytes | Use the protocol path limit or reject longer input before copying |
| MicroPython filesystem operations violate buffer ownership/size | `components/micropython/vfs_fs_file.c:46-105,249-304`, `components/micropython/vfs_fs.c:62`, and `components/micropython/modfs_raw.c:111` send blocking/raw-async operations through fixed buffers, copy paths without matching bounds, and include an open-error double free | Bound/chunk every transfer and path, repair cleanup ownership, validate transport/completion status, and test all boundaries/failures |
| I2C and framebuffer bindings do not validate mapped-region/source sizes | `components/micropython/machine_i2c.c:49-103`; `components/micropython/modfb.c:25-77` | Validate lengths, arithmetic, dimensions, and mappings before copy/write |
| Firewall interface check is off by one | `components/micropython/mpfirewallport.c:189-196` permits `interface == num_interfaces` before indexing arrays | Require a strict bound and test malformed descriptors |
| POSIX socket/I/O dispatch can overwrite or call through null operations | `lib/libc/posix/sock.c:350-408` writes accepted peer data without respecting caller `addrlen`; `lib/libc/posix/io.c:21-68` can invoke a missing read/write operation | Validate caller buffers and descriptor operations before the M2 POSIX gate |

### Confirmed test and functional drift

- `examples/kitty/client/kitty.py:92-104` uses `await` in a non-`async`
  function. A read-only Python compilation check fails with `SyntaxError`.
- `lib/libc/posix/posix.c:107-112` returns PID 1 while
  `examples/posix_test/test_core.c:120-122` requires PID 0. Runtime CI would
  already fail this inherited test.
- FAT invalid commands and some NFS/FAT operations can consume a request
  without producing a completion, which hangs blocking clients.
- FAT end-of-directory handling is overwritten by a generic error.
- Filesystem descriptor generation checks accept future generations rather
  than requiring an exact match.
- Firewall subnet-mask construction shifts by 32 for the valid `/0` prefix,
  producing undefined behavior in a default-route case.
- MicroPython VFS contains no-op current-directory/unmount behavior and several
  paths that ignore transport failure before reading completion data.
- The native POSIX layer has known descriptor ownership, socket state, and
  partial syscall-semantics gaps. These must be documented as a supported
  subset rather than presented as full POSIX.

### Security and trust gaps

- `getrandom()` is explicitly implemented with `rand()` and is not suitable
  for secrets (`lib/libc/posix/posix.c:133-159`).
- The Firewall management service exposes route, rule, and ping mutations over
  an unauthenticated HTTP API in the inherited example.
- The Firewall starts with allow rules for ICMP, TCP, and UDP on both
  interfaces. That is a demonstration posture, not a production default.
- WAMR grants the embedded module a `0.0.0.0/0` WASI address pool.
- The ordinary `pull_request` workflow includes a job on a persistent
  self-hosted macOS runner. Repository code must not reach that runner without
  an explicit trusted boundary.
- GitHub Actions use mutable tags, including `@master`; the apt CI lane and
  Kitty/VMM payload downloads do not consistently verify content hashes.
- No `SECURITY.md`, threat model, security-support window, or vulnerability
  response process exists.

### Build, test, and release gaps

- The root README correctly states that no EaglesOS build has been validated.
- At the initial assessment snapshot, none of the eight submodule worktrees was
  populated in this checkout.
- The initial assessment environment had Python and Git but lacked Nix, Make,
  CMake, Clang, QEMU, ShellCheck, actionlint, and REUSE, so a full baseline build
  could not be attempted during that assessment pass.
- `ci/README.md:10-11` explicitly says CI builds examples but has no runtime
  checks. The POSIX and WASM `PASS` sentinels are therefore unused.
- The VMM is commented out of `ci/examples.sh` and has stale build logic and
  documentation.
- The Nix flake exposes only a development shell, not build packages, checks,
  apps, or release outputs.
- No workflow retains images, Microkit reports, serial logs, test results, or
  dependency manifests.
- There are no tags, versions, changelog, source bundle, SBOM, checksum/signing
  process, provenance attestation, support window, or update strategy.

### Documentation, ownership, and identity gaps

- The current README establishes provenance well but does not define a product
  contract or getting-started path.
- `MAINTAINERS.md`, CI labels, `flake.nix`, and much user-facing documentation
  still describe LionsOS and upstream ownership.
- No `CONTRIBUTING.md`, `CODEOWNERS`, architecture guide, component-authoring
  guide, release policy, or upstream-sync policy exists.
- The repository has only the EaglesOS `origin`; no upstream remote or
  divergence-report automation exists.
- `.reuse/dep5` correctly preserves inherited provenance in spirit but contains
  stale paths and has not been validated with REUSE in this environment.

## Delivery principles

1. Make a claim only when a required check emits retained evidence for the
   exact commit and dependency graph.
2. Prefer QEMU for the always-available integration spine; treat physical
   hardware as a separate support tier.
3. Record inherited failures before repairing them so baseline and divergence
   remain understandable.
4. Keep changes small and independently reviewable. Do not mix compatibility
   renames with correctness fixes.
5. Turn repeated example build knowledge into one machine-readable matrix and
   one root developer interface.
6. Fail safely on invalid input and exhausted capacity; assertions remain for
   internal invariants, not routine error handling.
7. Preserve upstream history, SPDX data, and compatibility identifiers unless
   an explicit migration decision says otherwise.
8. Upstream fixes when practical, but never block an EaglesOS safety or release
   gate on upstream response time.

## Roadmap and gates

No milestone is complete because a date elapsed. Each milestone ends only when
its exit criteria are met.

### M0 — Charter and takeover controls

Deliverables:

- Adopt this product definition and non-goals.
- Create `SECURITY.md`, `CONTRIBUTING.md`, and EaglesOS ownership/CODEOWNERS.
- Record an initial QEMU threat model and generated authority map.
- Define signing-key custody, access, rotation, revocation, and incident policy
  before any signed alpha artifact is published.
- Document upstream sync cadence, patch policy, and dependency-fork criteria.
- Record identity categories: external names to change now, compatibility names
  to alias later, and provenance names that must remain unchanged.
- Add architecture decisions for the canonical build path, QEMU reference
  profile, support tiers, and version scheme.

Exit criteria:

- Every area has an EaglesOS owner.
- “Supported,” “experimental,” and “showcase” have testable meanings.
- A contributor can find build, review, security, and upstream policies from
  the root README.

### M1 — Trusted, reproducible inherited baseline

Deliverables:

- Remove ordinary untrusted PR execution from persistent self-hosted runners;
  pin actions and declare least-privilege permissions, timeouts, and
  concurrency.
- Populate every submodule recursively at its recorded gitlink and generate a
  consolidated dependency manifest.
- Make the Nix path canonical and expose build/check outputs rather than only a
  development shell.
- Build the intended QEMU matrix on canonical `x86_64-linux` Nix builders from
  independent fresh clones/build directories, compare SHA-256 artifact
  digests, and retain commands, versions, locks, submodule SHAs, reports, logs,
  hashes, failures, and any diagnosed nondeterminism.
- After dependency materialization, prove that the release source bundle builds
  with networking disabled.
- Lock and hash Python transitives; generate recursively complete SBOM and
  license data for submodules, SDKs, and downloaded payloads; triage known
  vulnerabilities and document reviewed exceptions.
- Verify corresponding-source and notice obligations for distributed Linux,
  Buildroot, GPL, and other third-party payloads.
- Add Python compilation, shell lint, action lint, SPDX/REUSE, C formatting,
  warnings, and static-analysis checks. Ratchet inherited debt with a reviewed
  baseline/allowlist so new regressions fail without derailing qualification.
- Replace `getrandom()` with a defined entropy source or return a clear
  unsupported error; no release profile may silently provide `rand()` as secure
  randomness.
- Record non-gating image size, Microkit memory-report, boot-time, and available
  FileIO/network benchmark baselines so later regressions are visible.
- Record and fix the confirmed source/build blockers in focused changes with
  regression tests.

Exit criteria:

- A new developer can reproduce the same dependency graph and build artifacts
  from the documented root command.
- Every download is content-verified and no release build performs an
  undeclared network fetch.
- Independent clean builds either have identical SHA-256 digests or a reviewed,
  documented nondeterminism blocks release until removed.
- Recursive vulnerability/license review has no untriaged release blocker.
- Known P0 memory-safety blockers have tests and are fixed.
- A baseline evidence bundle is attached to the exact revision.

### M2 — Runtime-green QEMU spine

Deliverables:

- Boot POSIX and WASM systems under QEMU with hard timeouts.
- Require core/file/server/client `PASS` sentinels from both POSIX and WASM
  (four per system, eight total) and fail on `FAILED`, `ERROR`, unexpected
  assertion, timeout, missing marker, or QEMU fault.
- Run FileIO against a deterministic disk image and verify its functional
  result, not just serial output.
- Exercise debug and release configurations where behavior can differ.
- Capture non-gating boot-time, memory-report, FileIO, and network measurements.
- On a non-blocking showcase track, compile/boot Kitty and run the Firewall
  shUnit2 suite only on an ephemeral privileged worker. Failures remain visible
  but do not block the core profile until each showcase is promoted.

Exit criteria:

- Tier 1 QEMU acceptance is required on every merge.
- Runtime logs and machine-readable results are retained.
- Performance trends are retained even before budgets become release gates.
- The implementation/test `getpid()` contradiction and other discovered drift
  are resolved by an explicit API contract.
- Every dequeued filesystem command, including an invalid command, produces
  exactly one completion.

### M3 — Coherent EaglesOS SDK and developer preview

Deliverables:

- One root build/test interface and one machine-readable support matrix drive
  Nix, Make, CI, and documentation.
- Normalize configuration inputs, build directories, artifact names, and
  report formats.
- Publish self-contained quickstart, architecture, component-authoring,
  debugging, and deployment guides.
- Define the native/POSIX subset, MicroPython port surface, WASI policy, and
  protocol/API compatibility rules.
- Promote Webserver into a maintained quickstart reference application by
  automatically provisioning deterministic local NFS/export/site data. If that
  cannot be made one-command and self-contained, choose a simpler reference
  application rather than documenting hidden infrastructure.
- Rebrand external surfaces while retaining tested compatibility aliases for
  internal LionsOS identifiers.
- Produce versioned source bundles and QEMU images with licenses, SBOM,
  checksums, signatures, and provenance.

Exit criteria for `v0.1.0-alpha`:

- A clean supported host builds and runs the QEMU profile from the quickstart.
- All release-blocking M2 core-profile tests pass from released artifacts;
  showcase results are published separately.
- Recursive SBOM, vulnerability triage, license/corresponding-source checks, the
  QEMU threat model, and signing-key policy are complete.
- Known limitations and support boundaries are published.
- The release can be reproduced and verified without relying on mutable URLs.

### M4 — One production-quality hardware profile

Deliverables:

- Select one AArch64 board based on actual ownership and lab access.
- Automate hardware provisioning, image deployment, serial control, recovery,
  runtime acceptance, reboot, and soak testing.
- Define and measure boot-time, memory, throughput, latency, and reliability
  budgets.
- Extend the QEMU threat model and authority map for physical peripherals,
  deployment, and recovery; harden update/recovery, management interfaces, and
  WASI network authority.
- Test fault containment by crashing or starving individual protection domains.

Exit criteria:

- Hardware-in-loop acceptance runs on every release candidate and on a regular
  schedule.
- Recovery from an interrupted or bad deployment is documented and tested.
- Published security/performance claims link to revision-specific evidence.

### M5 — Verification and controlled expansion

Deliverables:

- Specify narrow, tractable properties first: ring-queue invariants,
  descriptor-generation safety, one-completion-per-dequeued-command,
  generated-memory bounds, and protection-domain authority constraints.
- Add executable model/property tests before committing to full formal proofs.
- Choose proof targets based on risk and stability, then preserve traceability
  from specification to implementation and release revision.
- Promote additional boards and showcase systems only when they meet the same
  runtime, security, performance, and release bar.

Exit criteria:

- Verification claims name the property, assumptions, tool/version, source
  revision, and reproducible evidence.
- No new target expands the Tier 1 contract without an owner and automated
  acceptance path.

## First execution package

Work should begin with the following small, ordered changes.

### PR 1 — Establish a trusted and truthful gate

- Restrict the persistent self-hosted job to trusted/manual execution or move
  it to an ephemeral runner.
- Pin actions, set explicit permissions, add timeouts/concurrency, and retain
  logs.
- Add a read-only Python source compilation check. First retain the Kitty
  failure as baseline evidence, then repair it in a separate commit and make
  the check required; an expected-failure entry may bridge those commits only.
- Add shell/action/license checks where the canonical environment can run them.
- Rename misleading CI labels that say examples are run when they are only
  built.

### PR 2 — Capture the inherited build baseline

- Materialize pinned submodules recursively without `--remote`.
- Add a root bootstrap/build command backed by Nix.
- Generate the dependency/toolchain manifest and baseline evidence directory.
- Attempt each QEMU build independently and record every success and failure.
- Do not hide inherited failures with a broad fix commit.

### PR 3 series — Stabilize memory and request safety

Land each item as a separate, focused safety PR:

- **3A — Client allocator contract:** fix request/buffer metadata bounds and
  shared-region sizing with explicit queue/request and mapped-buffer
  capacities; add static/runtime assertions, full exhaustion, and invalid-free
  tests.
- **3B — Filesystem server lifecycle:** repair NFS path dimensions, rename and
  callback ownership, deinitialization, continuation exhaustion/in-flight
  accounting, FAT path bounds, invalid-command completions, end-of-directory,
  unsupported-ioctl errors, exact descriptor-generation validation, and
  completion-queue saturation. Require exactly one completion for every
  dequeued command, including invalid commands.
- **3C — MicroPython filesystem safety:** bound or chunk blocking and raw-async
  transfers and path copies, remove the open-error double free, validate all
  transport/completion results, and test cleanup ownership.
- **3D — Component input bounds:** validate I2C mapped-region lengths and
  zero-length write-read, validate framebuffer source/destination arithmetic,
  repair the firewall interface off-by-one and `/0` mask behavior, and add
  malformed-input tests at protection-domain boundaries.
- **3E — POSIX caller safety:** respect `accept()` caller buffer lengths, reject
  missing descriptor read/write operations safely, and add negative tests
  before the POSIX runtime suite becomes release-blocking.

Each PR must add its boundary, exhaustion, failure-injection, or ownership
regression test before the next subsystem is changed.

### PR 4 — Execute the conformance spine

- Build a QEMU harness with hard timeouts and serial-log parsing.
- Run POSIX and WASM core/file/server/client suites.
- Resolve the PID contract and any other runtime-only drift revealed by the
  harness.
- Add deterministic FileIO runtime verification.

### PR 5 — Productize the first reference experience

- Make Webserver a self-provisioning, one-command quickstart with deterministic
  local NFS/site data and a runtime health/content check; choose a simpler
  reference if that dependency cannot be hidden reliably.
- Centralize the QEMU support matrix and artifact layout.
- Produce the first release-candidate evidence bundle.

Firewall/Kitty showcase promotion, VMM repair, physical-board promotion, broad
identity migration, and new features should not delay this spine.

## Verification strategy

| Layer | Required checks |
| --- | --- |
| Source | Python compile, shell/action lint, format, warnings, static analysis, SPDX/REUSE |
| Host unit | Queue arithmetic, allocation exhaustion, path/buffer bounds, descriptor generations, routing/filter/checksum logic |
| QEMU component | POSIX and WASM core/file/TCP suites with machine-readable verdicts |
| QEMU core system | Release-blocking FileIO disk behavior; self-contained Webserver request after M3 |
| QEMU showcase | Non-blocking Firewall routing/filter results and Kitty compile/boot sentinel until promotion |
| Hardware | Provision, boot, peripheral/network/storage behavior, reboot/recovery, soak |
| Non-functional | Deterministic builds; early boot/memory/performance baselines; later budgets, fault containment, fuzz/error injection |
| Verification | Protocol invariants, generated mapping/authority checks, property tests, then selected proofs |

Any release-blocking test must have a timeout, a positive success condition, a
negative failure condition, retained diagnostics, and a documented owner.

## Release contract

Every EaglesOS release must identify:

- EaglesOS version and exact Git commit;
- upstream LionsOS baseline and divergence summary;
- recursive dependency revisions and toolchain versions;
- supported host and target profiles;
- source bundle including submodule content or a verifiable materialization
  mechanism;
- build commands, configuration, Microkit reports, and test results;
- artifact hashes, SBOM, license/notice bundle, signature, and provenance;
- known limitations, security support window, and upgrade/recovery guidance;
- exact evidence for every security, performance, or verification claim.

Suggested version progression:

- `v0.1.0-alpha`: reproducible, runtime-green QEMU SDK preview with the
  self-contained quickstart and documented component contracts.
- `v0.2.0-beta`: one hardware profile with deployment, recovery, threat-model,
  and performance evidence.
- `v0.3.0-rc`: selected verification evidence and the complete release process
  proven across repeated candidates.
- `v1.0.0`: stable supported profiles, compatibility policy, and demonstrated
  maintenance/recovery capability.

Versions are readiness markers, not calendar promises.

## Upstream and identity policy

- Add the LionsOS repository as a documented read-only upstream remote.
- Review upstream changes on a regular cadence and before each release.
- Merge or cherry-pick intentionally; record provenance and resolve each
  conflict in a dedicated upstream-sync change.
- Generate a release divergence report covering commits, dependency gitlinks,
  carried patches, API changes, and evidence invalidated by divergence.
- Submit generally useful fixes upstream when practical while keeping EaglesOS
  progress independent of upstream response time.
- Change names at the project boundary first. Migrate programmatic identifiers
  only with aliases, deprecation windows, and runtime/build tests.
- Never rewrite inherited copyright, SPDX, authorship, historical artifact
  names, or Git history to simulate original EaglesOS authorship.

## Open decisions

These decisions do not block M1 unless noted:

1. Which physical board can EaglesOS continuously own and test?
2. Is the standalone VMM repaired, replaced by the Kitty-integrated path, or
   retired?
3. Is the long-term application contract MicroPython-first, WASM-first, or an
   equally supported pair?
4. Which POSIX calls and semantics are contractual for the first stable SDK?
5. What update and rollback mechanism is appropriate for the selected hardware?
6. Which AU-TS dependencies need EaglesOS mirrors or forks for continuity?
7. Which formal property is small, valuable, and stable enough to become the
   first proof target?

## Assessment record and limitations

Completed read-only checks:

- repository, history, branch, remote, and file inventory;
- architecture and system-composition inspection;
- submodule/gitlink and declared dependency inventory;
- build, CI, board, test, governance, licensing, and release-path inspection;
- focused implementation review across filesystem, POSIX/socket, MicroPython,
  WAMR, Firewall, Kitty, and VMM paths;
- `git fsck --no-dangling`, `git diff --check`, Bash syntax, and POSIX shell
  syntax, all successful;
- compilation of all 40 non-submodule Python files, with one confirmed failure
  in Kitty.

During the initial assessment pass, a full build, QEMU boot, runtime suite,
REUSE audit, and recursive dependency source review were not possible because
the submodule worktrees and declared toolchain were absent. M1 exists to close
that evidence gap. Findings in external dependencies are therefore out of scope
for this assessment and must be added to the baseline review after
materialization.
