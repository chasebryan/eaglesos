#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Chase Bryan
# SPDX-License-Identifier: BSD-2-Clause

"""Check the syntax of every tracked Python source file without writing bytecode."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tokenize


def tracked_python_files(repository: Path) -> tuple[list[Path], str | None]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.py"],
        cwd=repository,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.decode(errors="replace").strip().replace("\n", " ")
        return [], f"git ls-files exited with status {result.returncode}: {detail}"

    names = {
        os.fsdecode(name)
        for name in result.stdout.split(b"\0")
        if name
    }
    return [Path(name) for name in sorted(names)], None


def format_error(path: Path, error: Exception) -> str:
    if isinstance(error, SyntaxError):
        line = error.lineno or 0
        column = error.offset or 0
        message = error.msg
    else:
        line = 0
        column = 0
        message = str(error)

    message = " ".join(message.splitlines())
    return f"PYTHON_SYNTAX|ERROR|{path.as_posix()}:{line}:{column}|{message}"


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    paths, discovery_error = tracked_python_files(repository)
    if discovery_error is not None:
        print(f"PYTHON_SYNTAX|ERROR|git|{discovery_error}")
        print("PYTHON_SYNTAX|FAIL|checked=0|errors=1")
        return 1

    errors: list[str] = []
    for relative_path in paths:
        try:
            with tokenize.open(repository / relative_path) as source_file:
                source = source_file.read()
            compile(source, relative_path.as_posix(), "exec", dont_inherit=True)
        except (OSError, SyntaxError, UnicodeError) as error:
            errors.append(format_error(relative_path, error))

    for error in errors:
        print(error)

    if errors:
        print(f"PYTHON_SYNTAX|FAIL|checked={len(paths)}|errors={len(errors)}")
        return 1

    print(f"PYTHON_SYNTAX|PASS|checked={len(paths)}|errors=0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
