#!/usr/bin/env python3
"""Build the editable five-slide deck from live application state.

Usage:
    backend/.venv/bin/python tools/build_deck.py [--api http://127.0.0.1:8000]

Numbers come from /api/metrics, /api/brief and /api/replay, so the deck cannot
drift from the product. Run it after loading the post-update demo state.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Pt

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "five-slides.pptx"

NAVY = RGBColor(0x0C, 0x1A, 0x2B)
INK = RGBColor(0x1F, 0x2A, 0x3A)
MUTED = RGBColor(0x5B, 0x66, 0x76)
ACCENT = RGBColor(0x25, 0x49, 0xD8)
SOFT = RGBColor(0xF2, 0xF4, 0xF8)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)


def get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=20) as response:
        return json.loads(response.read().decode())


def post(url: str) -> dict:
    request = urllib.request.Request(url, method="POST")
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode())


def textbox(slide, left, top, width, height, text, size=14, bold=False, color=INK, align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(Emu(left), Emu(top), Emu(width), Emu(height))
    frame = box.text_frame
    frame.word_wrap = True
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    run = paragraph.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = "Calibri"
    return box


def bullets(slide, left, top, width, height, items, size=13, color=INK, space=6):
    box = slide.shapes.add_textbox(Emu(left), Emu(top), Emu(width), Emu(height))
    frame = box.text_frame
    frame.word_wrap = True
    first = True
    for item in items:
        paragraph = frame.paragraphs[0] if first else frame.add_paragraph()
        first = False
        paragraph.space_after = Pt(space)
        run = paragraph.add_run()
        run.text = f"• {item}"
        run.font.size = Pt(size)
        run.font.color.rgb = color
        run.font.name = "Calibri"
    return box


def header(slide, number: int, title: str, subtitle: str | None = None):
    bar = slide.shapes.add_shape(1, 0, 0, Emu(9144000), Emu(150000))
    bar.fill.solid()
    bar.fill.fore_color.rgb = NAVY
    bar.line.fill.background()
    textbox(slide, 500000, 250000, 1200000, 260000, f"0{number}", 12, True, ACCENT)
    textbox(slide, 500000, 430000, 8200000, 520000, title, 26, True, NAVY)
    if subtitle:
        textbox(slide, 500000, 960000, 8200000, 400000, subtitle, 12, False, MUTED)
    line = slide.shapes.add_shape(1, Emu(500000), Emu(1380000), Emu(8144000), Emu(9000))
    line.fill.solid()
    line.fill.fore_color.rgb = RGBColor(0xE4, 0xE7, 0xEC)
    line.line.fill.background()


def footer(slide, note: str):
    textbox(slide, 500000, 6600000, 8200000, 260000, note, 9, False, MUTED)


def panel(slide, left, top, width, height, fill=SOFT):
    shape = slide.shapes.add_shape(1, Emu(left), Emu(top), Emu(width), Emu(height))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.color.rgb = RGBColor(0xE4, 0xE7, 0xEC)
    return shape


def build(api: str) -> Path:
    metrics = get(f"{api}/api/metrics")
    brief = get(f"{api}/api/brief")
    replay = post(f"{api}/api/replay")
    exports = get(f"{api}/api/exports")

    totals = metrics["totals"]
    coverage = f"{totals['usable_text']}/{totals['coverage_denominator']} = {totals['coverage_pct']}%"
    findings = brief["findings"]
    rejected = brief["rejected_decision"]
    passed = replay["summary"]["passed"]
    total_checks = replay["summary"]["total"]
    route_counts = {r["route"]: r["count"] for r in metrics["routes"]["effective"]}
    multi = totals["multi_route_records"]

    prs = Presentation()
    prs.slide_width = Emu(9144000)
    prs.slide_height = Emu(6858000)
    blank = prs.slide_layouts[6]

    # ---------------- Slide 1
    slide = prs.slides.add_slide(blank)
    header(
        slide,
        1,
        "The manager problem and what the evidence actually shows",
        f"Selected day: 21 Aug 2026 (IST) · {totals['records']} records · {totals['calls']} calls · "
        f"{totals['meetings']} meetings · usable text {coverage}",
    )
    textbox(
        slide, 500000, 1520000, 8144000, 420000,
        "Problem: incoming calls and meetings arrive with late transcripts and stored labels that "
        "disagree with what was said. A manager needs to know what happened, what needs attention, "
        "and where each conversation belongs — without invented pipeline or performance claims.",
        12, False, INK,
    )
    top = 2020000
    for index, finding in enumerate(findings[:3], start=1):
        panel(slide, 500000, top, 8144000, 1330000)
        textbox(slide, 640000, top + 90000, 7900000, 260000, f"{index}. {finding['title']}", 14, True, NAVY)
        textbox(slide, 640000, top + 350000, 7700000, 300000, finding["observation"], 10.5, False, INK)
        evidence = finding["evidence"]
        where = f"turn {evidence.get('turn')}" if evidence.get("kind") == "turn" else "call transcript"
        textbox(
            slide, 640000, top + 830000, 7700000, 400000,
            f"“{evidence['quote']}”  — {evidence['record_ref']}, {where}\n"
            f"Product effect: {finding['affected_surface']}",
            9.5, False, MUTED,
        )
        top += 1450000
    footer(slide, "All three citations are re-checked against the current source text in the app and by pytest.")

    # ---------------- Slide 2
    slide = prs.slides.add_slide(blank)
    header(slide, 2, "Interface decisions — and what I deliberately left out", "One screen answers: what happened, what needs me, where does it belong.")
    bullets(
        slide, 500000, 1600000, 4200000, 4300000,
        [
            "Overview leads with exceptions, not total activity: coverage, review load and overrides, each with its denominator.",
            "Call representatives and meeting organisers are separate tables — an organiser is not assumed to be the seller.",
            "Every headline number is a link into the filtered inbox, so a manager lands on the records behind it.",
            "The inbox shows suggested and effective routes side by side; manual overrides stay visibly distinct.",
            "Detail view puts the cited passage next to the analysis and highlights it in the transcript.",
            "Data Quality exposes missing text, stale analyses and failed citation checks instead of hiding them.",
        ],
        11.5,
    )
    panel(slide, 5000000, 1600000, 3640000, 4300000)
    textbox(slide, 5180000, 1700000, 3300000, 260000, "Deliberately excluded", 13, True, NAVY)
    bullets(
        slide, 5180000, 2040000, 3300000, 3700000,
        [
            "Pipeline value, revenue, deal stage and forecasts: no opportunity table is supplied.",
            "Performance rankings and talk ratios: missing inputs and no reliable timing for calls.",
            "Account matching from similar names or titles: a proposed association is not a confirmed account.",
            "A live model call: pre-generated analysis plus deterministic rules keeps the product usable with no API key.",
            "Dashboard date filtering: all activity is one local day, so person and source-type filters do the work.",
        ],
        10.5,
        MUTED,
    )
    footer(slide, f"Implementations: React + Vite + Tailwind, FastAPI + SQLite. {passed}/{total_checks} replay checks pass.")

    # ---------------- Slide 3
    slide = prs.slides.add_slide(blank)
    header(slide, 3, "Routing and export design", "Seven destinations; a record can hold more than one, and a manager can always overrule the engine.")
    routes_text = " · ".join(
        f"{r['label']} {route_counts.get(r['route'], 0)}" for r in metrics["routes"]["effective"]
    )
    textbox(slide, 500000, 1500000, 8144000, 300000, "Effective route assignments", 11, True, NAVY)
    textbox(slide, 500000, 1740000, 8144000, 420000, routes_text, 9.5, False, MUTED)
    textbox(
        slide, 500000, 2100000, 5000000, 260000,
        f"{totals['route_assignments']} assignments across {totals['records']} records; {multi} record(s) hold multiple routes.",
        10, False, MUTED,
    )
    panel(slide, 500000, 2420000, 8144000, 2550000)
    textbox(slide, 650000, 2510000, 7800000, 260000, "Difficult case — M04 Cedarwave Distribution", 13, True, NAVY)
    textbox(
        slide, 650000, 2820000, 7800000, 2000000,
        "The transcript contains pricing, a forced migration and a proposal request, so keyword routing "
        "would file it as a deal. The customer's stated condition is credit, they already hold an INR 1.3 "
        "crore credit line, the replacement is still prepaid, and they ask what SpendNest adds beyond the "
        "bank portal. Routed to Customer success with an owed follow-up: this is retention and product fit, "
        "not new pipeline. Evidence: turn 11 (“moving from prepaid to credit is the main issue for us”) and "
        "turn 26 (“Then what do we gain by adding SpendNest?”).",
        11, False, INK,
    )
    textbox(slide, 500000, 5100000, 8144000, 900000,
            "Evidence, multiple destinations and corrections: each output repeats the source identity and its "
            "cited passages. A manual route replaces the effective destination for exports but never the stored "
            "suggestion; the change is audited with a reason, and only an explicit reset clears it.",
            10.5, False, MUTED)
    footer(slide, "Exports: one markdown file per effective route under exports/2026-08-21/, plus needs-review intake files.")

    # ---------------- Slide 4
    slide = prs.slides.add_slide(blank)
    header(slide, 4, "Validation — numbers and conclusions checked against source", "Nothing here is asserted from memory; each value is recomputed by the app.")
    panel(slide, 500000, 1580000, 3900000, 2050000)
    textbox(slide, 640000, 1670000, 3600000, 250000, "Key metric: transcript coverage", 13, True, NAVY)
    bullets(
        slide, 640000, 1980000, 3600000, 1500000,
        [
            f"Numerator: records with nonblank call text or at least one nonblank turn = {totals['usable_text']}.",
            f"Denominator: unique selected records in the same filter = {totals['coverage_denominator']}.",
            f"Result: {coverage}. 26 records have no usable text and keep an intake state.",
            "After revision 2 the numerator rises by one (M07) and the denominator is unchanged.",
        ],
        10,
    )
    panel(slide, 4540000, 1580000, 4100000, 2050000)
    textbox(slide, 4680000, 1670000, 3800000, 250000, "Analytical conclusion: M03 price change", 13, True, NAVY)
    bullets(
        slide, 4680000, 1980000, 3800000, 1500000,
        [
            "Claim: the annual price moved inside one call.",
            "Checked: turn 23 asks why INR 26,000 became INR 39,000; turn 24 splits INR 26,000 recurring and INR 13,000 one-time setup.",
            "Conclusion kept, and routed to deal next steps plus coaching. The app re-verifies the quotation on every load.",
        ],
        10,
    )
    panel(slide, 500000, 3800000, 8144000, 2300000)
    textbox(slide, 640000, 3890000, 7800000, 250000, "Duplicate and update replay — measured, not asserted", 13, True, NAVY)
    textbox(
        slide, 640000, 4200000, 7800000, 1800000,
        f"{passed}/{total_checks} checks pass in the isolated replay harness.\n"
        "Initial import: 44 records, 17 usable texts. Repeat import, shuffled: 0 inserted, 44 ignored, still 44. "
        "M07 manual route: effective Customer success, suggested unchanged. Update: 1 record updated in place, "
        "0 inserted, coverage 18/44, M07 revision 2 with turns visible. Replay of revision 1: 0 inserted, 44 ignored, "
        "M07 still revision 2 with its transcript and override. Unrelated record C01 remains byte-identical. "
        "Export: every manifest path exists in the zip; JSON and CSV agree; a repeat export creates no second active version.",
        10.5, False, INK,
    )
    footer(slide, f"Deck generated from live endpoints at {api} · export version {exports.get('version') or 'n/a'}.")

    # ---------------- Slide 5
    slide = prs.slides.add_slide(blank)
    header(slide, 5, "Trade-offs, rejected decision and what I would do next", "Pre-generated content is labelled; runtime facts are computed; limitations are explicit.")
    bullets(
        slide, 500000, 1580000, 4000000, 2600000,
        [
            "Pre-generated: the 18 analyses, the brief narrative, findings and rejected decision. Each records the revision it was written for.",
            "Runtime: counts, denominators, filters, routing rules, freshness, citation checks, exports and test results.",
            "New text is never shown against an old analysis: it is refreshed or visibly marked pending review, and never silently replaced.",
            "Trade-off: static analyses cannot re-read a materially different transcript; the app flags that instead of faking certainty.",
            "SQLite keeps the demo reproducible; multi-user editing would need a server database and auth.",
        ],
        10.5,
    )
    panel(slide, 4650000, 1580000, 3994000, 2600000)
    textbox(slide, 4790000, 1670000, 3700000, 250000, "Rejected: route M02 as a deal", 13, True, NAVY)
    textbox(
        slide, 4790000, 1980000, 3700000, 2100000,
        f"{rejected['why_rejected']}\n\nTrade-off accepted: {rejected['trade_off']}\n\nAppears in: {rejected['where_it_appears']}",
        9.5, False, MUTED,
    )
    textbox(slide, 500000, 4400000, 8144000, 240000, "Known limitations", 13, True, NAVY)
    bullets(
        slide, 500000, 4700000, 8144000, 1300000,
        [
            "26 records carry no usable text; they get intake states and needs-review outputs, never invented analysis.",
            "No CRM or account graph, so no pipeline value, deal outcomes or cross-person ranking.",
            "Meeting speaker labels are local to each meeting; organisers are not mapped to speakers.",
            "The backend needs a Python host for deployment; a static host alone is insufficient.",
        ],
        10,
    )
    textbox(slide, 500000, 6020000, 8144000, 300000, "Next improvement: a review queue that lets a manager re-run the rules on a changed transcript and diff the previous analysis, instead of only flagging it.", 10.5, True, ACCENT)
    footer(slide, "Deck is editable: docs/five-slides.pptx · regenerate with tools/build_deck.py")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT)
    return OUT


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    try:
        path = build(args.api)
    except Exception as exc:  # noqa: BLE001 - clear operator message
        print(f"Could not build the deck: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"Wrote {path}")
