<!--
     Copyright 2024, UNSW
     Copyright 2026, Chase Bryan
     SPDX-License-Identifier: CC-BY-SA-4.0
-->

# Continuous integration for EaglesOS

Materialize and verify the pinned developer toolchain before running these
commands; see the [development environment guide](../docs/DEVELOPMENT.md).

## Source checks

Source-check jobs validate repository source and workflow files without booting
an EaglesOS system. The pinned Nix package containing the CI linters can be
materialized with:

```sh
nix build .#ci-tools
```

The package provides `actionlint`, `shellcheck`, and `reuse` from the Nixpkgs
revision recorded in `flake.lock`.

## Example image builds

The example jobs compile system images for the configured boards. A successful
job means that the image was built; it does not mean that the image was booted
or that its runtime behavior was tested.

You can run the CI example script with:

```sh
./ci/examples.sh /absolute/path/to/eaglesos /absolute/path/to/microkit/sdk
```

Both arguments must be absolute paths. When using the repository's Nix
development shell, run the same image builds with:

```sh
nix develop --ignore-environment -c bash -c \
  './ci/examples.sh "$PWD" "$MICROKIT_SDK"'
```

## Native x86_64 boot gate

The X0 gate builds the pinned sDDF timer system for Microkit's non-VT-x
`x86_64_generic` board and boots it on QEMU `q35` under TCG. It requires seL4
user-space entry, CapDL thread startup, the Microkit monitor, the timer client,
and at least three HPET timeout notifications. The harness has bounded build
and runtime deadlines, checks explicit failure markers, and terminates the
whole child process group on pass, failure, interruption, or timeout.

Run the gate from the canonical Nix environment:

```sh
nix --extra-experimental-features 'nix-command flakes' \
  develop --ignore-environment \
  -c python3 ci/run_x86_boot.py
```

With no path arguments, the harness creates and retains a uniquely named build
directory under `/tmp` in the environment running the harness. For CI or a
deliberate local evidence location, pass new or empty directories explicitly:

```sh
nix --extra-experimental-features 'nix-command flakes' \
  develop --ignore-environment \
  -c python3 ci/run_x86_boot.py \
  --build-dir /tmp/eaglesos-x86-build \
  --log-dir /tmp/eaglesos-x86-evidence
```

The evidence directory contains raw and line-normalized build/runtime logs,
the Microkit report, and a machine-readable record of the commands, QEMU
version, observed markers, result, timings, and artifact hashes. Exit status
`0` means every positive condition was observed, `1` means a build or runtime
failure, `2` means invalid configuration, and `124` means a bounded build or
runtime timeout.

X0 is evidence for the pinned QEMU timer path only. It is not a top-level
EaglesOS product image and does not establish networking, storage, VT-x,
installer, desktop, or physical-PC support. The AArch64 example systems remain
build-only until their separate runtime gates land.
