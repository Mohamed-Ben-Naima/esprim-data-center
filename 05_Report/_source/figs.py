import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch, FancyArrowPatch, Circle
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})

C = dict(dry="#efe6cf", lawn="#d4e8c4", road="#4a4d52", pad="#c9c9c4", it="#23272e", itl="#00b8d9",
         tech="#6b7280", log="#2f6db5", noc="#1c2430", gen="#d99a0b", tank="#b8bcc2", sub="#a8a29e",
         park="#5c6066", sec="#c62828", hv="#8a5a00", ink="#1f2328", muted="#5b6168")

def R(ax, x0, y0, x1, y1, fc, ec="none", lw=0.8, z=1, **kw):
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor=fc, edgecolor=ec, lw=lw, zorder=z, **kw))

def T(ax, x, y, s, c="white", size=8, weight="bold", z=10, **kw):
    ax.text(x, y, s, color=c, fontsize=size, fontweight=weight, ha="center", va="center", zorder=z, **kw)

# ------------------------------------------------------------------ site plan
fig, ax = plt.subplots(figsize=(11, 8.2))
ax.set_facecolor(C["dry"])
R(ax, -170, -130, 230, 130, C["dry"])
R(ax, -140, -95, 140, 95, C["lawn"])
# roads
R(ax, -170, -111, 230, -97, C["road"], z=2)
for x in range(-165, 230, 10):
    R(ax, x, -104.15, x + 5, -103.85, "white", z=3)
R(ax, -65, -97, -55, -37, C["road"], z=2)
R(ax, -95, -44.5, 105, -35.5, C["road"], z=2)
R(ax, -95, 57.5, 105, 66.5, C["road"], z=2)
R(ax, -99.5, -44.5, -90.5, 66.5, C["road"], z=2)
R(ax, 100.5, -44.5, 109.5, 66.5, C["road"], z=2)
# pads
R(ax, -37, -7, 47, 47, C["pad"], z=2)
R(ax, 49, -25, 97, 45, C["pad"], z=2)
R(ax, -66, -33, -14, -3, C["pad"], z=2)
# parking
R(ax, -128, -86, -68, -46, C["park"], z=3)
for yb in (-81, -69, -63, -51):
    for i in range(20):
        x = -126 + i * 2.8
        ax.plot([x, x], [yb - 2.5, yb + 2.5], color="white", lw=0.35, zorder=4)
R(ax, -126, -80.5, -70, -69.5, "#1b2a4a", z=4, alpha=0.55)
R(ax, -126, -62.5, -70, -51.5, "#1b2a4a", z=4, alpha=0.55)
T(ax, -98, -66, "PARKING", size=8)
T(ax, -98, -41, "≈80 places · carports solaires · bornes VE", size=6.5, c=C["ink"], weight="normal")
# buildings
R(ax, -30, 0, 40, 40, C["it"], ec=C["itl"], lw=1.6, z=5)
T(ax, 5, 24, "BÂTIMENT\nINFORMATIQUE", size=10)
T(ax, 5, 12, "salle blanche · ≈200 baies\n70 × 40 m · h 11 m", size=7, weight="normal", c="#cfe9ef")
R(ax, -20, 40, 20, 50, C["pad"], ec=C["muted"], z=4, lw=0.5)
T(ax, 0, 45, "quai de livraison", c=C["ink"], size=6.5, weight="normal")
R(ax, 55, 12, 91, 42, C["tech"], ec=C["itl"], lw=1.2, z=5)
T(ax, 73, 30, "BÂTIMENT\nTECHNIQUE", size=9)
T(ax, 73, 20, "TGBT · onduleurs\ngroupes froids", size=6.3, weight="normal", c="#eef0f2")
R(ax, 40, 24, 55, 30, C["tech"], z=5)
R(ax, -62, -29, -18, -7, C["log"], ec=C["itl"], lw=1.2, z=5)
T(ax, -40, -16, "BÂTIMENT\nLOGISTIQUE", size=9)
T(ax, -40, -25, "bureaux · réunions · pause", size=6.5, weight="normal", c="#e6eefa")
R(ax, -74, -29.6, -62, -6.4, C["noc"], ec=C["itl"], lw=1.2, z=6)
T(ax, -68, -18, "NOC", size=8)
R(ax, -27, -7, -21, 0, "#9cc3e0", z=5)
# generators + tanks
for i in range(6):
    gx = 56 + i * 6.5
    R(ax, gx - 1.8, -12, gx + 1.8, 0, C["gen"], ec="#7a5600", lw=0.6, z=5)
    T(ax, gx, -6, f"G{i+1}", size=6.5, c=C["ink"])
