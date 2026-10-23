# Revenue Intelligence Inbox

A manager workspace for reviewing calls and meetings, inspecting the evidence behind an
analysis, routing each conversation to the right kind of output, correcting the machine's
suggestion, and exporting organised files another person can actually use.

Built for the Revenue Intelligence Inbox hiring assignment. The dataset is de-identified
assessment data and is **not** committed to any public repository.

---

## 1. What is in the box

| Area | Implementation |
| --- | --- |
| Frontend | React 19 + TypeScript + Vite, Tailwind CSS 4, Recharts, React Router, Lucide icons |
| Backend | Python 3.12, FastAPI, Pydantic, SQLAlchemy 2, SQLite |
| Import engine | Revision-aware, transactional, identity = `(source_type, source_id)` |
| Analysis | 18 pre-generated, evidence-cited analyses + deterministic routing rules |
| Tests | 26 pytest tests: engine, API, and 5 contract tests against the supplied deliveries (all passing, none skipped) |
| Exports | Real `.zip` + `manifest.json` + `manifest.csv`, content-hash versioned |
| Docs | This README, `docs/five-slides.pptx`, `docs/demo-script.md` |

### Pages

1. **Overview** — filtered activity, coverage, review load, routing distribution, per-person
   call and meeting activity (kept separate), source-reported connection rate.
2. **Conversations** — all records with search and seven filters; each row opens the detail view.
3. **Routing & Review** — the decision queue, taxonomy explanations, and the current route
   versus the automated suggestion.
4. **Manager Brief** — fixed to 21 August 2026, evidence-linked, with the three findings and
   the rejected decision.
5. **Exports** — generate, download, inspect the manifest and archive structure, see versioning.
6. **Import History** — the replay lab, batch log, revision counts, M07 check, and the
   pass/fail replay harness.
7. **Data Quality / Settings** — computed anomalies, citation verification, metric and routing
   definitions, provenance, reset.

---

## 2. Run it locally

Requirements: Python 3.11+, Node 20+.

```bash
# 1. Backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --reload --port 8000

# 2. Frontend (second terminal)
cd frontend
npm install
npm run dev            # http://localhost:3000, /api proxied to :8000
```

Open <http://localhost:3000>. On first start the workspace is empty; use **Import lab** to
load the supplied deliveries, or **Load post-update demo state** (reset + revision 1 +
revision 2).

Production-style single process:

```bash
cd frontend && npm run build
cd ../backend && .venv/bin/python -m uvicorn app.main:app --port 8000
# FastAPI serves frontend/dist at / and the API at /api
```

### Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `RII_DATA_DIR` | `./data` | Where `01_initial.json` and `02_update.json` live |
| `RII_DB_PATH` | `backend/var/revenue_intelligence.db` | SQLite file (persistent state) |
| `RII_EXPORT_DIR` | `./exports` | Generated archives and manifests |
| `RII_ALLOWED_ORIGINS` | localhost dev origins | Comma-separated CORS allow-list |
| `RII_ALLOWED_ORIGIN_REGEX` | unset | Optional regex for a preview hostname |
| `VITE_API_BASE_URL` | same origin | Set only if the API is hosted separately |
| `VITE_ALLOWED_HOSTS` | unset | Comma-separated dev-server host allow-list |

No API keys, credentials or paid services are required. There is no model call anywhere in
the running application.

### Dataset locations

```
data/01_initial.json    # delivery revision 1
data/02_update.json     # delivery revision 2 (M07 transcript)
data/README.md          # provenance note; raw deliveries are never served as static files
```

The backend reads them only through the import service. There is no `/data` static route.

---

## 3. Reproduce the required replay

All of this is available in **Import History → Reproduce the required replay** (buttons 1–6),
and every number is read back from SQLite. The equivalent API calls:

```bash
curl -X POST localhost:8000/api/admin/reset
curl -X POST localhost:8000/api/imports -H 'content-type: application/json' -d '{"dataset":"initial"}'
curl -X POST localhost:8000/api/imports -H 'content-type: application/json' -d '{"dataset":"initial","shuffle":true}'
# manually change M07: find it, then override
curl -X PATCH localhost:8000/api/records/meeting/<M07_SOURCE_ID>/override \
     -H 'content-type: application/json' \
     -d '{"routes":["customer_success"],"reason":"Manager: support conversation, not a deal."}'
curl -X POST localhost:8000/api/imports -H 'content-type: application/json' -d '{"dataset":"update"}'
curl -X POST localhost:8000/api/imports -H 'content-type: application/json' -d '{"dataset":"initial"}'
```

Then refresh the browser (state is in SQLite, not localStorage) and confirm:

| Expectation | Where to see it |
| --- | --- |
| 44 unique records | Overview "Selected records"; Import lab "Current state" |
| Repeat import adds nothing | Batch log: `ignored = 44`, `inserted = 0` |
| M07 override survives | Import lab M07 check: suggested ≠ effective, manual override = yes |
| M07 transcript arrives | M07 detail: turns visible, revision 2, coverage 17/44 → 18/44 |
| Revision 1 cannot overwrite revision 2 | Batch log: replay `ignored = 44`; M07 still revision 2 |
| Analysis flagged after new text | M07 badge "Needs review" + note naming revision 2 |
| Other records untouched | C01's revision and payload hash unchanged |

**Automated verification:** `POST /api/replay` (button "Run replay verification") executes the
whole sequence in a temporary database with the same engine and returns real pass/fail checks,
including manifest/zip agreement. Running it does not disturb your saved corrections.

**Reset:** Import lab → "Reset to a clean state", Data Quality → "Reset workspace", or
`POST /api/admin/reset`. Deleting `backend/var/revenue_intelligence.db` also works.

---

## 4. Exports

**Exports → Generate export** writes to `exports/2026-08-21/run-<n>/…` and produces:

```
exports/2026-08-21/
  manifest.json
  manifest.csv
  manager-brief.md
  summary/overview.md
  deal-next-steps/<ref>-<slug>.md
  customer-follow-up/…
  sales-coaching/…
  customer-success/…
  internal-vendor/…
  no-action/…
  needs-review/…        # intake files for records without usable text
```

Download from the page: `revenue-intelligence-export.zip`, `manifest.json`, `manifest.csv`
(endpoints `/api/exports/current/…`). The archive root is `exports/2026-08-21/`; every
`output_paths` value in the manifest is a relative path that exists inside the zip (asserted
by a test and by the replay harness).

**Versioning policy.** The export is a snapshot of application state identified by a content
hash. Re-exporting unchanged state returns the existing version and writes nothing new. A
changed state creates `v(n+1)`, marks the previous run superseded, and updates the unversioned
`revenue-intelligence-export.zip`. A record that changes route only appears in its new
destination in the current version, so obsolete active copies are not left behind.

---

## 5. Metric definitions

| Metric | Definition |
| --- | --- |
| Selected records | Distinct `(source_type, source_id)` after applying the highest revision received. Repeat imports never add. |
| Calls / meetings | Counts by `source_type` among selected records. |
| Activity by day | Calls grouped on `started_at`, meetings on `starts_at`, converted to `Asia/Kolkata`. Delivery time (`exported_at`) is never used. |
| Activity by person | Call representative (`rep_name`, else `rep_email`) and meeting organiser (`organizer_email`) are shown in **separate** tables and never merged. |
| Usable supplied text | Nonblank call `payload.transcript`, or a meeting with at least one nonblank turn. |
| Transcript coverage | Usable supplied texts ÷ unique selected records **in the same filter**. The denominator is always displayed. |
| Needs review | Review state `needs_review` **plus** records still `awaiting_text`. Reviewed records are excluded. |
| Route assignments | Count of effective routes; a record may hold several, so assignments can exceed records. |
| Manual overrides | Records whose effective route comes from a manager, not the engine. |
| Source-reported connection rate | Calls with `is_connected = true` ÷ calls with a non-null `is_connected`; unknown count shown separately. This is a stored classification, not a transcript finding. |
| Missing text | Records without usable supplied text. Never treated as a failed conversation. |

Every percentage in the UI shows its denominator next to it, and the same definitions are in
Data Quality and in `summary/overview.md`.

---

## 6. Routing taxonomy and rules

| Route | Meaning |
| --- | --- |
| Deal next steps | Live commercial conversation: evaluation, pricing, proposal, pilot, decision path. |
| Customer follow-up | A promised follow-up or material send; no confirmed evaluation. |
| Sales coaching | Evidence about how the conversation was handled. Never a performance ranking. |
| Customer success / product issue | Existing customer blocked by product behaviour, access or workflow. |
| Internal or vendor / partnership | Partner, supplier or internal enablement; no customer deal. |
| No action / informational | Nothing owed: wrong number, voicemail, clear decline. |
| Human review required | Evidence missing, contradictory or too thin. Reason is shown. |

Rules, in order of authority:

1. Read the conversation text, not the title or source label.
2. Identify the counterparty: prospect, existing customer, partner, supplier, internal.
3. Separate product interest from a purchase, and a suggestion from a commitment.
4. If the evidence cannot settle it, `needs_review` with a stated reason.
5. An action owner is named only when the text shows that person committing to the action.
6. Meeting organisers are organisers; no organiser-to-speaker mapping exists, so no one is
   called the salesperson on a meeting.
