<!--
    SPDX-FileCopyrightText: 2026 Chase Bryan
    SPDX-License-Identifier: CC-BY-SA-4.0
-->

# EaglesOS development environment

EaglesOS uses the root Nix flake as the authoritative developer and build
toolchain. The Git tree pins source dependencies as submodule commits;
`flake.lock` pins the Nix inputs; and fixed-output hashes in `flake.nix` pin the
Microkit and WASI SDK archives. A successful toolchain check establishes that
those inputs are materialized and executable. It does not establish that an
EaglesOS image boots or passes runtime tests.

## Validated bootstrap scope

The initial bootstrap was exercised on Linux x86-64 with Nix 2.28.5. The same
flake declares development shells for Linux x86-64, Linux AArch64, macOS
x86-64, and macOS AArch64, but declaring an output is not evidence that every
host has passed the EaglesOS build and runtime gates.

At the current flake and lock revision, the Linux x86-64 shell resolves these
principal tools:

| Tool | Resolved version |
| --- | --- |
| Microkit SDK | 2.2.0 |
| WASI SDK | 27.0 (LLVM 20.1.8) |
| Clang/LLVM build toolchain | 18.1.8 |
| QEMU | 9.2.4 |
| Python | 3.12.11 |
| sdfgen | 0.28.1 |
| CMake | 3.31.6 |
| GNU Make | 4.4.1 |

These versions describe the current `flake.lock`, not an independent list of
packages to install. Update this table and the toolchain doctor whenever the
lock or fixed-output SDK versions change.

## Host prerequisites

Use one of these two bootstrap paths:

1. Git plus a Nix installation with the `nix-command` and `flakes` features.
2. Git plus Podman, using the immutable diagnostic container below.

The first materialization needs network access to the Git remotes, Nix cache or
source endpoints, and the fixed SDK release archives. Reserve several GiB for
the recursive submodules, Nix store paths, build trees, and generated images.
QEMU's software emulation does not require KVM, although hardware acceleration
may be used by later host-specific workflows.

Do not assemble an equivalent host toolchain from whichever compiler, QEMU, or
Python packages happen to be installed. That can be useful for comparison, as
the apt-based CI build is, but it is not the reproducible reference path.

## Materialize the source

Clone all direct and nested submodules at the gitlink revisions recorded by the
selected EaglesOS commit:

```sh
git clone --recurse-submodules https://github.com/chasebryan/eaglesos
cd eaglesos
git submodule sync --recursive
git submodule update --init --recursive --jobs 8
```

The current repository has eight direct submodules and additional nested
submodules. Some inherited Makefiles initialize only the subset needed by one
example; do not treat that as a complete checkout. A leading `-`, `+`, or `U`
from `git submodule status --recursive` means that at least one dependency is
missing, checked out at a different commit, or conflicted.

## Verify the exact shell

Run the doctor through the clean Nix environment:

```sh
nix --extra-experimental-features 'nix-command flakes' \
  develop --ignore-environment \
  -c python3 ci/toolchain_doctor.py --verbose
```

The doctor exits nonzero unless all of the following hold:

- the root worktree is clean and its exact Git revision can be recorded;
- the direct flake inputs have immutable revisions and NAR hashes;
- every direct and nested submodule matches its recorded gitlink and has a clean
  worktree;
- build commands resolve from the Nix store, not an ambient host `PATH`;
- Microkit 2.2.0 contains the QEMU AArch64, generic x86_64, and x86_64 VT-x
  debug boards, `sel4.elf` and `sel4_32.elf` for both x86 boards, and its tool
  runs;
- WASI SDK 27.0's compiler runs, matches its metadata, and compiles and links a
  small WebAssembly program; and
- the pinned Python environment imports sdfgen 0.28.1.

The output is line-oriented (`TOOLCHAIN|STATUS|CHECK|DETAIL`) so it can be saved
as build evidence and parsed without installing another package. Without
`--verbose`, the doctor summarizes recursive submodules and flake inputs instead
of printing every revision.

During an intentional local edit, `--allow-dirty` permits the root worktree and
labels the result as unsuitable for release evidence. It never relaxes the
locked-input, submodule, tool, SDK, or smoke-compile checks.

## Immutable Podman fallback

The Linux x86-64 bootstrap was also exercised with this image:

```text
docker.io/nixos/nix@sha256:005629f814b9c13543fc3a66c7b3d81704757e15e5088491a02f7afcbd4df9b5
```

From the repository root, run the same check without installing Nix on the
host:

```sh
podman run --rm --security-opt label=disable \
  --volume "$PWD:/workspace" --workdir /workspace \
  docker.io/nixos/nix@sha256:005629f814b9c13543fc3a66c7b3d81704757e15e5088491a02f7afcbd4df9b5 \
  nix --extra-experimental-features 'nix-command flakes' \
  develop --ignore-environment \
  -c python3 ci/toolchain_doctor.py --verbose
```

The digest fixes the container contents for this reference platform. The flake
still controls the EaglesOS compiler, emulator, SDKs, Python packages, and build
utilities. Rootless Podman and SELinux installations may use different storage
locations, but those locations are outside the EaglesOS dependency identity.

## Build versus runtime evidence

After the doctor passes, reproduce the image-build matrix described in
[`ci/README.md`](../ci/README.md). Image construction by itself is not runtime
evidence.

The first runtime gate is the non-VT-x x86_64 QEMU boot probe:

```sh
nix --extra-experimental-features 'nix-command flakes' \
  develop --ignore-environment \
  -c python3 ci/run_x86_boot.py
```

It builds the pinned sDDF HPET timer system for `x86_64_generic`, starts QEMU
`q35` under TCG, and passes only after observing seL4 and Microkit startup plus
three timer deliveries. Raw and normalized logs, the Microkit report, QEMU
identity, marker results, timings, and artifact hashes form the retained
evidence. See [`ci/README.md`](../ci/README.md) for explicit paths and exit
codes.

This gate deliberately does not execute `x86_64_generic_vtx`. Microkit 2.2.0
contains that board package, so the doctor inventories it, but EaglesOS must
not enable VT-x or a 64-bit guest until the planned Microkit 2.3/seL4 16
upgrade and requalification are complete. Do not label a successful `make`
invocation, this narrow timer gate, or an inherited upstream result as broader
runtime or hardware support.

## Dependency boundaries

The reproducible reference includes:

- the selected EaglesOS commit and every direct or nested gitlink;
- every locked Nix input, including the exact Nixpkgs, sdfgen, and Zig-overlay
  source revisions;
- the per-platform Microkit and WASI archives verified by hashes in `flake.nix`;
  and
- the resulting Nix store closures.

It does not pin the host kernel, firmware, CPU, filesystem, Git implementation,
Nix engine, or container runtime. Record those separately whenever a failure
could depend on the host. The immutable Podman image narrows that ambient set
for Linux x86-64 investigations but does not replace runtime evidence on a
supported EaglesOS target.