T(ax, 72, 3.5, "6 groupes électrogènes (N+1)", size=6.8, c=C["ink"])
R(ax, 51, -24.5, 91, -13.5, "none", ec=C["muted"], lw=0.8, z=5, ls="--")
for tx in (62, 80):
    R(ax, tx - 7, -20.8, tx + 7, -17.2, C["tank"], ec=C["muted"], lw=0.6, z=6)
T(ax, 71, -28, "cuves de gazole (rétention)", size=6.5, c=C["ink"], weight="normal")
# substation
R(ax, 109, -13, 135, 43, C["sub"], z=3)
for ty, tag in ((30, "A"), (2, "B")):
    R(ax, 115, ty - 2.25, 121, ty + 2.25, "#56605a", z=5)
    T(ax, 118, ty, f"TR-{tag}", size=6.5)
    R(ax, 128.7, ty - 4.5, 129.3, ty + 4.5, C["hv"], z=5)
T(ax, 122, 16, "POSTE\nHT", size=7.5, c=C["ink"])
# HV lines + pylons
for (pts, tag, gy) in (([(170, 44), (230, 61.6)], "A", 30), ([(170, -12), (230, -30.4)], "B", 2)):
    ax.plot([129, pts[0][0]], [gy, pts[0][1]], color=C["hv"], lw=1.4, zorder=6)
    ax.plot([p[0] for p in pts], [p[1] for p in pts], color=C["hv"], lw=1.4, zorder=6)
    ax.plot(170, pts[0][1], marker="X", ms=9, color=C["hv"], zorder=7)
    T(ax, 190, pts[0][1] + (8 if tag == "A" else -8), f"Ligne HT {tag}", size=7.5, c=C["hv"])
# fence + gate
ax.add_patch(Rectangle((-138, -93), 276, 186, fill=False, ec=C["sec"], lw=1.6, ls=(0, (5, 2)), zorder=8))
R(ax, -67, -94, -53, -92, C["lawn"], z=8)
R(ax, -79, -88.5, -73, -83.5, C["noc"], z=8)
T(ax, -40, -86, "poste de garde", size=6.5, c=C["sec"])
ax.plot([-73,-52],[-86,-86],color=C["sec"],lw=0.6,zorder=9)
ax.annotate("entrée unique contrôlée\n(barrières + bornes anti-bélier)", xy=(-60, -94), xytext=(-20, -120),
            fontsize=7, color=C["sec"], ha="left", arrowprops=dict(arrowstyle="->", color=C["sec"], lw=0.9), zorder=9)
for x, y in [(-136, -91), (136, -91), (136, 91), (-136, 91), (-30, -2), (42, -8), (95, 46), (-70, -80), (0, 91), (136, 15)]:
    ax.add_patch(Circle((x, y), 2.2, fc="white", ec=C["sec"], lw=1.1, zorder=9))
# legend
from matplotlib.lines import Line2D
leg = [Line2D([0], [0], color=C["sec"], lw=1.6, ls="--", label="clôture périmétrique"),
       Line2D([0], [0], marker="o", color="w", markeredgecolor=C["sec"], markersize=7, label="caméra CCTV"),
       Line2D([0], [0], color=C["hv"], lw=1.6, label="ligne haute tension"),
       Rectangle((0, 0), 1, 1, fc=C["lawn"], label="pelouse irriguée"),
       Rectangle((0, 0), 1, 1, fc=C["dry"], ec="#bbb", label="terrain naturel")]
ax.legend(handles=leg, loc="upper left", fontsize=7, framealpha=0.95)
# north + scale
ax.annotate("", xy=(212, 118), xytext=(212, 100), arrowprops=dict(arrowstyle="-|>", color=C["ink"], lw=1.5))
T(ax, 212, 124, "N", c=C["ink"], size=10)
ax.plot([160, 210], [-122, -122], color=C["ink"], lw=2.5)
T(ax, 185, -117, "50 m", c=C["ink"], size=7.5)
T(ax, 30, -104, "route d'accès public", size=6.5, weight="normal")
ax.set_xlim(-170, 230); ax.set_ylim(-130, 130); ax.set_aspect("equal"); ax.axis("off")
ax.set_title("Plan de masse du campus – ESPRIM Data Center (≈ 280 × 190 m)", fontsize=12, fontweight="bold", color=C["ink"], pad=10)
fig.tight_layout(); fig.savefig("fig/plan_masse.png", dpi=220); plt.close(fig)

