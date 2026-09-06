#!/usr/bin/env python3
"""Extracts a file from a WoW Data directory via the bundled MPQExtractor,
correctly layering the client's own official patches on top of the base
archive first.

MPQ patching is whole-file override by load priority, not a per-row merge: if
patch-2.MPQ/patch-3.MPQ ship their own updated Spell.dbc, extracting from
common.MPQ alone gives a stale, pre-patch file -- and since our own patch loads
after all of these, we'd silently regress every official spell change, not
just fail to add our two custom rows. MPQExtractor's --patches applies the
real MPQ patch-archive mechanism (via StormLib) to resolve this correctly, the
same way this project's own WhatsTraining_Turtle_extractor uses it.
"""

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MPQ_EXTRACTOR = REPO_ROOT / "bin" / "MPQExtractor"

BASE_ARCHIVE_CANDIDATES = ["common.MPQ", "common-2.MPQ"]

# Matches "patch.MPQ" (priority 0, applied first) or "patch-<N>.MPQ" (priority N).
# Deliberately excludes locale-specific patches (Data/<locale>/patch-<locale>*.MPQ)
# -- Spell.dbc localization is out of scope for now (see main README).
PATCH_NAME_RE = re.compile(r"^patch(?:-(\d+))?\.mpq$", re.IGNORECASE)


def patch_priority(path: Path) -> int:
    match = PATCH_NAME_RE.match(path.name)
    assert match, path.name
    return int(match.group(1)) if match.group(1) else 0


def find_patch_files(data_dir: Path) -> list[Path]:
    candidates = [p for p in data_dir.iterdir() if p.is_file() and PATCH_NAME_RE.match(p.name)]
    return sorted(candidates, key=patch_priority)


def find_base_archive(data_dir: Path) -> Path:
    for name in BASE_ARCHIVE_CANDIDATES:
        candidate = data_dir / name
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"none of {', '.join(BASE_ARCHIVE_CANDIDATES)} found in {data_dir}"
    )


def main() -> int:
    if len(sys.argv) != 4:
        print("Usage: extract_dbc.py <wow_data_dir> <archived_path> <output_dir>", file=sys.stderr)
        print(
            r'Example: extract_dbc.py "/path/to/Data" "DBFilesClient\Spell.dbc" '
            "input/DBFilesClient",
            file=sys.stderr,
        )
        return 1

    data_dir = Path(sys.argv[1])
    archived_path = sys.argv[2]
    output_dir = Path(sys.argv[3])

    if not data_dir.is_dir():
        print(f"error: data directory does not exist: {data_dir}", file=sys.stderr)
        return 1

    if not MPQ_EXTRACTOR.is_file():
        print(f"error: {MPQ_EXTRACTOR} not found", file=sys.stderr)
        return 1

    try:
        base_archive = find_base_archive(data_dir)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    patch_files = find_patch_files(data_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    command = [str(MPQ_EXTRACTOR), str(base_archive), "-e", archived_path, "-o", str(output_dir)]
    for patch in patch_files:
        command += ["-p", str(patch)]

    print(f"Base archive: {base_archive.name}")
    print(f"Patches (applied in this order): {', '.join(p.name for p in patch_files) or '(none found)'}")
    subprocess.run(command, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
