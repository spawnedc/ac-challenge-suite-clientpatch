#!/usr/bin/env python3
"""Extracts one file from an existing WoW MPQ archive (e.g. common.MPQ)."""

import sys
from pathlib import Path

import mpq


def main() -> int:
    if len(sys.argv) != 4:
        print("Usage: extract_mpq.py <input.mpq> <archived_path> <output_file>", file=sys.stderr)
        print(
            r'Example: extract_mpq.py "/path/to/Data/common.MPQ" "DBFilesClient\Spell.dbc" '
            "input/DBFilesClient/Spell.dbc",
            file=sys.stderr,
        )
        return 1

    input_mpq = Path(sys.argv[1])
    archived_path = sys.argv[2]
    output_file = Path(sys.argv[3])

    if not input_mpq.is_file():
        print(f"error: input MPQ does not exist: {input_mpq}", file=sys.stderr)
        return 1

    with mpq.Archive(str(input_mpq)) as archive:
        if archived_path not in archive:
            print(f"error: {archived_path!r} not found in {input_mpq}", file=sys.stderr)
            return 1
        data = archive[archived_path].read()

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(data)
    print(f"Wrote {output_file} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
