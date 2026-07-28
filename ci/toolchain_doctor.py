#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Chase Bryan
# SPDX-License-Identifier: BSD-2-Clause

"""Verify that the EaglesOS source and pinned development toolchain are usable."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


EXPECTED_MICROKIT_VERSION = "2.2.0"
EXPECTED_SDFGEN_VERSION = "0.28.1"
EXPECTED_WASI_VERSION = "27.0"
LOCKED_FLAKE_INPUTS = ("nixpkgs", "sdfgen", "zig-overlay")

REQUIRED_COMMANDS = (
    "bash",
    "clang",
    "cmake",
    "curl",
    "dtc",
    "gcc",
    "gdisk",
    "git",
    "ld.lld",
    "llvm-ar",
    "llvm-objcopy",
    "llvm-ranlib",
    "llvm-size",
    "make",
    "mkfs.fat",
    "perl",
    "python3",
    "qemu-system-aarch64",
    "qemu-system-x86_64",
    "shasum",
    "unzip",
    "which",
)

VERSION_PROBES = {
    "bash": ("--version",),
    "clang": ("--version",),
    "cmake": ("--version",),
    "dtc": ("--version",),
    "gcc": ("--version",),
    "gdisk": ("--version",),
    "git": ("--version",),
    "ld.lld": ("--version",),
    "make": ("--version",),
    "python3": ("--version",),
    "qemu-system-aarch64": ("--version",),
    "qemu-system-x86_64": ("--version",),
}


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str


class Report:
    def __init__(self) -> None:
        self.checks: list[Check] = []

    def add(self, name: str, passed: bool, detail: str) -> None:
        self.checks.append(Check(name, passed, one_line(detail)))

    def print(self) -> None:
        for check in self.checks:
            status = "PASS" if check.passed else "FAIL"
            print(f"TOOLCHAIN|{status}|{check.name}|{check.detail}")

        failures = sum(not check.passed for check in self.checks)
        status = "PASS" if failures == 0 else "FAIL"
        print(
            f"TOOLCHAIN|{status}|summary|"
            f"checks={len(self.checks)} failures={failures}"
        )

    @property
    def successful(self) -> bool:
        return all(check.passed for check in self.checks)


def one_line(value: str) -> str:
    return " ".join(value.strip().splitlines())


def run(
    command: list[str], *, cwd: Path | None = None, timeout: int = 30
) -> tuple[int | None, str, str]:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return None, "", f"{type(error).__name__}: {error}"

    # Preserve the leading status character emitted by `git submodule status`.
    output = result.stdout.rstrip() or result.stderr.rstrip()
    error = result.stderr.rstrip() if result.returncode != 0 else ""
    return result.returncode, output, error


def first_line(value: str) -> str:
    return next((line.strip() for line in value.splitlines() if line.strip()), "")


def is_below(path: Path, directory: Path) -> bool:
    try:
        path.resolve().relative_to(directory.resolve())
    except (OSError, ValueError):
        return False
    return True


def check_nix_shell(report: Report) -> Path | None:
    in_nix_shell = os.environ.get("IN_NIX_SHELL", "")
    store_value = os.environ.get("NIX_STORE", "")
    if not in_nix_shell or not store_value:
        report.add(
            "nix-shell",
            False,
            "run with: nix develop --ignore-environment -c python3 "
            "ci/toolchain_doctor.py",
        )
        return None

    store = Path(store_value)
    report.add(
        "nix-shell",
        store.is_dir(),
        f"IN_NIX_SHELL={in_nix_shell} NIX_STORE={store}",
    )
    return store


def check_flake_lock(repository: Path, report: Report, verbose: bool) -> None:
    lock_path = repository / "flake.lock"
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        nodes = lock["nodes"]
        root = nodes[lock["root"]]
        inputs = root["inputs"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        report.add("flake-lock", False, f"cannot parse flake.lock: {error}")
        return

    identities: list[str] = []
    errors: list[str] = []
    for input_name in LOCKED_FLAKE_INPUTS:
        node_name = inputs.get(input_name)
        if not isinstance(node_name, str):
            errors.append(f"{input_name} has no direct locked node")
            continue

        locked = nodes.get(node_name, {}).get("locked", {})
        revision = locked.get("rev")
        nar_hash = locked.get("narHash")
        if not isinstance(revision, str) or not isinstance(nar_hash, str):
            errors.append(f"{input_name} lacks rev or narHash")
            continue

        repository_name = "/".join(
            value
            for value in (locked.get("owner"), locked.get("repo"))
            if isinstance(value, str)
        )
        identity = f"{input_name}={repository_name}@{revision} ({nar_hash})"
        identities.append(identity)
        if verbose:
            print(f"TOOLCHAIN|INFO|flake-input:{input_name}|{identity}")

    detail = "; ".join(errors or identities)
    report.add("flake-lock", not errors, detail)


def check_source(repository: Path, report: Report, allow_dirty: bool) -> None:
    revision_code, revision, revision_error = run(
        ["git", "rev-parse", "HEAD"], cwd=repository
    )
    if revision_code != 0:
        report.add(
            "source-revision",
            False,
            revision_error or revision or "cannot resolve HEAD",
        )
        return

    status_code, status, status_error = run(
        [
            "git",
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--ignore-submodules=all",
        ],
        cwd=repository,
        timeout=120,
    )
    if status_code != 0:
        report.add("source-revision", False, status_error or status)
        return

    changes = status.splitlines()
    clean = not changes
    detail = f"revision={revision} worktree={'clean' if clean else 'dirty'}"
    if changes:
        detail += f" changes={len(changes)}"
    if changes and allow_dirty:
        detail += " (allowed for development; not release evidence)"
    report.add("source-revision", clean or allow_dirty, detail)


def parse_submodule_line(line: str) -> tuple[str, str, str]:
    state = line[0]
    fields = line[1:].strip().split(maxsplit=2)
    revision = fields[0] if fields else "unknown"
    path = fields[1] if len(fields) > 1 else "unknown"
    return state, revision, path


def check_submodules(repository: Path, report: Report, verbose: bool) -> None:
    modules_path = repository / ".gitmodules"
    try:
        direct_count = len(
            re.findall(
                r"^\s*path\s*=\s*.+$",
                modules_path.read_text(encoding="utf-8"),
                flags=re.MULTILINE,
            )
        )
    except OSError as error:
        report.add("submodules", False, f"cannot read .gitmodules: {error}")
        return

    returncode, output, error = run(
        ["git", "submodule", "status", "--recursive"], cwd=repository, timeout=120
    )
    if returncode != 0:
        report.add("submodules", False, error or output or "git command failed")
        return

    lines = [line for line in output.splitlines() if line]
    failures = [parse_submodule_line(line) for line in lines if line[0] != " "]
    if verbose:
        for line in lines:
            state, revision, path = parse_submodule_line(line)
            label = {" ": "recorded", "-": "missing", "+": "mismatch", "U": "conflict"}.get(
                state, "unknown"
            )
            print(f"TOOLCHAIN|INFO|submodule:{path}|{revision} state={label}")

    dirty: list[str] = []
    for line in lines:
        state, _revision, path = parse_submodule_line(line)
        if state != " ":
            continue
        status_code, status_output, status_error = run(
            [
                "git",
                "-C",
                path,
                "status",
                "--porcelain",
                "--untracked-files=all",
                "--ignore-submodules=all",
            ],
            cwd=repository,
        )
        if status_code != 0:
            dirty.append(f"{path} (status failed: {status_error or status_output})")
        elif status_output:
            dirty.append(f"{path} (dirty worktree)")

    if failures:
        descriptions = ", ".join(
            f"{path} ({'missing' if state == '-' else 'not at recorded commit'})"
            for state, _revision, path in failures
        )
        report.add("submodules", False, descriptions)
    elif dirty:
        report.add("submodules", False, ", ".join(dirty))
    else:
        report.add(
            "submodules",
            bool(lines) and direct_count > 0,
            f"direct={direct_count} recursive={len(lines)}; all at recorded commits",
        )


def check_commands(report: Report, nix_store: Path | None) -> None:
    for command_name in REQUIRED_COMMANDS:
        executable = shutil.which(command_name)
        if executable is None:
            report.add(f"command:{command_name}", False, "not found on PATH")
            continue

        executable_path = Path(executable)
        if nix_store is not None and not is_below(executable_path, nix_store):
            report.add(
                f"command:{command_name}",
                False,
                f"{executable_path} is not provided by {nix_store}",
            )
            continue

        detail = str(executable_path)
        arguments = VERSION_PROBES.get(command_name)
        if arguments is not None:
            returncode, output, error = run([executable, *arguments])
            if returncode != 0:
                report.add(
                    f"command:{command_name}",
                    False,
                    error or output or f"version probe exited {returncode}",
                )
                continue
            detail = f"{detail}; {first_line(output)}"

        report.add(f"command:{command_name}", True, detail)


def read_sdk_version(path: Path) -> tuple[str | None, str | None]:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError as error:
        return None, str(error)
    return text, None


def check_sdk_path(
    name: str, value: str, report: Report, nix_store: Path | None
) -> Path | None:
    if not value:
        variable = name.upper().replace("-", "_")
        report.add(name, False, f"{variable} is not set")
        return None

    path = Path(value)
    if not path.is_dir():
        report.add(name, False, f"{path} is not a directory")
        return None
    if nix_store is not None and not is_below(path, nix_store):
        report.add(name, False, f"{path} is not provided by {nix_store}")
        return None
    return path


def check_microkit(report: Report, nix_store: Path | None) -> None:
    sdk = check_sdk_path(
        "microkit-sdk", os.environ.get("MICROKIT_SDK", ""), report, nix_store
    )
    if sdk is None:
        return

    version, error = read_sdk_version(sdk / "VERSION")
    version_ok = error is None and version == EXPECTED_MICROKIT_VERSION
    report.add(
        "microkit-version",
        version_ok,
        error or f"expected={EXPECTED_MICROKIT_VERSION} actual={version}",
    )

    boards = {
        "qemu_virt_aarch64": sdk / "board" / "qemu_virt_aarch64" / "debug",
        "x86_64_generic": sdk / "board" / "x86_64_generic" / "debug",
        "x86_64_generic_vtx": sdk / "board" / "x86_64_generic_vtx" / "debug",
    }
    for board_name, board in boards.items():
        report.add(
            f"microkit-board:{board_name}",
            board.is_dir(),
            str(board),
        )

    x86_kernel_files = [
        board / "elf" / kernel
        for board_name, board in boards.items()
        if board_name.startswith("x86_64_")
        for kernel in ("sel4.elf", "sel4_32.elf")
    ]
    missing_x86_kernels = [path for path in x86_kernel_files if not path.is_file()]
    report.add(
        "microkit-x86-kernels",
        not missing_x86_kernels,
        (
            "both 64-bit kernels and 32-bit Multiboot-compatible kernels "
            "are present for generic and VT-x boards; VT-x is inventory-only "
            "until the Microkit 2.3/seL4 16 upgrade"
            if not missing_x86_kernels
            else "missing: " + ", ".join(str(path) for path in missing_x86_kernels)
        ),
    )

    executable = sdk / "bin" / "microkit"
    returncode, output, command_error = run([str(executable), "--help"])
    report.add(
        "microkit-executable",
        returncode == 0,
        str(executable)
        if returncode == 0
        else command_error or output or f"exited {returncode}",
    )


def parse_wasi_metadata(value: str) -> dict[str, str]:
    metadata = {"version": first_line(value)}
    for line in value.splitlines()[1:]:
        key, separator, item = line.partition(":")
        if separator:
            metadata[key.strip()] = item.strip()
    return metadata


def check_wasi_compile(clang: Path) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="eaglesos-toolchain-") as directory:
        work = Path(directory)
        source = work / "doctor.c"
        output = work / "doctor.wasm"
        source.write_text(
            "#include <stdint.h>\n"
            "int main(void) { return (int)sizeof(uint32_t) - 4; }\n",
            encoding="utf-8",
        )
        returncode, command_output, error = run(
            [str(clang), str(source), "-o", str(output)], timeout=60
        )
        if returncode != 0:
            return False, error or command_output or f"clang exited {returncode}"
        try:
            header = output.read_bytes()[:4]
        except OSError as read_error:
            return False, str(read_error)
        if header != b"\x00asm":
            return False, f"unexpected output header {header!r}"
        return True, "compiled and linked a WASI program with a WebAssembly header"


def check_wasi(report: Report, nix_store: Path | None) -> None:
    sdk = check_sdk_path(
        "wasi-sdk", os.environ.get("WASI_SDK", ""), report, nix_store
    )
    if sdk is None:
        return

    value, error = read_sdk_version(sdk / "VERSION")
    metadata = parse_wasi_metadata(value or "")
    version_ok = error is None and metadata.get("version") == EXPECTED_WASI_VERSION
    report.add(
        "wasi-version",
        version_ok,
        error
        or (
            f"expected={EXPECTED_WASI_VERSION} actual={metadata.get('version')} "
            f"llvm={metadata.get('llvm-version', 'unknown')}"
        ),
    )

    sysroot = sdk / "share" / "wasi-sysroot"
    report.add("wasi-sysroot", sysroot.is_dir(), str(sysroot))

    clang = sdk / "bin" / "clang"
    returncode, output, command_error = run([str(clang), "--version"])
    llvm_version = metadata.get("llvm-version")
    version_matches = (
        returncode == 0
        and llvm_version is not None
        and f"clang version {llvm_version}" in output
    )
    report.add(
        "wasi-clang",
        version_matches,
        f"{clang}; {first_line(output)}"
        if returncode == 0
        else command_error or output or f"exited {returncode}",
    )

    if returncode == 0:
        compiled, detail = check_wasi_compile(clang)
        report.add("wasi-smoke-compile", compiled, detail)


def check_sdfgen(report: Report) -> None:
    try:
        version = importlib.metadata.version("sdfgen")
    except importlib.metadata.PackageNotFoundError:
        report.add("sdfgen", False, "Python distribution is not installed")
        return
    report.add(
        "sdfgen",
        version == EXPECTED_SDFGEN_VERSION,
        f"expected={EXPECTED_SDFGEN_VERSION} actual={version}",
    )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print every locked flake input and recursive submodule revision",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="permit an intentionally modified root worktree (not release evidence)",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    repository = Path(__file__).resolve().parents[1]
    report = Report()

    nix_store = check_nix_shell(report)
    check_source(repository, report, arguments.allow_dirty)
    check_flake_lock(repository, report, arguments.verbose)
    check_submodules(repository, report, arguments.verbose)
    check_commands(report, nix_store)
    check_microkit(report, nix_store)
    check_wasi(report, nix_store)
    check_sdfgen(report)

    report.print()
    return 0 if report.successful else 1


if __name__ == "__main__":
    sys.exit(main())