# ------------------------------------------------------------------ box diagram helpers
def box(ax, x, y, w, h, text, fc, tc="white", size=8, ec="none"):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=fc, ec=ec, lw=1, zorder=3))
    ax.text(x, y, text, ha="center", va="center", fontsize=size, color=tc, zorder=4, fontweight="bold")

def arr(ax, a, b, c=C["ink"], lw=1.3, ls="-", style="-|>"):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle=style, mutation_scale=11, color=c, lw=lw, ls=ls, zorder=2))

# ------------------------------------------------------------------ power single line
fig, ax = plt.subplots(figsize=(11, 6.3))
ax.set_xlim(0, 11); ax.set_ylim(0, 6.6); ax.axis("off")
for col, x in (("A", 2.6), ("B", 8.4)):
    fc = "#00838f" if col == "A" else "#3949ab"
    box(ax, x, 6.0, 2.2, 0.55, f"Ligne HT {col}\n(arrivée indépendante)", C["hv"])
    box(ax, x, 5.0, 2.2, 0.55, f"Transformateur TR-{col}\n2,5 MVA", "#56605a")
    box(ax, x, 3.95, 2.2, 0.6, f"TGBT {col}\n(tableau général BT)", fc)
    box(ax, x, 2.85, 2.2, 0.6, f"Onduleurs {col}\n5 × 250 kW (N+1) + batteries", fc)
    box(ax, x, 1.8, 2.2, 0.55, f"PDU / busbar {col}", fc)
    for y1, y2 in ((5.72, 5.28), (4.72, 4.25), (3.65, 3.15), (2.55, 2.08)):
        arr(ax, (x, y1), (x, y2))
    arr(ax, (x, 1.52), (5.5 + (-0.6 if col == "A" else 0.6), 0.88), c=fc, lw=1.6)
box(ax, 5.5, 0.6, 3.2, 0.55, "Baies IT – double alimentation (voie A + voie B)", C["it"], size=8.5)
box(ax, 5.5, 4.55, 2.5, 0.9, "Groupes électrogènes\nG1 … G6  (N+1)\n6 × 500 kVA · gazole", C["gen"], tc=C["ink"])
arr(ax, (4.25, 4.35), (3.72, 4.05), c=C["gen"], lw=1.6)
arr(ax, (6.75, 4.35), (7.28, 4.05), c=C["gen"], lw=1.6)
ax.text(5.5, 3.72, "inverseurs de source (ATS)\ndémarrage < 15 s", ha="center", fontsize=7.2, color=C["muted"])
ax.text(5.5, 2.85, "autonomie batteries ≈ 10 min\n(le temps de démarrer les groupes)", ha="center", fontsize=7.2, color=C["muted"])
ax.text(5.5, 6.35, "Chaîne d'alimentation électrique – deux voies indépendantes A / B", ha="center", fontsize=12,
        fontweight="bold", color=C["ink"])
fig.tight_layout(); fig.savefig("fig/alimentation.png", dpi=220); plt.close(fig)

# ------------------------------------------------------------------ cooling chain
fig, ax = plt.subplots(figsize=(11, 4.6))
ax.set_xlim(0, 11); ax.set_ylim(0, 4.6); ax.axis("off")
ax.text(5.5, 4.3, "Chaîne de refroidissement – de la baie jusqu'à l'air extérieur", ha="center", fontsize=12,
        fontweight="bold", color=C["ink"])
# aisle schematic
ax.add_patch(Rectangle((0.3, 0.5), 3.6, 3.2, fc="#f4f6f8", ec=C["muted"], lw=0.8))
ax.text(2.1, 3.45, "Salle blanche (vue en coupe)", ha="center", fontsize=8, color=C["ink"], fontweight="bold")
for i, x in enumerate((0.8, 2.1, 3.4)):
    kind = ["chaude", "froide", "chaude"][i]
    ax.add_patch(Rectangle((x - 0.35, 0.9), 0.7, 2.2, fc="#fde2e1" if kind == "chaude" else "#dcefff", ec="none"))
    ax.text(x, 0.72, f"allée\n{kind}", ha="center", va="top", fontsize=6.8, color=C["muted"])
