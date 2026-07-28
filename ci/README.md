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

## Runtime status

EaglesOS CI does not yet boot the generated images or perform runtime checks.
Runtime acceptance requires a separate QEMU or hardware harness with timeouts,
positive pass conditions, failure detection, and retained logs.
