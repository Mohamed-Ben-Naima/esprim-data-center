"""Build the team speech booklet for deck v1 (24 slides) -> Discours_Soutenance_v1.pdf (A4, French).

  python 05_Report/presentation/discours/build_discours.py

Content lives in content.py; slide thumbnails come from deck_v1/render/<nn>_<id>.png (run deck_v1/render_check.py
first if they are missing). Rendered with Edge (Playwright channel msedge), like the deck gate.
"""
import base64
import html
import io
import re
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import content as C  # noqa: E402

RENDER = HERE.parent / "deck_v1" / "render"
OUT_HTML = HERE / "discours_v1.html"
OUT_PDF = HERE / "Discours_Soutenance_v1.pdf"
WPM = 140  # calm French speaking pace


def md(s: str) -> str:
    """**bold**, `code`, [[pause]]; the rest is trusted HTML from content.py."""
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s.replace("[[pause]]", '<span class="pause">‖</span>')


def words(s: str) -> int:
    return len(re.sub(r"<[^>]+>|\*\*|`|\[\[pause\]\]", " ", s).split())


def secs(card) -> int:
    t = words(card["say"]) * 60 / WPM
    if card.get("steps"):
        t += 300  # the 5-minute demo itself
    return int(round(t / 5) * 5)


def fmt(t: int) -> str:
    m, s = divmod(t, 60)
    return f"{m} min {s:02d}" if m else f"{s} s"


def thumb(card) -> str:
    p = RENDER / f"{card['n']:02d}_{card['id']}.png"
    if not p.exists():
        return ""
    im = Image.open(p).convert("RGB")
    im.thumbnail((720, 405))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=80)
    return f'<img class="thumb" src="data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}">'


def owner(n):
    for name, (a, b), col, mission in C.TEAM:
        if a <= n <= b:
            return name, col
    raise ValueError(n)


def card_html(c) -> str:
    name, col = owner(c["n"])
    parts = [f'<div class="card{' long' if c.get('steps') else ''}" style="--c:{col}">',
             f'<div class="head"><span class="num">{c["n"]}</span><h3>{html.escape(c["title"])}</h3>'
             f'<span class="dur">≈ {fmt(secs(c))}</span></div>',
             f'<div class="top">{thumb(c)}<div class="say"><div class="lbl">À dire</div><p>{md(c["say"])}</p></div></div>']
    if c.get("steps"):
        rows = "".join(f"<tr><td class='t'>{t}</td><td class='st'>{s}</td><td>{md(x)}</td></tr>" for t, s, x in c["steps"])
        parts.append(f'<div class="box steps"><div class="lbl">Commentaire pendant la démo</div><table>{rows}</table></div>')
    keys = "".join(f"<li>{k}</li>" for k in c["keys"])
    parts.append(f'<div class="grid"><div class="box keys"><div class="lbl">Idées clés</div><ul>{keys}</ul></div>'
                 f'<div class="box norm"><div class="lbl">Norme et conformité</div><p>{c["norm"]}</p></div></div>')
    if c["traps"]:
        tr = "".join(f'<div class="qa"><p class="q">{html.escape(q)}</p><p class="a">{md(a)}</p></div>'
                     for q, a in c["traps"])
        parts.append(f'<div class="box traps"><div class="lbl">Problèmes possibles et questions du jury → réponse</div>{tr}</div>')
    if c["alt"] != "—" or c["improve"] != "—":
        parts.append(f'<div class="grid"><div class="box alt"><div class="lbl">Alternative (substitution)</div>'
                     f'<p>{c["alt"]}</p></div><div class="box imp"><div class="lbl">Pour améliorer</div>'
                     f'<p>{c["improve"]}</p></div></div>')
    if c.get("relay"):
        parts.append(f'<div class="relay"><span>Relais →</span> {md(c["relay"])}</div>')
    parts.append("</div>")
    return "".join(parts)


