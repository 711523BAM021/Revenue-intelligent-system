# Three-minute screen recording — narration script

Record one continuous take of the running app at `http://localhost:3000`. No editing is needed.
Before recording, load the post-update state (Import History → *Load post-update demo state*) so
the inbox has all 44 records and M07 has its transcript.

Total: **~3:00**. Times are cumulative.

---

### 0:00–0:25 — The manager problem (Overview)

**On screen:** Overview, unfiltered. Point at the four headline cards, then the two person tables
side by side.

**Say:**
> "A sales manager gets calls, meetings and transcripts from several systems, and the stored
> labels don't always match what was said. This workspace answers three questions: what happened,
> what needs me, and where should each conversation go. The data is one selected day — 44 records,
> 30 calls and 14 meetings — and I never show a percentage without its denominator. Transcript
> coverage is 18 of 44, and call representatives are kept separate from meeting organisers,
> because an organiser isn't automatically a salesperson."

**Click:** *Transcript coverage* card → the filtered inbox opens (18 records).

---

### 0:25–0:50 — A difficult routing decision (M04, or M02)

**On screen:** open **M04 — Cedarwave Distribution** (`/conversations/meeting/<M04 id>`).
Scroll to *Routing*, then click the evidence item for **turn 11**.

**Say:**
> "This looks like a deal — pricing, a proposal, a migration. But the customer already has an
> INR 1.3 crore credit line, the replacement is still prepaid, and they ask what SpendNest adds
> beyond their bank portal. So it's routed to customer success, not deal next steps: this is a
> retention and product-fit problem. The evidence is turn 11, and clicking it highlights the
> exact line in the transcript."

**Then scroll to the routing panel:**
> "The automated suggestion and the manager's decision are stored separately. I can correct the
> route here, with a reason, and reset it later if I change my mind."

---

### 0:50–1:35 — Initial import and the repeat test (Import History)

**On screen:** Import History. Point at *Current state* (44 records, rev 1 = 44).

**Click:** **1 Reset**, then **2 Import 01_initial.json**. Let the log appear.
**Click:** **3 Repeat initial, shuffled**.

**Say:**
> "Identity is the pair (source_type, source_id) — never a company name, title or array position.
> The first import creates 44 records with 17 usable transcripts. I import the same file again
> with the rows shuffled: the engine reports zero inserted and 44 ignored, and the count is still
> 44. A repeat delivery is not new activity."

---

### 1:35–2:05 — Manual correction and the update (M07)

**Click:** **4 Change M07's route**.
**On screen:** the log shows the manual route; the M07 panel shows suggested ≠ effective.

**Say:**
> "M07 is a support call about four product defects, so I set its route to Customer success. That
> decision is stored separately from the automated suggestion."

**Click:** **5 Import 02_update.json**.

**Say:**
> "Now the late transcript arrives for the same meeting, at revision 2. One record is updated in
> place: no new record, coverage moves from 17 of 44 to 18 of 44, and my manual route is still in
> effect. The analysis is refreshed and visibly flagged for review, because new text arrived."

---

### 2:05–2:30 — Replay the old batch, then show the proof

**Click:** **6 Replay 01_initial.json**.
**On screen:** log says inserted 0, ignored 44; M07 still revision 2, still has text.

**Say:**
> "Replaying revision 1 after revision 2 inserts nothing. M07 keeps the newer transcript, keeps
> the manual route, and unrelated records are byte-for-byte unchanged. Refresh the browser and
> nothing moves, because the state lives in SQLite, not local storage."

**Click:** **Run replay verification**. Scroll the pass/fail table.

**Say:**
> "This runs the whole sequence against a temporary database with the same engine and checks the
> contract — count, coverage, override survival, analysis freshness, manifest paths and
> duplicate-export behaviour — so the result is measured, not a hardcoded success message."

---

### 2:30–2:55 — Export and close

**On screen:** Exports → **Generate new export** → show version, record count, archive tree,
manifest table. Click **revenue-intelligence-export.zip** once (download).

**Say:**
> "The export writes real files: a manager brief, an overview, one markdown output per effective
> route, needs-review intake files for records without text, and both manifests. Every path in
> the manifest exists inside the zip. Re-exporting unchanged state reuses the version instead of
> duplicating outputs; a changed state creates the next version and marks this one superseded."

**Close on:** Manager Brief, three findings with verified evidence.

> "The brief is fixed to 21 August and links each recommendation to a turn or an exact quote.
> Three findings survived checking against the source; the one decision I rejected — routing a
> supplier negotiation as a sales deal — is documented on this page and in the slides."

---

## Pre-recording checklist

- [ ] `data/01_initial.json` and `data/02_update.json` present
- [ ] Backend running on `:8000`, frontend on `:3000`
- [ ] **Import History → Load post-update demo state**
- [ ] Zoom browser to ~110% so evidence text is readable
- [ ] Close unrelated tabs; hide bookmarks bar
- [ ] Say the denominators out loud: 18/44 coverage, 30 calls, 14 meetings
- [ ] One continuous take; narration is what is assessed, not production polish