for x in (1.45, 2.75):
    ax.add_patch(Rectangle((x - 0.18, 1.0), 0.36, 1.9, fc=C["it"], ec="none"))
    ax.text(x, 1.95, "baie", rotation=90, ha="center", va="center", color="white", fontsize=6.5)
arr(ax, (2.1, 1.2), (1.63, 1.6), c="#1e88e5"); arr(ax, (2.1, 1.2), (2.57, 1.6), c="#1e88e5")
arr(ax, (1.27, 2.3), (0.85, 2.7), c="#e53935"); arr(ax, (2.93, 2.3), (3.35, 2.7), c="#e53935")
box(ax, 5.1, 2.1, 1.5, 0.85, "Armoires\nCRAH\n(N+1)", "#546e7a")
box(ax, 7.2, 2.1, 1.6, 0.85, "Groupes froids\n4 × 400 kW\n(3 + 1)", "#455a64")
box(ax, 9.5, 2.1, 1.7, 0.85, "Aéroréfrigérants\n21 dry coolers\n(free cooling)", "#37474f")
arr(ax, (3.95, 2.3), (4.33, 2.3), c="#e53935"); arr(ax, (4.33, 1.9), (3.95, 1.9), c="#1e88e5")
arr(ax, (5.88, 2.3), (6.38, 2.3), c="#e53935"); arr(ax, (6.38, 1.9), (5.88, 1.9), c="#1e88e5")
arr(ax, (8.02, 2.3), (8.63, 2.3), c="#e53935"); arr(ax, (8.63, 1.9), (8.02, 1.9), c="#1e88e5")
ax.text(5.1, 1.35, "air 20–25 °C", ha="center", fontsize=7, color=C["muted"])
ax.text(7.2, 1.35, "boucle d'eau glacée", ha="center", fontsize=7, color=C["muted"])
ax.text(9.5, 1.35, "rejet de chaleur à l'extérieur\n(toiture du bâtiment IT)", ha="center", fontsize=7, color=C["muted"], va="top")
ax.text(8.35, 3.25, "en hiver : les dry coolers refroidissent seuls l'eau\n→ les groupes froids s'arrêtent (économie d'énergie)",
        ha="center", fontsize=7.2, color="#2e7d32")
fig.tight_layout(); fig.savefig("fig/refroidissement.png", dpi=220); plt.close(fig)

# ------------------------------------------------------------------ security zones
fig, ax = plt.subplots(figsize=(8.5, 5.2))
ax.set_xlim(0, 10); ax.set_ylim(0, 6.2); ax.axis("off")
zones = [("Zone 0 – Voie publique", "#eceff1", C["ink"]),
         ("Zone 1 – Périmètre clôturé : poste de garde, barrières, bornes, CCTV", "#ffe0b2", C["ink"]),
         ("Zone 2 – Bâtiments : badge nominatif, sas d'entrée", "#ffcc80", C["ink"]),
         ("Zone 3 – Salle blanche / salles techniques : badge + biométrie", "#ef6c00", "white"),
         ("Zone 4 – Baie : clé ou code, journalisation", "#b71c1c", "white")]
for i, (label, fc, tc) in enumerate(zones):
    m = i * 0.55
    ax.add_patch(FancyBboxPatch((0.3 + m, 0.2 + m * 0.62), 9.4 - 2 * m, 5.5 - 2 * m * 0.62,
                                boxstyle="round,pad=0.02,rounding_size=0.12", fc=fc, ec="white", lw=1.5))
    ax.text(5, 5.45 - m * 0.62 * 0.97 - 0.02, label, ha="center", va="center", fontsize=8.2, color=tc, fontweight="bold")
ax.text(5, 2.9, "Défense en profondeur :\nchaque zone ajoute un contrôle\net chaque passage est enregistré", ha="center",
        va="center", fontsize=8, color="white")
ax.set_title("Zonage de sécurité physique", fontsize=12, fontweight="bold", color=C["ink"])
fig.tight_layout(); fig.savefig("fig/securite.png", dpi=220); plt.close(fig)
print("ok")