def speaker_html(name, rng, col, mission) -> str:
    cards = [c for c in C.SLIDES if rng[0] <= c["n"] <= rng[1]]
    total = sum(secs(c) for c in cards)
    sent = re.split(r"(?<=[.?!])\s+", cards[0]["say"].replace("[[pause]]", ""))
    first = ""
    for x in sent:  # at least ~8 words, so the opener is a real sentence
        first = f"{first} {x}".strip()
        if words(first) >= 8:
            break
    relay = next((c["relay"] for c in cards if c.get("relay")), None)
    out = [f'<section class="speaker" style="--c:{col}"><div class="band"><div><p class="who">{name}</p>'
           f'<p class="rng">Slides {rng[0]} → {rng[1]} · ≈ {fmt(total)}</p></div><p class="mission">{mission}</p></div>',
           f'<div class="memo"><p><b>Ta première phrase :</b> « {md(first.strip())} »</p>']
    if relay:
        out.append(f'<p><b>Ta phrase de relais :</b> « {md(relay)} »</p>')
    out.append("</div>")
    out += [card_html(c) for c in cards]
    out.append("</section>")
    return "".join(out)


def front() -> str:
    team_rows = ""
    grand = 0
    for name, rng, col, mission in C.TEAM:
        t = sum(secs(c) for c in C.SLIDES if rng[0] <= c["n"] <= rng[1])
        grand += t
        team_rows += (f'<tr><td><span class="dot" style="background:{col}"></span><b>{name}</b></td>'
                      f'<td>{rng[0]} → {rng[1]}</td><td>≈ {fmt(t)}</td><td>{mission}</td></tr>')
    team_rows += f'<tr class="tot"><td><b>Total</b></td><td>24 slides</td><td>≈ {fmt(grand)}</td><td>dont 5 min de démo</td></tr>'
    norms = "".join(f"<tr><td class='nm'>{n}</td><td>{w}</td><td>{u}</td><td class='who2'>{who}</td></tr>"
                    for n, w, u, who in C.NORMS)
    iso = "".join(f"<tr><td class='mono'>{k}</td><td>{t}</td><td>{d}</td><td><span class='pill {s.lower()}'>{s}</span></td></tr>"
                  for k, t, d, s in C.ISO)
    tia = "".join(f"<tr><td>{d}</td><td><span class='pill {s.lower()}'>{s}</span></td></tr>" for d, s in C.TIA)
    gold = "".join(f"<tr><td><b>{a}</b></td><td class='big'>{b}</td><td class='muted'>{c}</td></tr>" for a, b, c in C.GOLDEN)
    wrd = "".join(f"<tr><td class='ok'>✔ {a}</td><td class='no'>✘ {b}</td></tr>" for a, b in C.WORDS)
    glo = "".join(f"<tr><td><b>{a}</b></td><td>{b}</td></tr>" for a, b in C.GLOSSARY)
    return f"""
<section class="cover">
  <p class="kick">Soutenance · 25 novembre 2026 · ESPRIM</p>
  <h1>Data Center Casablanca<br><span>Le discours de l'équipe</span></h1>
  <p class="sub">Présentation v1 · 24 slides · ANSI/TIA-942 Rated-3 · ISO/IEC 27001:2022</p>
  <table class="team"><tr><th>Orateur</th><th>Slides</th><th>Durée</th><th>Mission</th></tr>{team_rows}</table>
  <p class="note">Durées calculées sur le texte à dire, à {WPM} mots/minute (rythme calme). Plan imposé : 20 à 25 slides.</p>
  <div class="legend">
    <h2>Comment lire chaque fiche</h2>
    <ul>
      <li><b>À dire</b> : le texte à réciter. Phrases courtes. Les mots en <b>gras</b> = à appuyer avec la voix.
          Le signe <span class="pause">‖</span> = une respiration, un regard vers le jury.</li>
      <li><b>Idées clés</b> : si tu oublies le texte, ces 2–3 idées suffisent. Dis-les avec tes mots.</li>
      <li><b>Norme et conformité</b> : quelle norme, ce qu'elle demande, où nous en sommes (fait / simulé / conçu / partiel).</li>
      <li><b>Problèmes possibles</b> : les questions que le jury peut poser, avec une réponse courte et honnête.</li>
      <li><b>Alternative / Pour améliorer</b> : ce qu'on aurait pu choisir, et ce qu'on ferait ensuite.</li>
    </ul>
    <h2>Les 5 règles devant le jury</h2>
    <ol>
      <li>Un chiffre = celui de la page « Chiffres d'or ». Jamais un autre.</li>
      <li>Trois mots, trois sens : <b>réalisé</b> (tourne dans le labo), <b>simulé</b> (BMS-SIM, CCTV-SIM), <b>conçu</b> (sur le papier).</li>
      <li>Dire nos limites <b>avant</b> qu'on nous les demande : c'est notre force.</li>
      <li>On ne sait pas ? « Nous ne l'avons pas mesuré ; voici comment nous le ferions. »</li>
      <li>Parler au jury, pas à l'écran. Une idée par phrase.</li>
    </ol>
  </div>
</section>
<section class="page">
  <h2 class="pt">Les normes en 2 minutes</h2>
  <p class="lead">Tout le monde doit pouvoir dire la 2<sup>e</sup> colonne en une phrase. La dernière colonne dit qui la présente.</p>
  <table class="norms"><tr><th>Norme</th><th>Ce que c'est</th><th>Chez nous</th><th>Qui</th></tr>{norms}</table>
</section>
<section class="page">
  <h2 class="pt">Conformité : ce qui est fait, sans arrondi</h2>
  <p class="lead">Phrase à retenir : « <b>11 contrôles ISO 27001 sur 12, 6 exigences TIA-942 sur 8</b>. Nous sommes
  alignés, pas certifiés : la certification exige un SMSI complet et un audit par un organisme accrédité. »</p>
  <h3>ISO/IEC 27001:2022 – les 12 mesures de l'Annexe A retenues (sur 93)</h3>
  <table class="iso"><tr><th>Mesure</th><th>Titre</th><th>Ce que nous faisons</th><th>Statut</th></tr>{iso}</table>
  <h3>ANSI/TIA-942-C Rated-3 – les 8 exigences suivies</h3>
  <table class="tia"><tr><th>Exigence</th><th>Statut</th></tr>{tia}</table>
  <p class="muted small">Preuves datées : 03_Network/report/evidence (flow_matrix.csv, fw_audit.txt, nas5_restore.txt, verify_lab.txt…).</p>
</section>
<section class="page">
  <h2 class="pt">Les chiffres d'or</h2>
  <p class="lead">Source unique : <code>05_Report/presentation/facts.json</code>. Le même chiffre dans toutes les bouches.</p>
  <table class="gold"><tr><th>Sujet</th><th>À dire</th><th>Attention</th></tr>{gold}</table>
  <div class="trap"><b>Piège n° 1 – 3,0 s ou 2,5 s ?</b> La couverture dit 3,0 s (campagne de tests), la slide 22 dit
  2,5 s (démo enregistrée). Les deux sont vrais, les deux sont sous la cible de 5 s. En démo en direct : dire le chiffre affiché.</div>
  <h3>Les mots qui comptent</h3>
  <table class="words"><tr><th>À dire</th><th>À ne jamais dire</th></tr>{wrd}</table>
</section>
<section class="page">
  <h2 class="pt">Glossaire express</h2>
  <p class="lead">Si le jury demande « c'est quoi ? », la réponse tient en une ligne.</p>
  <table class="glo">{glo}</table>
</section>
"""


