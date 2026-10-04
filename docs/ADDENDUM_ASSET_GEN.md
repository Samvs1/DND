# ADDENDUM B: AI asset generation, review and install

Run as a SEPARATE goal after the main build is complete (all Addendum A work exists: manifest,
placeholders, ASSETS_TODO.md, docs/STYLE_BIBLE.md). Obeys SPEC.md sections 0, 2 and 5, and the layering
contracts. Provider: OpenAI Images API. Prepaid budget: about 10 EUR, hard cap 8 EUR.

## B.1 Generate only what is needed
- Candidates are manifest entries with `status: placeholder`. NEVER touch entries with
  `status: real` or `source: v1`. NEVER overwrite a file that exists.
- Priority tiers in `docs/ASSET_PRIORITY.md` (the agent derives them from data, then commits the file):
  - **P1 (generate):** every portrait choice shown in the character wizard that has no real art
    (race and class combinations, at most one image per distinct look), NPC archetype portraits the
    campaign generator can pick, the 30 most frequently encounterable monsters (by encounter
    tables and CR band), one icon per item category and per damage type, the 5 surface icons, 6 region
    banners. 
  - **P2 (do not generate unless `--tier 2` is passed and budget remains).** Everything else stays a
    placeholder. This is correct and expected.
- Icons, tokens and condition marks are generated as 4x4 SHEETS (one API call yields up to 16
  items), then sliced with a slicer modelled on v1 `assets_src/slice.py`. Portraits and banners are
  one call each.

## B.2 Provider and key handling
- Env: `IMAGE_PROVIDER=openai`, `IMAGE_API_KEY` in `.env`. Never print, log, echo or commit it.
  `check_secrets.py` must stay green. Only network calls allowed: OpenAI image and models endpoints.
- Before any generation, list models from the API and choose the current GPT Image model. Do not
  hardcode a retired id (gpt-image-1 is scheduled for retirement on 2026-10-23, verify). If the account
  needs organisation verification for that model, stop and tell the user exactly what to do.
- Default quality: medium (or the cheapest tier that passes review). Use `transparent` background
  where the manifest says so. Do not use high quality unless a medium attempt failed review twice.

## B.3 Style consistency (the whole point)
- `docs/STYLE_BIBLE.md` is a mandatory prefix of every prompt. Re-read it before each batch.
- Every portrait/banner call passes 2 or 3 REAL v1 reference images of the same kind through the
  images edit endpoint (multi-reference input) together with the prompt: "Match the style, palette,
  lighting, framing and painterly quality of the reference images exactly. Create a new subject:
  <subject>." Sheets use one v1 sheet as reference (v1 `assets_src/sheets/`).
- Subjects come from data (race, class, creature type, material). No real people, no copyrighted
  characters, no Baldur's Gate 3 art or names, no text or watermarks in images.

## B.4 Budget guard (code, tested)
- `scripts/gen_assets.py` has `--dry-run` (default) printing: entries to generate, API calls,
  estimated cost per call from `data/asset_costs.json` (editable price table), total. Real
  generation requires `--yes`.
- `logs/asset_spend.json` ledger: written BEFORE each call with the worst-case estimate and updated
  AFTER with the actual cost from the response usage. A call that would push the projected total above
  the cap (`--cap` default 8.00 EUR, converted with a constant in the price table) is refused.
- Retries count toward the cap. On cap hit: stop cleanly, report remaining entries as placeholders.

## B.5 Review pipeline (the reviewer is the Claude Code session itself)
1. **Automatic checks** (Pillow): expected size, alpha present when required (corner pixels
   transparent), not blank (pixel variance), no large uniform borders, sane file size. Failures retry
   without wasting reviewer attention.
2. **Contact sheets:** `scripts/contact_sheet.py` renders up to 12 labelled candidates (key, attempt)
   with 2 v1 reference thumbnails in a top row, saved to `artifacts/assets/review_<n>.png`.
3. **Reviewer:** the session OPENS each sheet image with its image viewing ability and writes
   `artifacts/assets/review_<n>.json`: for each key scores 1-5 for subject correct, style match to
   the references, composition and framing, cleanliness (no text, watermarks, extra limbs, artifacts),
   readability at 64 px; verdict `accept`, `retry` or `reject`; for `retry` a one-sentence prompt fix.
   Accept only when every score is >= 4. Be strict and honest: a mediocre accepted asset is worse than a
   placeholder.
4. **Retries:** at most 3 attempts per key, using the revised prompt. After that keep the placeholder
   and list it in `ASSETS_REPORT.md`.
5. **Install:** accepted files go atomically to the manifest `file` path. Manifest gets
   `source: generated:<model>`, `prompt`, `cost`, `license: "AI generated via OpenAI API, check
   provider terms before commercial use"`, `reviewed: true`. `ASSETS_TODO.md` regenerates.
6. **Final human review:** `artifacts/assets/FINAL_REVIEW.png` (all accepted assets in one or
   more sheets, next to v1 art) and `ASSETS_REPORT.md` (spend vs cap, accepted, rejected, kept as
   placeholder). `scripts/revert_asset.py <key>` restores the placeholder for any asset the user
   dislikes.
7. **In-context check:** after install run the Playwright UI test and view the wizard, a combat scene
   and the sheet screenshots with the new art; fix framing issues (crops, sizes) before finishing.

## B.6 Tests (no network, deterministic)
`FakeImageProvider` returns synthetic images. Tests: dry-run prints and spends nothing; cap refusal;
ledger written before and after; retry counts toward cap; auto-check failures; contact sheet builds;
slicer splits a 4x4 sheet correctly; atomic install and revert; real/v1 entries never overwritten;
manifest and ASSETS_TODO update; key never appears in logs or ledger. One opt-in live smoke test
(`RUN_LIVE_IMAGES=1`) that generates exactly ONE small image and reports its real cost.

## B.7 Definition of done
Tests and all gates green; dry-run output shown; live smoke passed; P1 run within cap with the
ledger shown; reviewer verdict table shown; FINAL_REVIEW.png and ASSETS_REPORT.md exist and were
viewed; UI screenshots with new art viewed; no key material anywhere tracked.