7. A manual override replaces the effective route but never the stored suggestion; only an
   explicit reset removes it.

Multiple destinations are supported. M01 and M02, for example, produce both a partnership/
internal output and a follow-up output.

The engine (`backend/app/routing_rules.py`) is deterministic and returns a trace. Pre-generated
analyses carry their own route rationale and trace, which the UI displays separately from the
manager's decision.

---

## 7. Evidence conventions

- **Meetings:** source record reference + 1-based turn number in the supplied `turns` array.
  Timecodes are shown for locating an excerpt and are never treated as identifiers.
- **Calls:** a short exact quotation from the adapted transcript. No timecodes or talk ratios
  are invented for calls.
- The detail view highlights the cited passage when you click an evidence item, and has a
  find-in-text box.
- Data Quality re-checks every pre-generated citation against the current text at page load.
  A failed match is shown in red, not hidden.
- When evidence is missing, the UI says so rather than filling the gap.

---

## 8. Pre-generated vs runtime — be precise

**Pre-generated (authored offline, loaded read-only):**

- the 18 conversation analyses in `backend/app/corpus/calls.json` and `meetings.json`;
- the manager-brief narrative, the three findings and the rejected decision in
  `backend/app/corpus/editorial.json`.

Every analysis records `origin: pre_generated` and the source revision it was written for.
No model is called by the application, and the UI never claims a model ran.

**Computed at runtime from SQLite:**

- every count, percentage, denominator, grouping and filter;
- revision application and payload replacement;
- routing suggestions for records without pre-generated analysis, and the rules trace;
- analysis freshness (current / pending review / stale / unavailable);
- evidence verification, quality checks, export manifests, zip contents and replay results.

**When new text arrives:** if the analysis is pre-generated, it is rebuilt from the corpus and
the record is flagged `needs_review` with a note naming the revision. If a manager wrote the
analysis, it is preserved, marked `stale`, and flagged — never silently replaced. If no analysis
exists for the new text, a clearly-labelled provisional rules-derived analysis is created.

---

## 9. Tests

```bash
cd backend
.venv/bin/python -m pytest -q
```

The suite covers: initial import shape, idempotent repeats, shuffled order, the two-field key,
revision-2 payload replacement including nulls, older revisions ignored, late transcript,
override preservation, analysis freshness, intake states, metric denominators, malformed-batch
rejection, export files/manifest agreement, export idempotency, API filters and corrections,
downloads, quality and replay endpoints. `tests/test_real_dataset.py` adds the 44-record
contract, the full replay harness and corpus citation verification; it **skips** rather than
passes when `data/01_initial.json` is absent.

Measured against the supplied deliveries: `26 passed in 3.33s`, 0 skipped, 0 failed. The replay
harness reports 26/26 checks passing (see Import History, or `POST /api/replay`).

---

## 10. Known limitations

- No CRM, opportunity table, staff directory or account graph is supplied, so there is no
  pipeline value, deal stage, account join or performance ranking anywhere in the product.
- 26 of 44 records have no usable supplied text. They carry intake states and appear in
  `needs-review/` outputs; nothing substantive is invented for them.
- Meeting speakers are local labels (`Team member A`, `Customer A`), not identities, so no
  cross-meeting person analysis is possible.
- "Action owner" is limited to someone explicitly committing in the text; many records
  therefore have no owner and say so.
- Pre-generated analyses are static. If the supplied text changed materially, the app flags the
  analysis rather than re-reading it with a model.
- SQLite is appropriate for a single-user review workspace. Multi-user concurrent editing would
  need a server database and auth.
- The deployed-later path is documented, but this build is delivered as a locally runnable app;
  no live URL is claimed. FastAPI + SQLite need a Python host (Render/Fly/Railway free tier);
  a static host alone cannot run the backend.
- Browser-based visual checks could not be automated in this environment (Chromium system
  libraries unavailable), so UI verification is TypeScript build, API contract tests and HTTP
  smoke tests. Reviewers should open the app.

## 11. Approximate development time

About 9–10 hours of implementation in one build session, including data inspection, the import
engine, the analysis library, the UI, tests, exports and documentation. AI assistance was used
for drafting code and analysis text; every cited quotation and turn number is verified against
the supplied text by an automated test.

## 12. Repository layout

```
backend/app/          FastAPI app, models, ingest, routing, metrics, exports, replay
backend/app/corpus/   18 pre-generated analyses + editorial brief/findings
backend/tests/        pytest suite and a clearly synthetic fixture dataset
frontend/src/         React app (pages, components, API client)
data/                 supplied deliveries (private assessment data, not for publication)
exports/              generated archives and manifests
docs/                 five-slide deck and three-minute demo script
tools/                deck generator
```