def back() -> str:
    qa = "".join(f"<tr><td class='who2'>{w}</td><td><b>{html.escape(q)}</b><br>{a}</td></tr>" for w, q, a in C.QA)
    imp = "".join(f"<tr><td class='prio'>{p}</td><td><b>{w}</b></td><td>{y}</td></tr>" for p, w, y in C.IMPROVE)
    chk = "".join(f"<li>{x}</li>" for x in C.CHECKLIST)
    return f"""
<section class="page">
  <h2 class="pt">Questions et réponses : qui répond ?</h2>
  <p class="lead">Celui qui est désigné répond en 2–3 phrases ; un coéquipier peut compléter d'une phrase. Les réponses
  détaillées par slide sont dans chaque fiche.</p>
  <table class="qa2">{qa}</table>
</section>
<section class="page">
  <h2 class="pt">Si nous avions trois mois de plus</h2>
  <p class="lead">Réponse prête à « qu'est-ce que vous amélioreriez ? » — dans l'ordre de priorité.</p>
  <table class="imp2"><tr><th>#</th><th>Quoi</th><th>Pourquoi</th></tr>{imp}</table>
  <div class="trap"><b>Points uniques de défaillance restants (à avouer si on nous le demande)</b> : un seul DNS, un seul
  serveur web, un seul NAS (sans copie hors site), un seul bastion. Tous viennent de la limite de 15,7 Go de RAM du labo,
  pas de la conception.</div>
  <h2 class="pt" style="margin-top:9mm">Check-list avant le 25 novembre</h2>
  <ul class="check">{chk}</ul>
</section>
"""


