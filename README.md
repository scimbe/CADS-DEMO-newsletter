# CADS-DEMO-newsletter — Newsletter/Report Generator

Marketplace demo for **bunsenbrenner.org** (tracking: [CADS-agent-marketplace#22](https://github.com/scimbe/CADS-agent-marketplace/issues/22)).

A small pipeline that turns a real, live weather API into a business-audience
weekly briefing: a real chart, a real HTML/PDF document, and an LLM-written
narrative that is **not allowed to invent numbers** — enforced by code, not
just by prompt.

Core principle of this demo portfolio: **the LLM orchestrates real,
deterministic tools; it does not invent data.** This repo is a generator
tool, not a hosted `*.bunsenbrenner.org` service — it produces artifacts you
commit, run locally, or wire into a scheduled job. No tunnel/ops work is in
scope here.

## Marketplace status

This demo is published to the live **bunsenbrenner.org** registry
(`registry.bunsenbrenner.org`) as a signed manifest. Verified present on 2026-08-29:

- name `newsletter`, latest version `0.1.2`, `installer_kind: binary`
- publisher pubkey `1292c0cc…ce69b` (shared across the whole demo portfolio)
- manifest id `724a8919…7040`

Reproduce the check yourself:

```bash
curl -s https://registry.bunsenbrenner.org/manifests | grep '"name":"newsletter"'
```

**Measured vs. claimed:** what is *measured* here is that the manifest — signed metadata
plus a publisher-signed bundle reference — is listed on the registry. The registry's own
guardrail verdict for a binary-kind manifest explicitly notes it is **not** a static bundle
scan; trust rests on the publisher-pubkey allowlist checked at activation time. It is **not**
a claim that an always-on hosted `*.bunsenbrenner.org` service exists — as stated above this
is a local generator, not a hosted service; live tunnel/service deployment is out of scope.

## What's real here

| Piece | Real implementation |
|---|---|
| Data source | [Open-Meteo Forecast API](https://open-meteo.com/en/docs) — live, no API key, real 7-day Hamburg forecast (`src/fetch_weather.py`) |
| Facts | Pure Python arithmetic over the fetched JSON — no LLM involved (`src/facts.py`) |
| Charts | `matplotlib` renders actual PNGs from the fetched numbers (`src/build_chart.py`) — not ASCII art, not LLM-described |
| Document | `Jinja2` HTML templating (`templates/report.html.j2`) + headless **Google Chrome** `--print-to-pdf` for a real PDF with a real, selectable text layer (`src/render_report.py`) |
| Narrative | `local-devstral-small2` (via litellm-proxy, OpenAI-compatible client) selects 3–5 pre-computed highlights and writes 2–3 connecting sentences — **and nothing else** (`src/llm_narrative.py`) |

## The "LLM doesn't invent data" contract

This is enforced, not just requested:

1. `facts.py` computes a fixed JSON payload (`days[]`, `highlights[]`) from
   the fetched data, deterministically, with no LLM call.
2. The LLM receives that payload as data and a system prompt
   (`src/prompt/narrative_system_prompt.txt`) that says: pick 3–5 highlight
   ids, write 2–3 sentences, use **only** numbers from the payload, reply as
   strict JSON.
3. `narrative_guard.py` regex-extracts every numeric token from the model's
   narrative and checks each one is either (a) a real value from
   `days[]`/`highlights[]` within `±0.05` tolerance (LLM rounding), or (b) a
   small structural allowlist — the day count, or a day-of-month/month
   number that appears verbatim in one of the report's dates (so "on the
   28th" isn't flagged as a fabrication).
4. On guard failure: retry once with a stricter reminder. On a second
   failure: fall back to a deterministic, non-LLM templated sentence over
   the top-2 highlights, and record `"llm_fallback_used": true` in
   `run-manifest.json`. This makes the failure mode **observable and
   tested** (`tests/test_llm_narrative.py`), not a silent pass-through of
   bad output.
5. `scripts/verify_sample.py` re-runs the guard against the *committed*
   `run-manifest.json` and `report.html` — so a later hand-edit or drift
   between generation and commit is caught too, not just trusted at
   generation time.

## Proof artifact

[`docs/sample-report/`](docs/sample-report/) is committed as real, verifiable
proof — not a claim:

- `report.html`, `report.pdf` — the rendered document
- `chart-temperature.png`, `chart-precipitation.png` — the rendered charts,
  plus their exact plotted-data arrays (`.json` siblings) for verification
- `run-manifest.json` — provenance: source URL, raw-response sha256, model
  name, litellm request id, timestamp, guard result, and the frozen facts

Run `python3 scripts/verify_sample.py docs/sample-report` to independently
re-check all of the above against what's actually on disk. See "Real run
output" below for the actual output of a real run.

**Note on reproducibility:** the source is a *forecast* API, not an archive
— re-running `generate_report.py` will fetch different (later) forecast
data each time, so the committed sample reflects one specific real run, not
data that will match a fresh regeneration. That's expected and correct for
a weather briefing; `verify_sample.py` checks internal consistency (the
committed HTML/PDF/charts match the committed manifest's facts), not that
the numbers match some fixed reference.

## How to run it

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt   # or: pip install -r requirements-lock.txt for exact pinned versions

cp .env.example .env
# edit .env: LITELLM_API_BASE, LITELLM_API_KEY (a scoped litellm-proxy virtual
# key for local-devstral-small2 — see the operator's demo-portfolio key, or
# mint your own: curl -X POST $LITELLM_BASE/key/generate ...), LITELLM_MODEL

./scripts/run_demo.sh
```

`run_demo.sh` does a real generation run (real fetch, real chart, real LLM
call, real HTML+PDF), then runs the offline test suite, then runs the
acceptance-bar verifier against the freshly generated `docs/sample-report/`.

Or run the steps individually:

```bash
python3 -m src.generate_report --out docs/sample-report --pdf   # the real run
pytest                                                            # offline suite (default: excludes -m live)
pytest -m live                                                    # touches the real API + real model; needs .env
python3 scripts/verify_sample.py docs/sample-report               # acceptance-bar checker
```

## Repo layout

```
config/report.yaml          location, forecast window, model name, output dir (non-secret)
src/fetch_weather.py        Open-Meteo client -> raw JSON (+ schema validation, sha256)
src/facts.py                deterministic stats over raw JSON -> the facts contract
src/narrative_guard.py      verifies LLM narrative numbers against facts (see above)
src/llm_narrative.py        litellm-proxy call, retry-then-fallback policy
src/build_chart.py          matplotlib chart rendering
src/render_report.py        Jinja2 HTML + headless-Chrome PDF rendering
src/generate_report.py      orchestrator CLI (fetch -> facts -> chart -> llm -> render -> pdf -> manifest)
templates/report.html.j2    the HTML template
data/fixtures/              one frozen real Open-Meteo response, used by every offline test
data/raw/                   gitignored per-run fetch snapshots
tests/                      pytest suite, `-m live` marks tests that touch real services
scripts/run_demo.sh         real end-to-end run + verify
scripts/verify_sample.py    acceptance-bar checker (re-checks the committed artifact)
docs/sample-report/         COMMITTED PROOF ARTIFACT
```

## Real test/acceptance-check output (2026-08-28)

Offline suite (`pytest`, 25 tests, no network/LLM calls, fully deterministic):

```
25 passed, 2 deselected in 1.89s
```

Live suite (`pytest -m live`, real Open-Meteo call + real litellm-proxy call
to `local-devstral-small2`):

```
tests/test_fetch_weather.py::test_fetch_forecast_live_real_api PASSED
tests/test_llm_narrative.py::test_generate_narrative_live_real_litellm_call PASSED
2 passed in 4.16s
```

Real end-to-end generation run (`python3 -m src.generate_report --out
docs/sample-report --pdf`) against the live API and the live model,
narrative passed the facts-only guard on the **first** LLM attempt (no
retry/fallback needed this run):

```
{
  "run_id": "20260828-203428",
  "llm_used": true,
  "llm_fallback_used": false,
  "pdf_written": true,
  "out_dir": "docs/sample-report"
}
```

Acceptance-bar checker against the committed artifact:

```
[ok] manifest present with source_url, sha256, model_name='local-devstral-small2'
[ok] manifest narrative re-verified against frozen facts (7 numbers checked)
[ok] report.html contains the guarded narrative verbatim
[ok] report.pdf starts with %PDF- and pdftotext confirms a real text layer containing the narrative
[ok] chart-temperature.png source data matches fetched facts exactly
[ok] chart-precipitation.png source data matches fetched facts exactly

All acceptance-bar checks passed.
```

## Known limitations / honest gaps

- **`narrative_guard.py` is regex-based, not a semantic checker.** It
  catches any numeric token not grounded in the facts payload, but it can't
  catch a fabricated *non-numeric* claim (e.g. "expect thunderstorms" when
  the payload has no storm data) — the system prompt forbids this but it
  isn't independently enforced the way numbers are. A stronger version
  would validate claims against a small controlled vocabulary too; out of
  scope for this MVP.
- **No historical/"vs. last year" comparison.** Open-Meteo's archive API
  would support this; it's a real, scoped v1.1 follow-up, not implemented
  here.
- **Single location, single report type.** Hamburg only, weather only. The
  facts/guard/render pipeline is generic enough to reuse for another
  open-data source, but that's not wired up.
- **PDF rendering shells out to a system `google-chrome` binary** rather
  than a bundled/pinned dependency — reproducible on this host (confirmed
  installed), but means the PDF step needs Chrome/Chromium present
  wherever this runs. `find_chrome_binary()` fails loudly (not silently)
  if none is found.
- **The litellm virtual key is budget-capped** ($5 / 7 days, scoped to
  `local-devstral-small2` only, per the build-round shared key). If that
  budget is exhausted, `pytest -m live` and `generate_report.py --pdf`'s
  LLM call will fail or fall back — this was **not** hit during this
  build's testing (both live tests and the real end-to-end run above
  succeeded), but is worth knowing if you re-run this later.
- **No CI wired up in this repo yet** (no `.github/workflows/`). The
  default `pytest` run is fully offline/deterministic and safe to run in
  CI as-is; that's a straightforward follow-up, not done here.
