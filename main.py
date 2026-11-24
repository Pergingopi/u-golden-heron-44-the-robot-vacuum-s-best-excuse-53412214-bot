#!/usr/bin/env python3
"""The Robot Vacuum's Best Excuse.

Writes a single one-line excuse, spoken by a robot vacuum to its tired
homeowner for missing a spot, to /output/entry.txt (or $MAKEFUN_OUTPUT_DIR).

The line is a fixed constant: a deterministic entry, byte-identical on every
run. Python 3 standard library only, no network, no randomness.
"""

import os
import sys
import tempfile

# The entry: one sentence, one line, 97 characters, no trailing newline.
ENTRY = (
    "I mapped that corner as a cliff, a rug, and a sovereign nation "
    "\u2014 and I don't vacuum foreign soil."
)

OUTPUT_NAME = "entry.txt"


def _reject_control_chars(text: str) -> None:
    """Reject C0/C1 control characters (the gate wants plain UTF-8 text)."""
    for ch in text:
        code = ord(ch)
        if code < 0x20 or 0x7F <= code <= 0x9F:
            raise ValueError(f"control character U+{code:04X} in entry")


def _validate(text: str) -> None:
    """Enforce the competition gate: 1-140 chars, not whitespace-only."""
    _reject_control_chars(text)
    if not (1 <= len(text) <= 140):
        raise ValueError(f"entry length {len(text)} outside 1..140")
    if not text.strip():
        raise ValueError("entry is whitespace-only")
    if "\n" in text or "\r" in text:
        raise ValueError("entry must be a single line")
    if text.endswith("\n") or text.endswith("\r"):
        raise ValueError("entry must not end with a newline")


def _output_dir() -> str:
    """$MAKEFUN_OUTPUT_DIR, falling back to /output when unset or empty."""
    out = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    return out


def _fsync_dir(path: str) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_all(fd: int, data: bytes) -> None:
    """Write every byte: os.write may write only part of the buffer."""
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        if written == 0:
            raise OSError("os.write returned 0 bytes")
        view = view[written:]


def _write_atomic(target: str, data: bytes) -> None:
    """Write data to target via a temp file in the same directory.

    The temp file is created with mkstemp (unique name, O_EXCL semantics),
    written with a _write_all loop, fsynced, chmodded, and atomically
    renamed over the target. On any failure the temp file is unlinked in
    a finally block so a stale temp can never linger for the next run;
    a leftover stale temp from a killed earlier run is harmless because
    mkstemp always picks a fresh name, and the rename is retried once
    if it is interrupted.
    """
    out_dir = os.path.dirname(target) or "."
    fd = None
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(prefix=".entry-", dir=out_dir)
        _write_all(fd, data)
        os.fsync(fd)
        os.close(fd)
        fd = None
        os.chmod(tmp_path, 0o644)
        try:
            os.replace(tmp_path, target)
        except OSError:
            # A stale temp from a killed run must not poison the retry:
            # the temp is already unique, so just retry the rename once.
            os.replace(tmp_path, target)
        tmp_path = None
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def main() -> int:
    _validate(ENTRY)
    data = ENTRY.encode("utf-8")

    out_dir = _output_dir()
    # Never delete the output directory itself: the grader mounts it.
    os.makedirs(out_dir, exist_ok=True)

    target = os.path.join(out_dir, OUTPUT_NAME)
    _write_atomic(target, data)
    _fsync_dir(out_dir)

    # Read-back verification: the file must match the constant exactly.
    with open(target, "rb") as fh:
        written = fh.read()
    if written != data:
        raise ValueError("read-back mismatch: entry.txt != ENTRY")
    os.chmod(target, 0o644)
    return 0


if __name__ == "__main__":
    sys.exit(main())
