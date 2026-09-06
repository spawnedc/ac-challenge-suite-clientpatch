#!/usr/bin/env python3
"""Patches Spell.dbc to add mod-challenge-suite's custom spell rows.

Mirrors the two rows defined server-side in mod-challenge-suite's
data/sql/world/base/hardcore_challenge.sql. Field layout is for WotLK 3.3.5a
build 12340's Spell.dbc (234 fields, 936 bytes/record) -- see AzerothCore's
src/server/shared/DataStores/DBCStructure.h (struct SpellEntry) for the
authoritative field list this mirrors.
"""

import struct
import sys
from pathlib import Path

WDBC_MAGIC = b"WDBC"
HEADER_FORMAT = "<4I"
HEADER_SIZE = 20
FIELD_SIZE = 4
EXPECTED_FIELD_COUNT = 234
EXPECTED_RECORD_SIZE = EXPECTED_FIELD_COUNT * FIELD_SIZE

# 0-indexed field offsets, per DBCStructure.h's SpellEntry.
FIELD_ID = 0
FIELD_DURATION_INDEX = 40
FIELD_EQUIPPED_ITEM_CLASS = 68
FIELD_EFFECT_1 = 71
FIELD_EFFECT_IMPLICIT_TARGET_A_1 = 86
FIELD_EFFECT_APPLY_AURA_NAME_1 = 95
FIELD_SPELL_ICON_ID = 133
FIELD_SPELL_NAME_START = 136  # 16 consecutive per-locale string offsets
NUM_LOCALES = 16

SPELL_EFFECT_APPLY_AURA = 6
SPELL_AURA_DUMMY = 4
TARGET_UNIT_CASTER = 1

# Mirrors mod-challenge-suite/data/sql/world/base/hardcore_challenge.sql.
# icon_id values are existing, verified SpellIcon.dbc rows reused as placeholders
# (see that SQL file's comments) -- no new SpellIcon.dbc entries are needed.
CUSTOM_SPELLS = [
    {"id": 666666, "name": "Hardcore challenge", "icon_id": 3831},
    {"id": 666667, "name": "Hardcore: Deceased", "icon_id": 252},
]


def read_dbc(path: Path):
    data = path.read_bytes()
    magic = data[0:4]
    if magic != WDBC_MAGIC:
        raise ValueError(f"{path}: not a WDBC file (magic={magic!r})")

    record_count, field_count, record_size, string_block_size = struct.unpack(
        HEADER_FORMAT, data[4:HEADER_SIZE]
    )
    if field_count != EXPECTED_FIELD_COUNT or record_size != EXPECTED_RECORD_SIZE:
        raise ValueError(
            f"{path}: unexpected Spell.dbc layout (fields={field_count}, "
            f"record_size={record_size}); expected {EXPECTED_FIELD_COUNT} fields / "
            f"{EXPECTED_RECORD_SIZE} bytes (WotLK 3.3.5a build 12340). Wrong client version?"
        )

    records_start = HEADER_SIZE
    records_end = records_start + record_count * record_size
    records = [
        bytearray(data[records_start + i * record_size : records_start + (i + 1) * record_size])
        for i in range(record_count)
    ]
    string_block = bytearray(data[records_end : records_end + string_block_size])
    return records, string_block


def get_field(record: bytearray, field_index: int) -> int:
    return struct.unpack_from("<I", record, field_index * FIELD_SIZE)[0]


def set_field(record: bytearray, field_index: int, value: int) -> None:
    struct.pack_into("<I", record, field_index * FIELD_SIZE, value & 0xFFFFFFFF)


def append_string(string_block: bytearray, text: str) -> int:
    offset = len(string_block)
    string_block += text.encode("utf-8") + b"\x00"
    return offset


def build_spell_record(spell: dict, string_block: bytearray) -> bytearray:
    record = bytearray(EXPECTED_RECORD_SIZE)
    set_field(record, FIELD_ID, spell["id"])
    set_field(record, FIELD_DURATION_INDEX, 32767)
    set_field(record, FIELD_EQUIPPED_ITEM_CLASS, -1)
    set_field(record, FIELD_EFFECT_1, SPELL_EFFECT_APPLY_AURA)
    set_field(record, FIELD_EFFECT_IMPLICIT_TARGET_A_1, TARGET_UNIT_CASTER)
    set_field(record, FIELD_EFFECT_APPLY_AURA_NAME_1, SPELL_AURA_DUMMY)
    set_field(record, FIELD_SPELL_ICON_ID, spell["icon_id"])

    # TODO(localization): every locale slot gets the same enUS text for now; once
    # the cross-cutting localization pass lands, source per-locale text from a
    # {id: {locale: name}} table instead (see mod-challenge-suite's README).
    name_offset = append_string(string_block, spell["name"])
    for i in range(NUM_LOCALES):
        set_field(record, FIELD_SPELL_NAME_START + i, name_offset)

    return record


def patch(input_path: Path, output_path: Path) -> None:
    records, string_block = read_dbc(input_path)

    custom_ids = {spell["id"] for spell in CUSTOM_SPELLS}
    records = [r for r in records if get_field(r, FIELD_ID) not in custom_ids]

    for spell in CUSTOM_SPELLS:
        records.append(build_spell_record(spell, string_block))
        print(f"Added spell {spell['id']} ({spell['name']!r}, icon {spell['icon_id']})")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as f:
        f.write(WDBC_MAGIC)
        f.write(
            struct.pack(
                HEADER_FORMAT,
                len(records),
                EXPECTED_FIELD_COUNT,
                EXPECTED_RECORD_SIZE,
                len(string_block),
            )
        )
        for record in records:
            f.write(record)
        f.write(string_block)


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: patch_dbc.py <input Spell.dbc> <output Spell.dbc>", file=sys.stderr)
        return 1

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    try:
        patch(input_path, output_path)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
