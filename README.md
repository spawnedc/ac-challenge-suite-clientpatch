# ac-challenge-suite-clientpatch

A build pipeline that patches a local WoW 3.3.5a (build 12340) client's `Spell.dbc` and repackages it into an installable MPQ patch, so the two custom spells used by `mod-challenge-suite` (`666666` "Hardcore challenge" and `666667` "Hardcore: Deceased") show a real name and icon in the spellbook and on the buff bar instead of a blank/unnamed aura slot. See that module's README for why this is needed: the server's own `spell_dbc` table only drives server-side logic — the client resolves aura names/icons purely from its own local DBC files, which have no knowledge of custom spell IDs until patched.

## Legal note

`Spell.dbc` (and any other client data file) is Blizzard's proprietary game data. It must never be committed to this repository. `input/` and `build/` are gitignored for exactly this reason — only the *edits* (this pipeline's scripts) are checked in. You supply your own extracted DBC as a local, untracked file.

## Scope

This patch only touches `Spell.dbc`. The two custom spells reuse existing, already-shipped icons (`SpellIconID` 3831 and 252 — see `hardcore_challenge.sql` in mod-challenge-suite for why), so no new `SpellIcon.dbc` rows or custom icon textures are needed. If you'd rather ship distinct custom art later, that would mean extending `patch_dbc.py` to also patch `SpellIcon.dbc` and adding generated icon textures to the build tree — not needed for the current setup.

This entire pipeline is Python, managed with [uv](https://docs.astral.sh/uv/). Packing uses [libmpq](https://pypi.org/project/libmpq/), a ctypes binding that ships prebuilt native libraries for its supported platforms (Linux/macOS via manylinux/musllinux wheels) — no local C/C++ toolchain needed. `uv sync` (or any `uv run`) fetches it automatically.

## Existing client patches matter

MPQ patching is whole-file override by load priority, not a per-row merge: whichever archive contains a given internal path *last*, in the client's load order, wins **entirely** for that file. If a later archive ships its own updated `Spell.dbc` and we patched an earlier, stale one, our own patch (which loads after everything else — that's the point of the `patch-Z` naming) would silently regress every official change since, not just fail to add our two rows.

It's also not as simple as "check `common.MPQ` and its numbered patches": **`Spell.dbc` doesn't live there at all.** Verified against a real 3.3.5a client — `common.MPQ`, `common-2.MPQ`, `expansion.MPQ`, `lichking.MPQ`, and the base `patch.MPQ`/`patch-2.MPQ`/`patch-3.MPQ` all lack `DBFilesClient\Spell.dbc` entirely. DBC files carrying localized text ship in the locale-specific archives instead: `Data/<locale>/locale-<locale>.MPQ` and its `patch-<locale>.MPQ`/`patch-<locale>-2.MPQ`/`patch-<locale>-3.MPQ`. `tools/extract_dbc.py` checks those, in priority order, and reads from the highest-priority one that actually contains the file — which also confirmed empirically that Blizzard ships each patched DBC as a complete replacement file rather than a binary diff, so no patch-chain merging is needed, just picking the right single archive.

The bundled `bin/MPQExtractor` (a StormLib-based tool) can't be used for this step: its `--search`/`--extract` only matches names against an archive's internal `(listfile)`, and Blizzard's own listfiles have never included `DBFilesClient` paths — confirmed by dumping a real `common.MPQ`'s listfile (83,670 entries, zero `.dbc` files). So `extract_dbc.py` instead uses `libmpq` (the same binding `pack_mpq.py` already depends on) directly, which does a real by-name lookup independent of any listfile. `bin/MPQExtractor` stays in the repo for other MPQ exploration (listing an archive's contents, searching for non-DBC assets by pattern) — it's just not part of this particular step.

## Build

1. Extract your own client's `Spell.dbc`, correctly resolving locale + patch priority:

   ```
   uv run tools/extract_dbc.py /path/to/Data "DBFilesClient\Spell.dbc" input/DBFilesClient/Spell.dbc
   ```

   Defaults to the `enUS` locale; pass a fifth argument to use another (e.g. `deDE`). It checks `Data/<locale>/locale-<locale>.MPQ` and its `patch-<locale>*.MPQ` archives, in priority order, and reports which one it actually read from.

2. Patch it:

   ```
   uv run tools/patch_dbc.py input/DBFilesClient/Spell.dbc build/DBFilesClient/Spell.dbc
   ```

3. Pack `build/` into the patch MPQ:

   ```
   uv run tools/pack_mpq.py build dist/patch-Z.mpq
   ```

   `patch-Z` is a placeholder name — use a letter that sorts after your client's existing `patch-2.MPQ`/`patch-3.MPQ` etc. so it loads last and its `Spell.dbc` wins.

## Install

Copy `dist/patch-Z.mpq` into the client's `Data/` folder, next to `patch-2.MPQ`/`patch-3.MPQ`. This is entirely client-side and opt-in — players who don't install it still see the aura applied server-side, just with a blank name/icon (and can rely on the `ac-challenge-suite` addon's own UI instead, once that exists).

## Verifying a patched `Spell.dbc`

`tools/patch_dbc.py` is idempotent — running it again (even against an already-patched file) replaces the two rows rather than duplicating them, so re-running the pipeline after updating your input DBC is safe. It validates the input file's record layout (234 fields / 936 bytes per record, matching build 12340) and fails loudly rather than silently corrupting a mismatched client version.

`tools/pack_mpq.py`'s output was cross-checked during development against an independent MPQ implementation (StormLib, the same one `bin/MPQExtractor` is built on) in both raw and ZLIB-compressed modes — both round-tripped byte-for-byte identical to the original input file, confirming the archives it produces are standards-compliant and not just self-consistent with `libmpq`.

`tools/extract_dbc.py` was verified against a real, complete WoW 3.3.5a client's `Data` folder: it correctly resolved `DBFilesClient\Spell.dbc` from `patch-enUS-3.MPQ` (the highest-priority archive that had it), and the result was byte-for-byte identical to an independently-sourced reference copy of the same file.
