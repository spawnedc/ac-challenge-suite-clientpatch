#!/usr/bin/env python3
"""Packs a directory tree into an installable WoW MPQ patch archive.

Uses libmpq (https://pypi.org/project/libmpq/), a ctypes binding shipping
prebuilt native libraries for its supported platforms -- no local C/C++
toolchain needed to run this script.
"""

import sys
from pathlib import Path

import mpq

# ZLIB compression shrinks a mostly-zero-padded file like Spell.dbc by roughly
# 10x; both raw and ZLIB-compressed output were cross-checked against an
# independent MPQ reader (StormLib) while building this pipeline.
COMPRESSION_OPTIONS = mpq.FileCreateOptions.compressed(mpq.COMPRESSION_ZLIB, mpq.COMPRESSION_ZLIB)


def to_archive_path(relative: Path) -> str:
    # MPQ archives use backslash-separated internal paths regardless of host OS.
    return str(relative).replace("/", "\\")


def build(input_dir: Path, output_mpq: Path) -> None:
    files = sorted(p for p in input_dir.rglob("*") if p.is_file())
    if not files:
        raise ValueError(f"No files found under {input_dir}")

    output_mpq.parent.mkdir(parents=True, exist_ok=True)
    output_mpq.unlink(missing_ok=True)

    with mpq.Writer(str(output_mpq)) as writer:
        for file in files:
            archived_name = to_archive_path(file.relative_to(input_dir))
            writer.add(archived_name, file.read_bytes(), COMPRESSION_OPTIONS)
            print(f"Added {archived_name}")


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: pack_mpq.py <input_dir> <output.mpq>", file=sys.stderr)
        return 1

    input_dir = Path(sys.argv[1])
    output_mpq = Path(sys.argv[2])

    if not input_dir.is_dir():
        print(f"error: input directory does not exist: {input_dir}", file=sys.stderr)
        return 1

    try:
        build(input_dir, output_mpq)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {output_mpq}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