CSS = """
@page { size: A4; margin: 13mm 13mm 15mm 13mm; }
* { box-sizing: border-box; }
body { font-family: "Segoe UI", Calibri, Arial, sans-serif; color: #1f2937; font-size: 9.6pt; line-height: 1.38; margin: 0; }
b { color: #0f172a; }
code { font-family: Consolas, monospace; font-size: 0.92em; background: #f1f5f9; padding: 0 3px; border-radius: 3px; }
.pause { color: #94a3b8; font-weight: 700; padding: 0 3px; }
section.page, section.cover { page-break-after: always; }
.cover .kick { color: #0e7490; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; font-size: 9pt; margin: 6mm 0 2mm; }
.cover h1 { font-size: 30pt; line-height: 1.05; margin: 0 0 2mm; color: #0f172a; }
.cover h1 span { color: #0e7490; font-size: 21pt; }
.cover .sub { color: #475569; margin: 0 0 6mm; font-size: 10.5pt; }
table { width: 100%; border-collapse: collapse; margin: 2mm 0 3mm; }
th { text-align: left; background: #0f172a; color: #fff; font-weight: 600; padding: 4px 6px; font-size: 8.8pt; }
td { padding: 4px 6px; border-bottom: 1px solid #e2e8f0; vertical-align: top; }
.team td { font-size: 9.6pt; } .team td:nth-child(-n+3) { white-space: nowrap; } .team tr.tot td { background: #f1f5f9; border-top: 2px solid #0f172a; }
.dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; }
.note, .muted { color: #64748b; } .small { font-size: 8.4pt; }
.legend { border: 1px solid #cbd5e1; border-radius: 6px; padding: 3mm 5mm; margin-top: 5mm; background: #f8fafc; }
.legend h2 { font-size: 12pt; margin: 2mm 0 1mm; color: #0e7490; } .legend li { margin: 1.2mm 0; }
h2.pt { font-size: 17pt; margin: 0 0 1mm; color: #0f172a; border-bottom: 3px solid #0e7490; padding-bottom: 1mm; }
h3 { font-size: 11pt; margin: 4mm 0 1mm; color: #0e7490; }
.lead { color: #334155; margin: 1mm 0 3mm; }
.norms td.nm { font-weight: 700; width: 25mm; color: #0e7490; } .who2 { width: 19mm; font-weight: 600; color: #475569; }
.mono { font-family: Consolas, monospace; font-weight: 700; color: #0e7490; width: 15mm; }
.pill { display: inline-block; padding: 0 7px; border-radius: 10px; font-size: 8.2pt; font-weight: 700; color: #fff; }
.pill.fait, .pill.mesuré { background: #15803d; } .pill.partiel, .pill.simulé { background: #b45309; } .pill.conçu { background: #64748b; }
.gold td.big { font-weight: 700; color: #0e7490; } .gold td { font-size: 9.2pt; }
.trap { border-left: 4px solid #be123c; background: #fff1f2; padding: 2.5mm 4mm; margin: 3mm 0; border-radius: 0 5px 5px 0; }
.words td.ok { color: #15803d; width: 55%; } .words td.no { color: #be123c; }
.glo td:first-child { width: 42mm; }
.prio { font-weight: 800; color: #0e7490; width: 7mm; font-size: 12pt; }
.check li { margin: 1.5mm 0; }
.qa2 td { font-size: 9.2pt; }
/* speaker sections */
section.speaker { page-break-before: always; }
.band { display: flex; gap: 6mm; align-items: center; background: var(--c); color: #fff; border-radius: 7px; padding: 4mm 6mm; }
.band .who { font-size: 24pt; font-weight: 800; margin: 0; line-height: 1; color: #fff; }
.band .rng { margin: 1mm 0 0; font-weight: 600; opacity: .92; white-space: nowrap; }
.band .mission { margin: 0; font-size: 10.5pt; border-left: 2px solid rgba(255,255,255,.6); padding-left: 5mm; }
.memo { border: 1.5px dashed var(--c); border-radius: 6px; padding: 2mm 4mm; margin: 3mm 0 4mm; font-size: 10pt; }
.memo p { margin: 1mm 0; }
.card { border: 1px solid #cbd5e1; border-top: 4px solid var(--c); border-radius: 6px; padding: 3mm 4mm; margin: 0 0 4.5mm;
        page-break-inside: avoid; }
.card.long { page-break-inside: auto; } .card.long .box, .card.long .grid, .qa { page-break-inside: avoid; }
.head { display: flex; align-items: center; gap: 3mm; margin-bottom: 2mm; }
.head .num { background: var(--c); color: #fff; font-weight: 800; border-radius: 50%; width: 8mm; height: 8mm; display: flex;
             align-items: center; justify-content: center; font-size: 11pt; flex: none; }
.head h3 { margin: 0; color: #0f172a; font-size: 12.5pt; flex: 1; }
.head .dur { color: var(--c); font-weight: 700; white-space: nowrap; }
.top { display: flex; gap: 4mm; align-items: flex-start; }
.thumb { width: 54mm; border: 1px solid #cbd5e1; border-radius: 3px; flex: none; }
.say { flex: 1; } .say p { font-size: 11pt; line-height: 1.5; margin: 0; color: #111827; }
.lbl { font-size: 7.6pt; font-weight: 800; letter-spacing: .07em; text-transform: uppercase; color: var(--c); margin-bottom: 1mm; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 3mm; }
.box { background: #f8fafc; border-radius: 5px; padding: 2mm 3mm; margin-top: 2.5mm; }
.box p { margin: 0; } .box ul { margin: 0; padding-left: 4.5mm; } .box li { margin: .6mm 0; }
.box.norm { background: #ecfeff; } .box.traps { background: #fff7ed; } .box.imp { background: #f0fdf4; }
.qa { margin: 1.2mm 0; } .qa .q { font-weight: 700; color: #9a3412; margin: 0; } .qa .a { margin: 0 0 0 3mm; }
.steps table { margin: 0; } .steps td { padding: 2px 5px; font-size: 9.6pt; } .steps td.t { font-family: Consolas, monospace; font-weight: 700;
        color: var(--c); width: 11mm; } .steps td.st { font-weight: 700; width: 21mm; }
.relay { margin-top: 3mm; background: var(--c); color: #fff; border-radius: 5px; padding: 2mm 4mm; font-size: 10.5pt; }
.relay b { color: #fff; } .relay span { font-weight: 800; }
"""


