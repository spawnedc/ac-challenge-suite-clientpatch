#!/usr/bin/env python3
"""Extracts Spell.dbc (or another localized DBC file) from a WoW Data directory.

Two things make this less simple than "open common.MPQ and grab the file":

1. DBC files carrying localized text (Spell.dbc among them) ship in the
   locale-specific archives (Data/<locale>/), not the base ones -- verified
   against a real 3.3.5a client: common.MPQ, common-2.MPQ, expansion.MPQ,
   lichking.MPQ, and the base patch.MPQ/patch-2.MPQ/patch-3.MPQ all lack
   DBFilesClient\\Spell.dbc entirely. Only Data/<locale>/locale-<locale>.MPQ
   and its patch-<locale>*.MPQ archives have it.

2. MPQ patching is whole-file override by load priority, not a per-row merge,
   and Blizzard ships each patched DBC as a complete replacement file rather
   than a binary diff (confirmed: the single highest-priority archive
   containing the path already holds the fully-resolved result). So this just
   checks each known locale archive, in priority order, and reads from the
   highest-priority one that actually contains the file -- no need to open a
   StormLib-style patch chain at all.

Uses the same `libmpq` binding pack_mpq.py depends on -- pure Python, no
external tool needed. (The bundled bin/MPQExtractor can't do this: its
--search/--extract only matches names in an archive's internal (listfile),
and Blizzard's own listfiles have never included DBFilesClient paths.)
"""

import sys
from pathlib import Path

import mpq

# Checked in this order; the highest-priority archive that contains the
# target path wins. patch-<locale>-4 etc. don't exist for 3.3.5a build 12340
# (the final WotLK patch level), but listing a few extra is harmless if some
# repack ships one.
ARCHIVE_PRIORITY = [
    "locale-{locale}.MPQ",
    "expansion-locale-{locale}.MPQ",
    "lichking-locale-{locale}.MPQ",
    "patch-{locale}.MPQ",
    "patch-{locale}-2.MPQ",
    "patch-{locale}-3.MPQ",
]


def find_archives(locale_dir: Path, locale: str) -> list[Path]:
    names = (pattern.format(locale=locale) for pattern in ARCHIVE_PRIORITY)
    return [p for p in (locale_dir / name for name in names) if p.is_file()]


def resolve(locale_dir: Path, locale: str, archived_path: str) -> tuple[Path, bytes]:
    archives = find_archives(locale_dir, locale)
    if not archives:
        raise FileNotFoundError(f"no locale archives found in {locale_dir} for locale {locale!r}")

    winner, data = None, None
    for archive_path in archives:
        with mpq.Archive(str(archive_path)) as archive:
            if archived_path in archive:
                data = archive[archived_path].read()
                winner = archive_path

    if data is None:
        raise FileNotFoundError(
            f"{archived_path!r} not found in any of: {', '.join(a.name for a in archives)}"
        )

    return winner, data


def main() -> int:
    if len(sys.argv) not in (4, 5):
        print("Usage: extract_dbc.py <wow_data_dir> <archived_path> <output_file> [locale]", file=sys.stderr)
        print(
            r'Example: extract_dbc.py "/path/to/Data" "DBFilesClient\Spell.dbc" '
            "input/DBFilesClient/Spell.dbc enUS",
            file=sys.stderr,
        )
        return 1

    data_dir = Path(sys.argv[1])
    archived_path = sys.argv[2]
    output_file = Path(sys.argv[3])
    locale = sys.argv[4] if len(sys.argv) == 5 else "enUS"

    locale_dir = data_dir / locale
    if not locale_dir.is_dir():
        print(f"error: locale directory does not exist: {locale_dir}", file=sys.stderr)
        return 1

    try:
        winner, data = resolve(locale_dir, locale, archived_path)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_bytes(data)
    print(f"Resolved from: {winner.name}")
    print(f"Wrote {output_file} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
