# 05_Report

| File | Contents |
|---|---|
| `Rapport_Conception_DataCenter_Phases1-2.docx` | Phase 1–2 report (French, 24 pages): conception, sizing, power, cooling, security, 3D model |
| `Rapport_Conception_DataCenter_Phases1-2.pdf` | Same report as PDF |
| `_source/figs.py` | Generates the diagrams (site plan, power chain, cooling, security zones) from model coordinates |
| `_source/build.js` | Generates the .docx with the `docx` npm package |

Fill in the team members and the supervisor on the cover page before submitting.

## Soutenance du 25 novembre 2026 (`presentation/`, PLAN_05)

| Path | Contents |
|---|---|
| Slides artifact | https://claude.ai/artifact/9SfWhkneCwM7aaFgcNCTd1 – 61 slides in French with speaker notes; Share › Export gives the editable .pptx and the .pdf |
| `presentation/deck/project/` | Deck sources (one HTML file per slide, `deck.css`, `deck.json`); `deck/gen_annex.py` writes the 8 annex slides from the inventory |
| `presentation/deck/render_check.py` | Quality gate D15: renders every slide with Edge, checks overflow, footer band, text < 24 px, broken images |
| `presentation/DC_Casablanca_Soutenance.pdf` | Backup PDF made from the gate renders (images) |
| `presentation/facts.json`, `build_facts.py` | Every number shown on a slide or in the video, read from the inventory, tests and evidence |
| `presentation/assets/` | Diagrams V2–V19 (`build_diagrams.py` → SVG + PNG), licensed photos, `CREDITS.md` |
| `presentation/video/` | Demo video: `clips/` (one per scene), `DC_Casablanca_demo.mp4` (master), `thumbnail.png`, `endcard.png`, `chapters.txt`; recorded by `03_Network/automation/demo_video/director.py`, edited by `edit.py` |
| `presentation/REPETITION.md` | Rehearsal kit: timing, cue cards, 20 likely questions with answers, live-demo plan B |
