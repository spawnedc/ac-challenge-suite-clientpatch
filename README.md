# ac-challenge-suite-clientpatch

A build pipeline that patches a local WoW 3.3.5a (build 12340) client's `Spell.dbc` and repackages it into an installable MPQ patch, so the two custom spells used by `mod-challenge-suite` (`666666` "Hardcore challenge" and `666667` "Hardcore: Deceased") show a real name and icon in the spellbook and on the buff bar instead of a blank/unnamed aura slot. See that module's README for why this is needed: the server's own `spell_dbc` table only drives server-side logic — the client resolves aura names/icons purely from its own local DBC files, which have no knowledge of custom spell IDs until patched.

## Legal note

`Spell.dbc` (and any other client data file) is Blizzard's proprietary game data. It must never be committed to this repository. `input/` and `build/` are gitignored for exactly this reason — only the *edits* (this pipeline's scripts) are checked in. You supply your own extracted DBC as a local, untracked file.

## Scope

This patch only touches `Spell.dbc`. The two custom spells reuse existing, already-shipped icons (`SpellIconID` 3831 and 252 — see `hardcore_challenge.sql` in mod-challenge-suite for why), so no new `SpellIcon.dbc` rows or custom icon textures are needed. If you'd rather ship distinct custom art later, that would mean extending `patch_dbc.py` to also patch `SpellIcon.dbc` and adding generated icon textures to the build tree — not needed for the current setup.

This entire pipeline is Python, managed with [uv](https://docs.astral.sh/uv/). Packing uses [libmpq](https://pypi.org/project/libmpq/), a ctypes binding that ships prebuilt native libraries for its supported platforms (Linux/macOS via manylinux/musllinux wheels) — no local C/C++ toolchain needed. `uv sync` (or any `uv run`) fetches it automatically.

## Existing client patches matter

MPQ patching is whole-file override by load priority, not a per-row merge: the client loads `common.MPQ` → `common-2.MPQ` → `expansion.MPQ` → `lichking.MPQ` → `patch.MPQ` → `patch-2.MPQ` → `patch-3.MPQ` (then locale-specific equivalents), and whichever archive contains a given internal path *last* wins **entirely** for that file. If Blizzard's `patch-2.MPQ`/`patch-3.MPQ` ship their own updated `Spell.dbc` (likely, since spell data changed throughout 3.3.5a's patch cycle), extracting from `common.MPQ` alone would give a stale, pre-patch file — and since our own patch loads after all of these (that's the point of the `patch-Z` naming), patching that stale version would silently regress every official spell change, not just fail to add our two rows.

`tools/extract_dbc.py` (below) resolves this correctly using the real MPQ patch-archive mechanism via the bundled `bin/MPQExtractor` (a StormLib-based tool), rather than picking a single archive by hand.

## Build

1. Extract your own client's `Spell.dbc`, correctly layering its official patches, using the bundled `bin/MPQExtractor`:

   ```
   uv run tools/extract_dbc.py /path/to/Data "DBFilesClient\Spell.dbc" input/DBFilesClient
   ```

   This finds `common.MPQ`/`common-2.MPQ` as the base archive and every official `patch.MPQ`/`patch-<N>.MPQ` in that same directory (in the correct priority order — numerically, not by filesystem listing order), and applies them all before extracting. It deliberately ignores locale-specific patches (`patch-<locale>*.MPQ`) and custom/letter-suffixed ones like a previously-installed `patch-A.MPQ` — only official numbered patches feed into this step.

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

`tools/extract_dbc.py`'s patch-priority resolution was verified by packing three synthetic archives (a base + two "patches") each containing distinct content at the same internal path, then confirming the highest-priority one wins after layering — the same real patch-chain mechanism used against actual client data. What could **not** be verified here is the exact behavior against real retail `patch-2.MPQ`/`patch-3.MPQ` files (this environment doesn't have them) — if `MPQExtractor` reports something unexpected (e.g. needing a `--prefix`), check its `--help` output; that's a StormLib patch-archive concept this script doesn't currently pass through.
