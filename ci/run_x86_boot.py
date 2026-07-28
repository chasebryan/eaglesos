#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Chase Bryan
# SPDX-License-Identifier: BSD-2-Clause

"""Build and runtime-test the pinned x86_64 seL4/Microkit timer system."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import IntEnum
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from typing import Callable


BOARD = "x86_64_generic"
CONFIG = "debug"
TIMER_EVENTS_REQUIRED = 3
PROCESS_STOP_GRACE_SECONDS = 5.0

MILESTONES = {
    "sel4": b"Booting all finished, dropped to user space",
    "userspace": b"INFO  [sel4_capdl_initializer::initialize] Starting threads",
    "microkit": b"MON|INFO: Microkit Monitor started!",
    "client": b"CLIENT|INFO: starting",
}
TIMER_EVENT = b"CLIENT|INFO: Got a timeout!"
FAILURE_MARKERS = (
    b"Kernel panic",
    b"Assertion failed",
    b"|ERROR:",
    b"qemu-system-x86_64: could not",
    b"qemu-system-x86_64: failed",
)

ANSI_ESCAPE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


class ExitCode(IntEnum):
    PASS = 0
    FAILURE = 1
    CONFIG = 2
    TIMEOUT = 124


class ConfigurationError(Exception):
    """The harness cannot run with the supplied environment or arguments."""


class HarnessInterrupted(Exception):
    """The harness received a termination signal."""


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    timed_out: bool
    stop_requested: bool
    elapsed_seconds: float


class BootObserver:
    """Recognise boot milestones across arbitrary pipe-read boundaries."""

    def __init__(self) -> None:
        self.milestones = {name: False for name in MILESTONES}
        self.timer_events = 0
        self.failure: str | None = None
        self._tail = b""
        self._longest_marker = max(
            len(marker)
            for marker in (*MILESTONES.values(), TIMER_EVENT, *FAILURE_MARKERS)
        )

    def observe(self, chunk: bytes) -> bool:
        window = self._tail + chunk
        prior_bytes = len(self._tail)

        for name, marker in MILESTONES.items():
            if not self.milestones[name] and marker in window:
                self.milestones[name] = True

        self.timer_events += count_new_matches(window, TIMER_EVENT, prior_bytes)

        for marker in FAILURE_MARKERS:
            if marker in window:
                self.failure = marker.decode("ascii", errors="replace")
                break

        tail_length = self._longest_marker - 1
        self._tail = window[-tail_length:] if tail_length else b""
        return self.failure is not None or self.successful

    @property
    def successful(self) -> bool:
        return all(self.milestones.values()) and self.timer_events >= TIMER_EVENTS_REQUIRED


def count_new_matches(window: bytes, marker: bytes, prior_bytes: int) -> int:
    """Count matches ending in new input, without double-counting the saved tail."""
    count = 0
    offset = 0
    while True:
        found = window.find(marker, offset)
        if found < 0:
            return count
        if found + len(marker) > prior_bytes:
            count += 1
        offset = found + len(marker)


def positive_number(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be finite and greater than zero")
    return parsed


def positive_integer(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def parse_args() -> argparse.Namespace:
    repository = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=repository,
        help="EaglesOS repository root (default: inferred from this script)",
    )
    parser.add_argument(
        "--sdk",
        type=Path,
        help="Microkit SDK root (default: MICROKIT_SDK from the environment)",
    )
    parser.add_argument(
        "--build-dir",
        type=Path,
        help="new, empty build directory (default: a retained directory in /tmp)",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        help="evidence directory (default: <build-dir>/evidence)",
    )
    parser.add_argument(
        "--timeout",
        type=positive_number,
        default=30.0,
        help="QEMU runtime timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--build-timeout",
        type=positive_number,
        default=600.0,
        help="image build timeout in seconds (default: 600)",
    )
    parser.add_argument(
        "--jobs",
        type=positive_integer,
        default=os.cpu_count() or 1,
        help="parallel make jobs (default: host CPU count)",
    )
    return parser.parse_args()


def emit(level: str, subject: str, detail: str) -> None:
    detail = " ".join(detail.splitlines())
    print(f"X86_BOOT|{level}|{subject}|{detail}", flush=True)


def stream_bytes(data: bytes) -> None:
    output = getattr(sys.stdout, "buffer", None)
    if output is None:
        sys.stdout.write(data.decode("utf-8", errors="replace"))
        sys.stdout.flush()
        return
    output.write(data)
    output.flush()


def normalise_log(raw_path: Path, normalised_path: Path) -> None:
    text = raw_path.read_bytes().decode("utf-8", errors="replace")
    text = ANSI_ESCAPE.sub("", text.replace("\r\n", "\n").replace("\r", "\n"))
    with normalised_path.open("x", encoding="utf-8") as output:
        output.write(text)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_executable(name: str) -> Path:
    found = shutil.which(name)
    if found is None:
        raise ConfigurationError(f"required executable is not on PATH: {name}")
    return Path(found).resolve()


def first_version_line(executable: Path) -> str:
    try:
        result = subprocess.run(
            [str(executable), "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ConfigurationError(f"cannot execute {executable}: {error}") from error
    if result.returncode != 0:
        raise ConfigurationError(
            f"{executable} --version exited with status {result.returncode}"
        )
    output = result.stdout.decode("utf-8", errors="replace")
    version = next((line.strip() for line in output.splitlines() if line.strip()), "")
    if not version:
        raise ConfigurationError(f"{executable} --version produced no output")
    return version


def repository_revision(git: Path, repository: Path) -> str:
    try:
        result = subprocess.run(
            [str(git), "-C", str(repository), "rev-parse", "--verify", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ConfigurationError(f"cannot resolve repository revision: {error}") from error
    revision = result.stdout.decode("ascii", errors="replace").strip()
    if result.returncode != 0 or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ConfigurationError(
            f"cannot resolve repository revision: {detail or 'invalid Git output'}"
        )
    return revision


def prepare_build_directory(requested: Path | None) -> tuple[Path, bool]:
    if requested is None:
        # Nix shells can set TMPDIR to a shell-owned directory that disappears
        # on exit. Use system /tmp explicitly so the default evidence survives.
        return Path(
            tempfile.mkdtemp(prefix="eaglesos-x86-boot-", dir=Path("/tmp"))
        ), True

    build_dir = requested.expanduser().resolve()
    if build_dir.exists():
        if not build_dir.is_dir():
            raise ConfigurationError(f"build path is not a directory: {build_dir}")
        if any(build_dir.iterdir()):
            raise ConfigurationError(f"build directory must be empty: {build_dir}")
    else:
        build_dir.mkdir(parents=True)
    return build_dir, False


def signal_process_group(process_group: int, signum: int) -> bool:
    """Signal a process group, returning whether it still exists."""
    try:
        os.killpg(process_group, signum)
    except ProcessLookupError:
        return False
    return True


def terminate_process_group(process: subprocess.Popen[bytes]) -> bytes:
    """Stop a process group, escalate to KILL, reap it, and return unread output."""
    # The leader can exit before one of its descendants. Signal the group even
    # after the leader has been reaped so no descendant is left behind.
    deadline = time.monotonic() + PROCESS_STOP_GRACE_SECONDS
    signal_process_group(process.pid, signal.SIGTERM)

    try:
        remaining, _ = process.communicate(timeout=PROCESS_STOP_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        signal_process_group(process.pid, signal.SIGKILL)
        remaining, _ = process.communicate()
        return remaining or b""

    # A descendant can close the captured descriptors, ignore TERM, and keep
    # running after communicate() has reaped the leader. Give the entire group
    # the remaining grace period, then kill any surviving members.
    while signal_process_group(process.pid, 0):
        wait = deadline - time.monotonic()
        if wait <= 0:
            signal_process_group(process.pid, signal.SIGKILL)
            break
        time.sleep(min(wait, 0.05))
    return remaining or b""


def run_streamed_process(
    command: list[str],
    *,
    cwd: Path,
    raw_log: Path,
    timeout: float,
    observer: Callable[[bytes], bool] | None = None,
) -> ProcessResult:
    """Run a process with live output, a monotonic deadline, and group cleanup."""
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            bufsize=0,
        )
    except OSError as error:
        raise ConfigurationError(f"cannot start {command[0]}: {error}") from error

    assert process.stdout is not None
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    started = time.monotonic()
    deadline = started + timeout
    timed_out = False
    stop_requested = False

    try:
        with raw_log.open("xb") as output:
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break

                events = selector.select(min(remaining, 0.25))
                for key, _ in events:
                    chunk = os.read(key.fd, 64 * 1024)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    output.write(chunk)
                    output.flush()
                    stream_bytes(chunk)
                    if observer is not None and observer(chunk):
                        stop_requested = True
                        break
                if stop_requested:
                    break

                if process.poll() is not None and not events:
                    # A final readiness notification will drain and unregister the pipe.
                    continue

            if not timed_out and not stop_requested and process.poll() is None:
                try:
                    process.wait(timeout=max(0.0, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    timed_out = True
            unread = terminate_process_group(process)
            if unread:
                output.write(unread)
                output.flush()
                stream_bytes(unread)
                if observer is not None:
                    observer(unread)
    except BaseException:
        terminate_process_group(process)
        raise
    finally:
        selector.close()

    return ProcessResult(
        returncode=process.returncode if process.returncode is not None else -1,
        timed_out=timed_out,
        stop_requested=stop_requested,
        elapsed_seconds=time.monotonic() - started,
    )


def make_artifact(path: Path) -> dict[str, object]:
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def write_evidence(log_dir: Path, evidence: dict[str, object]) -> Path:
    path = log_dir / "evidence.json"
    temporary = log_dir / "evidence.json.tmp"
    with temporary.open("x", encoding="utf-8") as output:
        output.write(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
        output.flush()
        os.fsync(output.fileno())
    try:
        os.link(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    temporary.unlink()
    return path


def install_signal_handlers() -> dict[int, signal.Handlers]:
    previous: dict[int, signal.Handlers] = {}

    def handle(signum: int, _frame: object) -> None:
        raise HarnessInterrupted(signal.Signals(signum).name)

    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        previous[signum] = signal.signal(signum, handle)
    return previous


def restore_signal_handlers(previous: dict[int, signal.Handlers]) -> None:
    for signum, handler in previous.items():
        signal.signal(signum, handler)


def execute(args: argparse.Namespace) -> int:
    started_at = datetime.now(timezone.utc)
    root = args.root.expanduser().resolve()
    timer_example = root / "dep" / "sddf" / "examples" / "timer"
    if not (root / "flake.lock").is_file() or not timer_example.is_dir():
        raise ConfigurationError(f"not an EaglesOS repository root: {root}")

    sdk_argument = args.sdk or (
        Path(os.environ["MICROKIT_SDK"]) if os.environ.get("MICROKIT_SDK") else None
    )
    if sdk_argument is None:
        raise ConfigurationError("set MICROKIT_SDK or pass --sdk")
    sdk = sdk_argument.expanduser().resolve()
    microkit = sdk / "bin" / "microkit"
    kernel = sdk / "board" / BOARD / CONFIG / "elf" / "sel4_32.elf"
    for required in (microkit, kernel):
        if not required.is_file():
            raise ConfigurationError(f"required SDK file is missing: {required}")

    git = resolve_executable("git")
    make = resolve_executable("make")
    qemu = resolve_executable("qemu-system-x86_64")
    source_revision = repository_revision(git, root)
    qemu_version = first_version_line(qemu)
    build_dir, temporary_build = prepare_build_directory(args.build_dir)
    log_dir = (
        args.log_dir.expanduser().resolve()
        if args.log_dir is not None
        else build_dir / "evidence"
    )
    log_dir.mkdir(parents=True, exist_ok=True)

    log_paths = {
        "build_raw": log_dir / "build.raw.log",
        "build_normalized": log_dir / "build.normalized.log",
        "qemu_raw": log_dir / "qemu.raw.log",
        "qemu_normalized": log_dir / "qemu.normalized.log",
    }
    retained_report = log_dir / "microkit-report.txt"
    evidence_paths = (log_dir / "evidence.json", log_dir / "evidence.json.tmp")
    occupied = [
        path
        for path in (*log_paths.values(), retained_report, *evidence_paths)
        if path.exists() or path.is_symlink()
    ]
    if occupied:
        raise ConfigurationError(f"evidence file already exists: {occupied[0]}")

    build_command = [
        str(make),
        f"--jobs={args.jobs}",
        f"--directory={timer_example}",
        f"BUILD_DIR={build_dir}",
        f"MICROKIT_SDK={sdk}",
        f"MICROKIT_BOARD={BOARD}",
        f"MICROKIT_CONFIG={CONFIG}",
    ]
    qemu_command = [
        str(qemu),
        "-machine",
        "q35",
        "-accel",
        "tcg,thread=single",
        "-m",
        "size=2G",
        "-display",
        "none",
        "-monitor",
        "none",
        "-serial",
        "stdio",
        "-no-reboot",
        "-no-shutdown",
        "-d",
        "guest_errors",
        "-kernel",
        str(kernel),
        "-initrd",
        str(build_dir / "loader.img"),
        "-cpu",
        "qemu64,+fsgsbase,+pdpe1gb,+pcid,+invpcid,+xsave,+xsaves,+xsaveopt",
    ]

    evidence: dict[str, object] = {
        "schema_version": 1,
        "status": "running",
        "exit_code": None,
        "started_at": started_at.isoformat(),
        "source_root": str(root),
        "source_revision": source_revision,
        "board": BOARD,
        "config": CONFIG,
        "build_dir": str(build_dir),
        "temporary_build_dir": temporary_build,
        "log_dir": str(log_dir),
        "microkit_sdk": str(sdk),
        "qemu": {"path": str(qemu), "version": qemu_version, "accel": "tcg"},
        "commands": {"build": build_command, "qemu": qemu_command},
        "logs": {name: str(path) for name, path in log_paths.items()},
        "artifacts": {},
        "markers": {},
    }

    emit("INFO", "build-dir", f"path={build_dir} temporary={temporary_build}")
    emit("INFO", "log-dir", f"path={log_dir}")
    emit("INFO", "qemu", f"path={qemu} version={qemu_version} accel=tcg")
    emit("INFO", "build", f"board={BOARD} config={CONFIG} timeout={args.build_timeout}s")

    build_result = run_streamed_process(
        build_command,
        cwd=root,
        raw_log=log_paths["build_raw"],
        timeout=args.build_timeout,
    )
    normalise_log(log_paths["build_raw"], log_paths["build_normalized"])
    evidence["build"] = {
        "returncode": build_result.returncode,
        "stop_requested": build_result.stop_requested,
        "timed_out": build_result.timed_out,
        "elapsed_seconds": build_result.elapsed_seconds,
    }
    if build_result.timed_out:
        evidence.update(
            status="build-timeout",
            exit_code=int(ExitCode.TIMEOUT),
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        evidence_path = write_evidence(log_dir, evidence)
        emit("INFO", "evidence", f"path={evidence_path}")
        emit("TIMEOUT", "build", f"deadline={args.build_timeout}s")
        emit("TIMEOUT", "summary", f"exit_code={int(ExitCode.TIMEOUT)}")
        return ExitCode.TIMEOUT
    if build_result.returncode != 0:
        evidence.update(
            status="build-failed",
            exit_code=int(ExitCode.FAILURE),
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        evidence_path = write_evidence(log_dir, evidence)
        emit("INFO", "evidence", f"path={evidence_path}")
        emit("FAIL", "build", f"returncode={build_result.returncode}")
        emit("FAIL", "summary", f"exit_code={int(ExitCode.FAILURE)}")
        return ExitCode.FAILURE

    image = build_dir / "loader.img"
    report = build_dir / "report.txt"
    if not image.is_file() or not report.is_file():
        evidence.update(
            status="build-artifact-missing",
            exit_code=int(ExitCode.FAILURE),
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        evidence_path = write_evidence(log_dir, evidence)
        emit("INFO", "evidence", f"path={evidence_path}")
        emit("FAIL", "build", "loader.img or report.txt is missing")
        emit("FAIL", "summary", f"exit_code={int(ExitCode.FAILURE)}")
        return ExitCode.FAILURE

    with report.open("rb") as source, retained_report.open("xb") as destination:
        shutil.copyfileobj(source, destination)
    artifacts = {
        "image": make_artifact(image),
        "report": {
            **make_artifact(retained_report),
            "build_path": str(report),
        },
        "sel4_kernel": make_artifact(kernel),
    }
    evidence["artifacts"] = artifacts
    for name in ("image", "report", "sel4_kernel"):
        artifact = artifacts[name]
        emit(
            "INFO",
            name,
            f"path={artifact['path']} bytes={artifact['bytes']} sha256={artifact['sha256']}",
        )

    observer = BootObserver()
    emit(
        "INFO",
        "runtime",
        f"machine=q35 accel=tcg timeout={args.timeout}s timer_events={TIMER_EVENTS_REQUIRED}",
    )
    qemu_result = run_streamed_process(
        qemu_command,
        cwd=root,
        raw_log=log_paths["qemu_raw"],
        timeout=args.timeout,
        observer=observer.observe,
    )
    normalise_log(log_paths["qemu_raw"], log_paths["qemu_normalized"])
    evidence["runtime"] = {
        "returncode": qemu_result.returncode,
        "stop_requested": qemu_result.stop_requested,
        "timed_out": qemu_result.timed_out,
        "elapsed_seconds": qemu_result.elapsed_seconds,
    }
    evidence["markers"] = {
        **observer.milestones,
        "timer_events": observer.timer_events,
        "timer_events_required": TIMER_EVENTS_REQUIRED,
        "required": {
            name: marker.decode("ascii") for name, marker in MILESTONES.items()
        },
        "timer_event_marker": TIMER_EVENT.decode("ascii"),
        "failure": observer.failure,
    }

    if qemu_result.timed_out:
        status, code = "runtime-timeout", ExitCode.TIMEOUT
        missing = ",".join(name for name, seen in observer.milestones.items() if not seen)
        detail = f"deadline={args.timeout}s missing={missing or 'timer-events'}"
    elif observer.failure is not None:
        status, code = "runtime-failed", ExitCode.FAILURE
        detail = f"failure-marker={observer.failure}"
    elif observer.successful:
        status, code = "pass", ExitCode.PASS
        detail = (
            f"milestones={len(MILESTONES)}/{len(MILESTONES)} "
            f"timer_events={observer.timer_events}/{TIMER_EVENTS_REQUIRED}"
        )
    else:
        status, code = "runtime-early-exit", ExitCode.FAILURE
        missing = ",".join(name for name, seen in observer.milestones.items() if not seen)
        detail = (
            f"returncode={qemu_result.returncode} missing={missing or 'timer-events'} "
            f"timer_events={observer.timer_events}/{TIMER_EVENTS_REQUIRED}"
        )

    evidence.update(
        status=status,
        exit_code=int(code),
        finished_at=datetime.now(timezone.utc).isoformat(),
    )
    evidence_path = write_evidence(log_dir, evidence)
    emit("INFO", "evidence", f"path={evidence_path}")
    emit("PASS" if code == ExitCode.PASS else "TIMEOUT" if code == ExitCode.TIMEOUT else "FAIL", "summary", detail)
    return code


def main() -> int:
    args = parse_args()
    previous_handlers = install_signal_handlers()
    try:
        return int(execute(args))
    except ConfigurationError as error:
        emit("ERROR", "configuration", str(error))
        emit("FAIL", "summary", f"exit_code={int(ExitCode.CONFIG)}")
        return ExitCode.CONFIG
    except OSError as error:
        emit("ERROR", "configuration", f"{type(error).__name__}: {error}")
        emit("FAIL", "summary", f"exit_code={int(ExitCode.CONFIG)}")
        return ExitCode.CONFIG
    except HarnessInterrupted as error:
        emit("FAIL", "interrupted", str(error))
        emit("FAIL", "summary", f"exit_code={int(ExitCode.FAILURE)}")
        return ExitCode.FAILURE
    except KeyboardInterrupt:
        emit("FAIL", "interrupted", "SIGINT")
        emit("FAIL", "summary", f"exit_code={int(ExitCode.FAILURE)}")
        return ExitCode.FAILURE
    finally:
        restore_signal_handlers(previous_handlers)


if __name__ == "__main__":
    sys.exit(main())