def main():
    body = front() + "".join(speaker_html(*t) for t in C.TEAM) + back()
    doc = f'<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Discours – Soutenance v1</title><style>{CSS}</style></head><body>{body}</body></html>'
    OUT_HTML.write_text(doc, encoding="utf-8")
    foot = ('<div style="font-size:7pt;color:#94a3b8;width:100%;padding:0 13mm;display:flex;justify-content:space-between;'
            'font-family:Segoe UI"><span>DC Casablanca · Discours de soutenance v1 · 25/11/2026</span>'
            '<span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>')
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge")
        pg = b.new_page()
        pg.goto(OUT_HTML.as_uri())
        pg.pdf(path=str(OUT_PDF), format="A4", print_background=True, display_header_footer=True,
               header_template="<span></span>", footer_template=foot,
               margin={"top": "13mm", "bottom": "15mm", "left": "13mm", "right": "13mm"})
        b.close()
    for name, rng, _, _ in C.TEAM:
        t = sum(secs(c) for c in C.SLIDES if rng[0] <= c["n"] <= rng[1])
        print(f"{name:8s} slides {rng[0]:2d}-{rng[1]:2d}  {fmt(t)}")
    print(f"total {fmt(sum(secs(c) for c in C.SLIDES))} -> {OUT_PDF}")


if __name__ == "__main__":
    main()
