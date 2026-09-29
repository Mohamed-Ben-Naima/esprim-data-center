const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, ImageRun, Table, TableRow, TableCell,
  WidthType, ShadingType, BorderStyle, LevelFormat, TableOfContents, Header, Footer, PageNumber, PageBreak,
  TabStopType, VerticalAlign,
} = require("docx");

const FONT = "Calibri";
const INK = "1F2328", ACCENT = "00838F", MUTED = "5B6168", DARK = "23272E";
const W = 9638; // A4 content width in DXA with 2 cm margins

// ---------- helpers
const t = (text, o = {}) => new TextRun({ text, font: FONT, ...o });
const P = (runs, o = {}) => new Paragraph({
  spacing: { after: 120, line: 290 }, alignment: AlignmentType.JUSTIFIED, ...o,
  children: (Array.isArray(runs) ? runs : [runs]).map(r => typeof r === "string" ? t(r) : r),
});
// rich text: **bold** segments
const rich = (s) => s.split(/(\*\*[^*]+\*\*)/).filter(Boolean).map(seg =>
  seg.startsWith("**") ? t(seg.slice(2, -2), { bold: true }) : t(seg));
const p = (s, o) => P(rich(s), o);
const H1 = (s) => new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: true, children: [t(s)] });
const H1n = (s) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [t(s)] });
const H2 = (s) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [t(s)] });
const H3 = (s) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [t(s)] });
const bullet = (s, lvl = 0) => new Paragraph({ numbering: { reference: "bul", level: lvl }, spacing: { after: 60, line: 280 }, children: rich(s) });
const numbered = (s) => new Paragraph({ numbering: { reference: "num", level: 0 }, spacing: { after: 60, line: 280 }, children: rich(s) });

let figN = 0, tabN = 0;
function figure(path, caption, widthPx = 620) {
  const buf = fs.readFileSync(path);
  // read png/jpg size
  let w, h;
  if (path.endsWith(".png")) { w = buf.readUInt32BE(16); h = buf.readUInt32BE(20); }
  else { let i = 2; while (i < buf.length) { if (buf[i] !== 0xFF) { i++; continue; } const m = buf[i + 1]; const len = buf.readUInt16BE(i + 2);
      if (m >= 0xC0 && m <= 0xC3) { h = buf.readUInt16BE(i + 5); w = buf.readUInt16BE(i + 7); break; } i += 2 + len; } }
  figN++;
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 }, keepNext: true,
      children: [new ImageRun({ type: path.endsWith(".png") ? "png" : "jpg", data: buf,
        transformation: { width: widthPx, height: Math.round(widthPx * h / w) },
        altText: { title: caption, description: caption, name: `fig${figN}` } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 220 },
      children: [t(`Figure ${figN} – `, { bold: true, size: 18, color: MUTED }), t(caption, { italics: true, size: 18, color: MUTED })] }),
  ];
}

const border = { style: BorderStyle.SINGLE, size: 4, color: "C9CDD2" };
const borders = { top: border, bottom: border, left: border, right: border };
function table(headers, rows, widths, caption) {
  const total = widths.reduce((a, b) => a + b, 0);
  const cell = (txt, i, head) => new TableCell({
    borders, width: { size: widths[i], type: WidthType.DXA }, verticalAlign: VerticalAlign.CENTER,
    shading: head ? { fill: DARK, type: ShadingType.CLEAR, color: "auto" } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ spacing: { after: 0, line: 260 },
      children: head ? [t(txt, { bold: true, color: "FFFFFF", size: 19 })] : rich(txt).map(r => { r.root && 0; return r; }) })],
  });
  const tbl = new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths,
    rows: [new TableRow({ tableHeader: true, children: headers.map((h, i) => cell(h, i, true)) }),
      ...rows.map((r, ri) => new TableRow({ children: r.map((c, i) => {
        const tc = cell(c, i, false);
        return tc; }) }))],
  });
  const out = [];
  if (caption) { tabN++; out.push(new Paragraph({ spacing: { before: 120, after: 80 }, keepNext: true,
    children: [t(`Tableau ${tabN} – `, { bold: true, size: 18, color: MUTED }), t(caption, { italics: true, size: 18, color: MUTED })] })); }
  out.push(tbl, new Paragraph({ spacing: { after: 160 }, children: [] }));
  return out;
}
function callout(title, text) {
  return new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [W], rows: [new TableRow({ children: [
    new TableCell({ width: { size: W, type: WidthType.DXA },
      borders: { top: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" }, bottom: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" },
        right: { style: BorderStyle.NONE, size: 0, color: "FFFFFF" }, left: { style: BorderStyle.SINGLE, size: 24, color: ACCENT } },
      shading: { fill: "E8F4F5", type: ShadingType.CLEAR, color: "auto" },
      margins: { top: 120, bottom: 120, left: 200, right: 200 },
      children: [new Paragraph({ spacing: { after: 60 }, children: [t(title, { bold: true, color: ACCENT })] }),
        new Paragraph({ spacing: { after: 0, line: 280 }, children: rich(text) })] })] })] });
}
const gap = () => new Paragraph({ spacing: { after: 120 }, children: [] });


const { PositionalTab, PositionalTabAlignment, PositionalTabRelativeTo, PositionalTabLeader } = require("docx");
function tocLine(text, page, top) {
  const { Tab, TabStopType, LeaderType } = require("docx");
  return new Paragraph({ spacing: { before: top ? 140 : 20, after: 20 }, indent: { left: top ? 0 : 360 },
    tabStops: [{ type: TabStopType.RIGHT, position: W, leader: LeaderType ? LeaderType.DOT : "dot" }],
    children: [t(text, { bold: top, size: top ? 22 : 20 }),
      new TextRun({ font: FONT, size: top ? 22 : 20, bold: top, children: [new Tab(), String(page)] })] });
}
// ---------- content
const C = [];

// Cover
C.push(
  new Paragraph({ spacing: { before: 200, after: 0 }, children: [t("ESPRIM", { bold: true, size: 26, color: ACCENT })] }),
  new Paragraph({ spacing: { after: 600 }, children: [t("Module Projet Data Center – 5ème année", { size: 22, color: MUTED })] }),
  new Paragraph({ spacing: { after: 120 }, children: [t("Conception d'un Data Center", { bold: true, size: 56, color: INK })] }),
  new Paragraph({ spacing: { after: 360 }, children: [t("De la conception à la modélisation 3D du campus – Phases 1 et 2", { size: 30, color: ACCENT })] }),
  ...figure("img/01_Hero_SouthEast.jpg", "Vue d'ensemble du campus modélisé sous Blender (rendu Cycles)", 640),
  new Paragraph({ spacing: { before: 400, after: 80 }, children: [t("Réalisé par : ", { bold: true }), t("Mohamed Ben Naima, ……………………………………")] }),
  new Paragraph({ spacing: { after: 80 }, children: [t("Encadré par : ", { bold: true }), t("……………………………………")] }),
  new Paragraph({ spacing: { after: 80 }, children: [t("Année universitaire : ", { bold: true }), t("2026 – 2027")] }),
  new Paragraph({ spacing: { after: 80 }, children: [t("Date : ", { bold: true }), t("29 septembre 2026")] }),
);

// Résumé
C.push(new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: true, children: [t("Résumé")] }),
  p("Ce rapport présente les deux premières phases de notre projet de data center : la **conception** et la **modélisation 3D du campus**. En nous appuyant sur le support de cours « Objectif 1 – Qu'est-ce qu'un Data Center ? », nous avons défini un data center de niveau **Tier III** d'environ **1 MW** de charge informatique (≈ 200 baies), réparti en trois bâtiments : le bâtiment informatique (salle blanche), le bâtiment technique (énergie et froid) et le bâtiment logistique (NOC et bureaux)."),
  p("Chaque choix répond à l'un des quatre enjeux critiques du cours : **continuité électrique** (deux arrivées haute tension indépendantes, groupes électrogènes N+1, onduleurs), **maîtrise du froid** (allées chaudes/froides, eau glacée, free cooling), **sécurisation** (défense en profondeur en cinq zones) et **haute disponibilité** (redondance de chaque composant)."),
  p("Le campus complet a ensuite été modélisé sous **Blender 5.2** par programmation Python, puis rendu de façon photoréaliste (moteur Cycles, matériaux procéduraux, végétation, relief). Nous avons produit cinq images de présentation et une vidéo de survol par drone de 34 secondes. L'ensemble du projet est versionné avec **Git** sur un dépôt GitHub privé."),
  p("Les phases suivantes porteront sur l'aménagement intérieur, la conception du réseau sous **GNS3** et les services."),
  new Paragraph({ spacing: { before: 200 }, children: [t("Mots-clés : ", { bold: true }), t("data center, Tier III, redondance N+1, PUE, free cooling, sécurité physique, Blender, modélisation procédurale, Git LFS.", { italics: true })] }),
);

// TOC
C.push(new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: true, children: [t("Table des matières")] }),
  tocLine("1. Introduction", 4, true),
tocLine("1.1 Contexte", 4, false),
tocLine("1.2 Objectifs", 4, false),
tocLine("1.3 Démarche", 4, false),
tocLine("2. Qu'est-ce qu'un data center ?", 5, true),
tocLine("2.1 Définition", 5, false),
tocLine("2.2 Les trois bâtiments élémentaires", 5, false),
tocLine("2.3 Les enjeux critiques", 5, false),
tocLine("2.4 Types de data centers", 5, false),
tocLine("3. Cahier des charges et hypothèses", 6, true),
tocLine("3.1 Niveau de disponibilité : Tier III", 6, false),
tocLine("3.2 Capacité", 6, false),
tocLine("3.3 Bilan de puissance", 6, false),
tocLine("4. Choix de la localisation", 8, true),
tocLine("5. Architecture générale du campus", 9, true),
tocLine("5.1 Plan de masse", 9, false),
tocLine("5.2 Principes d'implantation", 9, false),
tocLine("6. Le bâtiment informatique", 10, true),
tocLine("7. Le bâtiment technique : énergie et froid", 11, true),
tocLine("7.1 Continuité électrique (E1)", 11, false),
tocLine("7.2 Maîtrise du froid (E2)", 12, false),
tocLine("8. Le bâtiment logistique et le NOC", 14, true),
tocLine("9. Sécurité physique (E3)", 15, true),
tocLine("10. Réponse aux enjeux critiques", 17, true),
tocLine("11. Modélisation 3D sous Blender", 18, true),
tocLine("11.1 Objectifs et outil", 18, false),
tocLine("11.2 Méthode : modélisation procédurale", 18, false),
tocLine("11.3 Organisation de la scène", 18, false),
tocLine("11.4 Réalisme du rendu", 18, false),
tocLine("11.5 Rendus", 19, false),
tocLine("11.6 Vidéo de survol par drone", 19, false),
tocLine("12. Gestion de projet et outillage", 21, true),
tocLine("12.1 Organisation des fichiers", 21, false),
tocLine("12.2 Versionnement avec Git", 21, false),
tocLine("13. Limites et perspectives", 22, true),
tocLine("13.1 Limites", 22, false),
tocLine("13.2 Prochaines étapes", 22, false),
tocLine("14. Conclusion", 23, true),
tocLine("Annexe A – Glossaire", 24, true),
tocLine("Annexe B – Dimensions principales", 24, true));

// 1 Introduction
C.push(H1("1. Introduction"),
  H2("1.1 Contexte"),
  p("Les data centers sont devenus l'infrastructure de base de toute l'économie numérique : chaque service en ligne, chaque application d'entreprise et chaque sauvegarde dépend d'équipements hébergés dans ces bâtiments. Leur conception est un exercice pluridisciplinaire qui mêle génie électrique, thermique, sécurité, réseau et architecture."),
  p("Dans le cadre du module Projet Data Center de 5ème année, notre équipe doit concevoir un data center complet : le site et ses bâtiments, leur aménagement intérieur, puis le réseau et les services qui y fonctionnent."),
  H2("1.2 Objectifs"),
  p("Les objectifs pédagogiques du cours guident notre travail :"),
  bullet("définir ce qu'est un data center et comprendre l'intérêt de sa mise en place ;"),
  bullet("distinguer les types de data centers et leurs spécificités ;"),
  bullet("comprendre l'importance du choix de la localisation et ses critères ;"),
  bullet("décrire la composition d'un data center : plan, zones et salles."),
  p("Nous y ajoutons un objectif concret : **rendre la conception visible** grâce à une maquette 3D fidèle, utilisable pour la présentation et comme base des phases suivantes."),
  H2("1.3 Démarche"),
  p("Le projet est découpé en six phases. Chacune se termine par un livrable vérifiable avant de passer à la suivante :"),
  ...table(["Phase", "Contenu", "Outils", "État"], [
    ["1. Conception", "Objectifs, niveau Tier, dimensionnement, localisation, plan de masse", "Documents", "Terminée"],
    ["2. Extérieur 3D", "Campus, trois bâtiments, énergie, sécurité, rendus, vidéo", "Blender", "Terminée"],
    ["3. Intérieurs", "Salle blanche, salles techniques, NOC", "Blender", "À venir"],
    ["4. Réseau", "Topologie, redondance, VLAN, plan d'adressage, DMZ", "GNS3", "À venir"],
    ["5. Services", "Supervision, sécurité logique, sauvegarde", "GNS3, serveurs", "À venir"],
    ["6. Livrables", "Rapport final, présentation, vidéo finale", "Word, Blender", "En cours"],
  ], [1900, 4238, 1800, 1700], "Découpage du projet en phases"),
);

// 2 Data center
C.push(H1("2. Qu'est-ce qu'un data center ?"),
  H2("2.1 Définition"),
  p("Un data center est **un espace physique où sont regroupés des équipements informatiques** (serveurs, baies de stockage, routeurs, commutateurs…) chargés de **stocker, traiter et protéger des données**. Il fournit à ces équipements tout ce dont ils ont besoin pour fonctionner sans interruption : énergie, refroidissement, connectivité et sécurité."),
  H2("2.2 Les trois bâtiments élémentaires"),
  p("Selon le cours, un data center se compose de trois bâtiments aux rôles distincts :"),
  ...table(["Bâtiment", "Rôle", "Contenu principal"], [
    ["Technique", "Supporter l'activité informatique", "Alimentation et conversion électrique, groupes électrogènes, distribution, refroidissement, filtrage de l'air, sécurité, éclairage"],
    ["Informatique (salle blanche)", "Héberger le système d'information", "Baies de stockage, racks, serveurs, routeurs, switchs, gestion des câbles, logiciels de gestion"],
    ["Logistique", "Surveiller et exploiter", "NOC (centre de contrôle des opérations), bureaux, salles de réunion, salles de pause"],
  ], [2100, 2400, 5138], "Les trois bâtiments d'un data center (d'après le cours)"),
  H2("2.3 Les enjeux critiques"),
  p("Pour bien fonctionner, un data center doit répondre à quatre enjeux majeurs. Nous les codons **E1 à E4** et les utilisons comme fil conducteur de tout le rapport :"),
  ...table(["Code", "Enjeu", "Ce que cela signifie"], [
    ["E1", "Continuité électrique", "Les équipements ne perdent jamais leur alimentation"],
    ["E2", "Maîtrise du froid", "Les salles restent entre 20 et 25 °C"],
    ["E3", "Sécurisation", "Seules les personnes autorisées atteignent les équipements"],
    ["E4", "Haute disponibilité", "Tout composant peut tomber en panne ou être maintenu sans arrêter le service"],
  ], [900, 2600, 6138], "Les quatre enjeux critiques"),
  H2("2.4 Types de data centers"),
  p("La taille d'une salle IT varie fortement, d'une petite salle intégrée à un bâtiment jusqu'à un bâtiment entièrement dédié. D'après l'enquête citée dans le cours (InformationWeek Analytics), près de la moitié des salles IT font moins de 185 m². Avec environ 1 500 m² de salle blanche dans un bâtiment dédié, notre projet se situe dans la catégorie des **grands data centers d'entreprise ou de colocation**."),
);

// 3 Cahier des charges
C.push(H1("3. Cahier des charges et hypothèses"),
  callout("Remarque", "Les chiffres de ce chapitre sont des **hypothèses de conception** posées pour un projet académique. Ils sont cohérents entre eux et avec les pratiques du secteur, mais doivent être validés avec l'encadrant avant d'être utilisés dans les phases réseau et intérieures."),
  gap(),
  H2("3.1 Niveau de disponibilité : Tier III"),
  p("La classification de l'Uptime Institute définit quatre niveaux de disponibilité :"),
  ...table(["Niveau", "Principe", "Disponibilité", "Arrêt annuel"], [
    ["Tier I", "Infrastructure de base, aucun composant redondant", "99,671 %", "≈ 28,8 h"],
    ["Tier II", "Composants redondants (N+1), un seul chemin de distribution", "99,741 %", "≈ 22 h"],
    ["**Tier III**", "**Maintenable sans arrêt** : N+1 et deux chemins (un actif, un secours)", "**99,982 %**", "**≈ 1,6 h**"],
    ["Tier IV", "Tolérant aux pannes : 2N, deux chemins actifs", "99,995 %", "≈ 0,4 h"],
  ], [1400, 4838, 1700, 1700], "Les niveaux Tier de l'Uptime Institute"),
  p("Nous retenons le **Tier III**. C'est la cible habituelle des data centers d'entreprise et de colocation : chaque équipement peut être arrêté pour maintenance sans interrompre le service, ce qui répond directement à l'enjeu E4. Le Tier IV doublerait quasiment l'installation électrique et frigorifique pour un gain de disponibilité faible, injustifié dans notre scénario."),
  H2("3.2 Capacité"),
  ...table(["Paramètre", "Valeur retenue"], [
    ["Nombre de baies", "≈ 200 baies 42U (600 × 1 200 mm)"],
    ["Puissance moyenne par baie", "5 kW"],
    ["Charge informatique (IT)", "≈ 1 MW"],
    ["Surface de salle blanche", "≈ 1 500 m²"],
    ["PUE visé", "1,4 à 1,5"],
    ["Puissance totale du site", "≈ 1,4 à 1,5 MW"],
    ["Température de consigne", "20 à 25 °C en allée froide"],
  ], [4200, 5438], "Hypothèses de capacité"),
  H2("3.3 Bilan de puissance"),
  p("Le **PUE** (Power Usage Effectiveness) est le rapport entre l'énergie totale consommée par le site et l'énergie consommée par les seuls équipements informatiques. Avec 1 MW de charge IT et un PUE de 1,45, la puissance totale du site est d'environ **1,45 MW**. Avec un facteur de puissance de 0,8, cela représente environ **1,8 MVA** apparents. Ce chiffre sert à dimensionner les transformateurs et les groupes électrogènes (chapitre 7)."),
);

// 4 Localisation
C.push(H1("4. Choix de la localisation"),
  p("Le cours classe les critères de localisation d'un data center privé par ordre de priorité. Nous les avons appliqués à un **scénario d'implantation en zone industrielle en périphérie du Grand Tunis** :"),
  ...table(["Priorité", "Critère", "Application à notre site"], [
    ["1", "Sécurité physique", "Zone industrielle hors lit d'oued et zone inondable, à l'écart des aéroports et des sites dangereux ; terrain plat et clôturable"],
    ["2", "Disponibilité énergétique", "Proximité du réseau haute tension national, ce qui permet deux arrivées indépendantes"],
    ["3", "Connectivité réseau", "Proximité des dorsales fibre nationales et des stations d'atterrissement des câbles sous-marins du nord du pays"],
    ["4", "Climat", "Étés chauds (> 40 °C) : le froid est dimensionné pour ces pointes ; hivers doux : le free cooling est possible une partie de l'année"],
    ["5", "Proximité des équipes", "Bassin d'ingénieurs et d'entreprises IT (écoles, technopôle d'El Ghazala)"],
  ], [1100, 2300, 6238], "Critères de localisation appliqués au scénario"),
  p("Ce choix est un scénario et non une étude de site réelle. Il explique le paysage sec qui entoure le campus dans nos rendus : seule la pelouse à l'intérieur de la clôture est irriguée."),
);

// 5 Architecture
C.push(H1("5. Architecture générale du campus"),
  H2("5.1 Plan de masse"),
  p("Le campus occupe une parcelle clôturée d'environ **280 × 190 m**. Le plan ci-dessous est généré directement à partir des coordonnées de la maquette 3D ; il correspond donc exactement au modèle Blender."),
  ...figure("fig/plan_masse.png", "Plan de masse du campus"),
  H2("5.2 Principes d'implantation"),
  bullet("**Séparation des risques.** Le bâtiment technique (carburant, batteries, transformateurs) est séparé de la salle blanche. Seule une passerelle couverte les relie, pour les câbles et les tuyauteries."),
  bullet("**Énergie au plus court.** Le poste haute tension est placé sur la limite est, au plus près des lignes. Les groupes électrogènes et les cuves sont juste à côté du bâtiment technique."),
  bullet("**Personnel séparé des équipements.** Le bâtiment logistique est proche de l'entrée ; le personnel y travaille sans traverser les zones sécurisées. Un couloir vitré le relie au bâtiment informatique."),
  bullet("**Une seule entrée.** Tout véhicule passe par le poste de garde. Le parking est à l'intérieur de la clôture mais à côté de l'entrée, pour que les visiteurs ne circulent pas près des bâtiments."),
  bullet("**Livraisons côté nord.** Les quais de livraison du bâtiment informatique donnent sur la voie de ceinture nord, à l'écart des flux du personnel."),
);

// 6 IT
C.push(H1("6. Le bâtiment informatique"),
  ...table(["Élément", "Caractéristique"], [
    ["Emprise", "70 × 40 m, hauteur 11 m"],
    ["Enveloppe", "Bardage graphite sans fenêtres (sécurité, pas d'apport solaire), ailettes en aluminium, lignes LED cyan"],
    ["Salle blanche", "≈ 1 500 m², ≈ 200 baies en allées chaudes et froides confinées"],
    ["Autres salles (phase 3)", "Salle d'arrivée des opérateurs (meet-me room), stockage, local de préparation"],
    ["Toiture", "21 aéroréfrigérants (dry coolers) en trois rangées et tuyauteries d'eau glacée"],
    ["Façade nord", "4 portes de quai de livraison"],
  ], [2800, 6838], "Caractéristiques du bâtiment informatique"),
  p("L'absence de fenêtres n'est pas qu'un choix esthétique : elle supprime une voie d'intrusion, évite les apports de chaleur solaire et facilite le contrôle de la poussière dans la salle blanche. Les lignes LED et le bardage sombre donnent au bâtiment son identité « technologique »."),
  ...figure("img/04_Power_Feed.jpg", "Bâtiment informatique et bâtiment technique vus depuis les lignes haute tension"),
);

// 7 Technique
C.push(H1("7. Le bâtiment technique : énergie et froid"),
  p("Le bâtiment technique (36 × 30 m) concentre tout ce qui fait vivre la salle blanche : distribution électrique, onduleurs et production de froid. À l'extérieur se trouvent les groupes électrogènes, les cuves de carburant et le poste haute tension."),
  H2("7.1 Continuité électrique (E1)"),
  p("L'alimentation suit **deux voies complètement indépendantes, A et B**, de la ligne haute tension jusqu'à la baie. Chaque serveur possède deux alimentations, l'une branchée sur la voie A, l'autre sur la voie B. La perte d'une voie entière n'interrompt donc aucun équipement."),
  ...figure("fig/alimentation.png", "Chaîne d'alimentation électrique à deux voies"),
  H3("Dimensionnement"),
  ...table(["Équipement", "Choix", "Justification"], [
    ["Arrivées HT", "2 lignes indépendantes (A et B)", "Une ligne peut tomber ou être maintenue sans coupure"],
    ["Transformateurs", "TR-A et TR-B, 2,5 MVA chacun", "Un seul transformateur alimente tout le site (≈ 1,8 MVA)"],
    ["Groupes électrogènes", "6 × 500 kVA (400 kW), N+1", "5 × 400 kW = 2 MW > 1,45 MW ; le 6ème est en secours"],
    ["Carburant", "2 cuves de 50 m³ dans un bac de rétention", "≈ 275 h d'autonomie (voir calcul)"],
    ["Onduleurs", "2 systèmes (A, B) de 5 × 250 kW, N+1", "Chaque système porte seul 1 MW IT"],
    ["Batteries", "≈ 10 minutes d'autonomie", "Couvre largement le démarrage des groupes (< 15 s)"],
  ], [2300, 3400, 3938], "Dimensionnement de la chaîne électrique"),
  H3("Autonomie en carburant"),
  p("Un groupe diesel consomme environ 0,25 L par kWh produit. À pleine charge (1 450 kW), la consommation est de 0,25 × 1 450 ≈ **360 L/h**. Avec 100 000 L stockés sur site, l'autonomie est de 100 000 / 360 ≈ **275 heures, soit environ 11 jours**. C'est bien au-delà des 12 heures généralement exigées pour le Tier III, et laisse le temps d'organiser des livraisons de carburant pendant une coupure prolongée."),
  H3("Scénario de coupure"),
  numbered("La ligne A tombe : la voie B continue d'alimenter tous les serveurs. Aucun impact."),
  numbered("Les deux lignes tombent : les onduleurs prennent le relais instantanément grâce aux batteries."),
  numbered("En moins de 15 secondes, les inverseurs de source (ATS) démarrent les groupes électrogènes, qui reprennent la charge."),
  numbered("Si un groupe est en panne, le groupe de secours (N+1) le remplace."),
  numbered("Au retour du réseau, la charge est retransférée sans coupure et les groupes s'arrêtent."),
  H2("7.2 Maîtrise du froid (E2)"),
  p("Presque toute l'électricité consommée par les serveurs se transforme en chaleur : environ 1 MW doit être évacué en permanence. La chaîne de froid transporte cette chaleur de la baie jusqu'à l'air extérieur."),
  ...figure("fig/refroidissement.png", "Chaîne de refroidissement"),
  bullet("**Allées chaudes et froides.** Les baies sont disposées face à face (allée froide) et dos à dos (allée chaude). Le confinement des allées empêche le mélange de l'air chaud et de l'air froid : c'est le gain d'efficacité le moins coûteux d'un data center."),
  bullet("**Armoires CRAH (N+1).** Elles soufflent l'air froid (20–25 °C) et reprennent l'air chaud en le faisant passer sur des batteries d'eau glacée."),
  bullet("**Groupes froids : 4 × 400 kW (3 + 1)** en toiture du bâtiment technique. Trois suffisent à évacuer la chaleur ; le quatrième est en secours."),
  bullet("**Free cooling : 21 aéroréfrigérants** en toiture du bâtiment informatique. Lorsque l'air extérieur est assez frais (nuits d'hiver), ils refroidissent l'eau seuls et les groupes froids s'arrêtent, ce qui réduit le PUE."),
  p("En Tunisie, le free cooling n'est possible qu'une partie de l'année. Les groupes froids restent donc indispensables et sont dimensionnés pour les journées à plus de 40 °C."),
  ...figure("img/01_Hero_SouthEast.jpg", "Bâtiment technique, groupes électrogènes G1 à G6 et cuves de carburant"),
);

// 8 Logistique
C.push(H1("8. Le bâtiment logistique et le NOC"),
  p("Le bâtiment logistique (44 × 22 m, trois niveaux) accueille le personnel. Contrairement au bâtiment informatique, il est largement vitré : c'est un lieu de travail, pas une zone sensible. Des panneaux solaires couvrent sa toiture."),
  p("Son extrémité ouest forme un bloc plein et sans fenêtre : le **NOC** (Network Operations Center). Les équipes y surveillent en temps réel la performance, la sécurité et les conditions environnementales du site (température, humidité, consommation). L'absence de fenêtres protège les écrans des reflets et limite les regards extérieurs."),
  ...table(["Espace", "Fonction"], [
    ["NOC", "Supervision 24 h/24 : réseau, énergie, froid, alarmes, vidéosurveillance"],
    ["Bureaux", "Équipes d'exploitation, d'ingénierie et d'administration"],
    ["Salles de réunion", "Réunions internes et accueil des clients"],
    ["Salles de pause", "Espaces de repos du personnel"],
  ], [2800, 6838], "Espaces du bâtiment logistique"),
  ...figure("img/05_Logistique_NOC.jpg", "Bâtiment logistique et bloc NOC"),
);

// 9 Sécurité
C.push(H1("9. Sécurité physique (E3)"),
  p("La sécurité repose sur le principe de **défense en profondeur** : pour atteindre un serveur, il faut franchir successivement plusieurs zones, chacune ajoutant un contrôle, et chaque passage est enregistré."),
  ...figure("fig/securite.png", "Zonage de sécurité physique", 520),
  ...table(["Dispositif", "Mise en œuvre dans la maquette"], [
    ["Clôture périmétrique", "3 m de haut, sur tout le pourtour du site"],
    ["Entrée unique", "Poste de garde, barrière d'entrée et barrière de sortie"],
    ["Protection anti-véhicule", "Bornes anti-bélier devant l'entrée"],
    ["Vidéosurveillance", "10 mâts CCTV de 7 m : angles de la clôture, entrée, poste HT, zone des groupes, accès aux bâtiments"],
    ["Contrôle d'accès (phase 3)", "Badges nominatifs, sas, biométrie pour la salle blanche et les salles techniques"],
  ], [3000, 6638], "Dispositifs de sécurité physique"),
  ...figure("img/02_Entrance_Gate.jpg", "Entrée sécurisée du site : poste de garde, barrières et bornes anti-bélier"),
);

// 10 Enjeux
C.push(H1("10. Réponse aux enjeux critiques"),
  p("Le tableau suivant résume, pour chaque enjeu du cours, les choix qui y répondent :"),
  ...table(["Enjeu", "Réponses apportées"], [
    ["E1 – Continuité électrique", "Deux arrivées HT indépendantes, deux transformateurs, 6 groupes électrogènes N+1, ≈ 11 jours de carburant, deux systèmes d'onduleurs avec batteries, double alimentation de chaque baie"],
    ["E2 – Maîtrise du froid", "Allées chaudes et froides confinées, armoires CRAH N+1, 4 groupes froids (3 + 1), 21 aéroréfrigérants avec free cooling, consigne 20–25 °C"],
    ["E3 – Sécurisation", "Cinq zones de sécurité, entrée unique gardée, bornes anti-bélier, 10 caméras, bâtiment IT sans fenêtres, NOC dédié"],
    ["E4 – Haute disponibilité", "Tier III : chaque composant a un secours (N+1) et deux chemins de distribution ; tout équipement peut être maintenu sans arrêt"],
  ], [2800, 6838], "Correspondance entre enjeux et choix de conception"),
);

// 11 Blender
C.push(H1("11. Modélisation 3D sous Blender"),
  H2("11.1 Objectifs et outil"),
  p("La maquette 3D a trois objectifs : **valider** la cohérence de l'implantation (proportions, circulations), **communiquer** la conception à l'aide d'images et d'une vidéo, et **servir de base** aux phases suivantes (intérieurs)."),
  p("Nous avons choisi **Blender 5.2**, logiciel libre et gratuit, pour deux raisons principales : il produit des rendus photoréalistes et il est entièrement programmable en Python. Blender a été piloté par l'assistant IA Claude, connecté à Blender par le protocole MCP (Model Context Protocol) : chaque élément du campus a été créé par des scripts plutôt qu'à la main."),
  H2("11.2 Méthode : modélisation procédurale"),
  p("Au lieu de modéliser chaque objet à la souris, nous avons écrit une petite bibliothèque Python, **dc_lib.py**, qui fournit des fonctions de base : box (parallélépipède), cyl (cylindre), beam (poutre entre deux points), text, join. Chaque bâtiment est ensuite décrit par un script à partir de ses dimensions réelles, en mètres."),
  p("Cette approche présente trois avantages :"),
  bullet("**Précision** : toutes les cotes du rapport proviennent directement du modèle."),
  bullet("**Reproductibilité** : le campus peut être régénéré ou modifié en changeant un paramètre (par exemple le nombre de groupes électrogènes)."),
  bullet("**Rapidité** : un pylône haute tension en treillis de plus de 100 barres est généré par une seule fonction."),
  H2("11.3 Organisation de la scène"),
  ...table(["Collection", "Contenu"], [
    ["00_Site", "Terrain, pelouse, routes, dalles, relief"],
    ["01_Batiment_Informatique", "Bâtiment IT, ailettes, LED, enseigne, quais, aéroréfrigérants"],
    ["02_Batiment_Technique", "Bâtiment technique, persiennes, groupes froids, passerelle"],
    ["03_Energie", "Groupes électrogènes, cuves, transformateurs, portiques, pylônes, câbles HT"],
    ["04_Batiment_Logistique", "Bâtiment vitré, bloc NOC, auvent, panneaux solaires"],
    ["05_Parking", "Parking, ombrières solaires, bornes de recharge, véhicules"],
    ["06_Securite", "Clôture, poste de garde, barrières, bornes, caméras"],
    ["07_Paysage", "Arbres, éclairage public, nuages"],
    ["08_Lumieres_Cameras", "Soleil et caméras"],
  ], [3200, 6438], "Organisation de la scène Blender (336 objets, 52 matériaux)"),
  H2("11.4 Réalisme du rendu"),
  p("Une seconde passe a été consacrée au photoréalisme :"),
  bullet("**Moteur Cycles** (lancer de rayons physique) sur la carte graphique RTX 2050 via OptiX, 160 échantillons et débruitage. Chaque image en 1920 × 1080 prend 3 à 5 minutes."),
  bullet("**Matériaux procéduraux**, générés par des textures mathématiques (bruit, Voronoï, briques) sans aucune image : asphalte granuleux, béton avec joints, bardage en panneaux, acier nervuré, aluminium brossé, peinture des groupes avec salissures, vitrages, cellules solaires, peinture automobile vernie."),
  bullet("**Végétation** : environ 120 000 touffes d'herbe dispersées par Geometry Nodes, avec un lancer de rayons qui empêche l'herbe de pousser sur les routes ; herbe sèche à l'extérieur du site, arbres aux feuillages irréguliers."),
  bullet("**Environnement** : collines générées à l'horizon, couche de nuages, ciel physique et soleil de fin d'après-midi projetant des ombres réelles."),
  bullet("**Post-traitement** : lueur (bloom) des LED et légère dispersion optique, gestion des couleurs AgX."),
  H2("11.5 Rendus"),
  ...figure("img/03_Aerial.jpg", "Vue aérienne du campus"),
  H2("11.6 Vidéo de survol par drone"),
  p("Une vidéo de **34 secondes** (1 020 images, 30 images/s, 1920 × 1080) simule le vol d'un drone qui présente chaque partie du site, puis s'élève pour révéler le campus entier. La caméra suit une cible animée par courbes de Bézier. Un léger bruit ajouté au mouvement reproduit les micro-vibrations d'un vrai drone, et le flou de mouvement est activé. Pour tenir des délais raisonnables, la vidéo est rendue avec le moteur **EEVEE** (≈ 10 s par image, soit environ 3 heures au total) plutôt qu'avec Cycles, qui aurait demandé plusieurs dizaines d'heures."),
  ...table(["Temps", "Séquence"], [
    ["0 – 3 s", "Vol à basse altitude au-dessus du terrain naturel, approche de la route et de l'entrée"],
    ["3 – 7,5 s", "Survol du poste de garde et du parking, vers le bâtiment logistique"],
    ["7,5 – 11,7 s", "Contournement du bâtiment logistique et du NOC"],
    ["11,7 – 16,5 s", "Travelling le long de la façade LED du bâtiment informatique, montée au-dessus des toitures"],
    ["16,5 – 21,5 s", "Descente sur les groupes électrogènes G1 à G6 et les cuves de carburant"],
    ["21,5 – 26,5 s", "Poste haute tension et départ des lignes A et B"],
    ["26,5 – 34 s", "Prise de recul : vue générale en hauteur du campus complet"],
  ], [1900, 7738], "Découpage de la vidéo de survol"),
);

// 12 Gestion de projet
C.push(H1("12. Gestion de projet et outillage"),
  H2("12.1 Organisation des fichiers"),
  p("Tout le projet est rassemblé dans un dossier racine unique, organisé en dossiers numérotés :"),
  ...table(["Dossier", "Contenu"], [
    ["00_Docs", "Supports de cours et documents de référence"],
    ["01_Planning", "Plan de projet, hypothèses, décisions"],
    ["02_Blender", "Scènes (versions v01 à v04), scripts, textures, rendus et vidéo"],
    ["03_Network", "Projets GNS3, plan d'adressage (phase 4)"],
    ["04_Code", "Scripts d'automatisation et de configuration"],
    ["05_Report", "Rapport et présentation"],
    ["06_Documentation", "Documentation technique : décisions d'architecture, guide Blender, workflow Git, feuille de route"],
  ], [2600, 7038], "Arborescence du projet"),
  H2("12.2 Versionnement avec Git"),
  p("Le dossier est un dépôt **Git**, hébergé sur un dépôt **GitHub privé** partagé par l'équipe. Les fichiers volumineux (scènes .blend, images, vidéo, documents Office) sont gérés par **Git LFS** (Large File Storage), ce qui garde le dépôt léger. Les fichiers temporaires (sauvegardes automatiques de Blender, images de la séquence vidéo, disques des machines virtuelles GNS3) sont exclus par le fichier .gitignore."),
  p("Chaque session de travail se termine par un commit au message explicite (par exemple « blender: v03 photoreal pass »). Les scènes gardent un numéro de version dans leur nom, ce qui permet de revenir à n'importe quelle étape."),
);

// 13 Limites & perspectives
C.push(H1("13. Limites et perspectives"),
  H2("13.1 Limites"),
  bullet("Les puissances et capacités sont des **hypothèses** cohérentes, pas le résultat d'une étude d'ingénierie détaillée (calcul des sections de câbles, bilan thermique pièce par pièce, étude de sol…)."),
  bullet("La localisation est un **scénario** : aucune étude de site réelle n'a été menée."),
  bullet("La maquette représente l'extérieur ; les intérieurs ne sont pas encore modélisés."),
  bullet("Certaines proportions sont simplifiées pour la lisibilité visuelle (par exemple la taille des cuves de carburant)."),
  H2("13.2 Prochaines étapes"),
  bullet("**Phase 3 – Intérieurs** : salle blanche avec faux plancher, ≈ 200 baies en allées confinées, armoires CRAH et chemins de câbles ; salles TGBT et onduleurs ; NOC avec mur d'images."),
  bullet("**Phase 4 – Réseau sous GNS3** : architecture spine-leaf redondante (deux spines, paires de leafs, serveurs raccordés en double), deux routeurs de bordure et deux opérateurs (BGP), pare-feux en haute disponibilité, segmentation (administration, production, stockage, DMZ, sauvegarde), plan d'adressage, tests de bascule."),
  bullet("**Phase 5 – Services** : DNS, DHCP, NTP, AAA, journalisation, supervision depuis le NOC, plan de sauvegarde et de reprise d'activité."),
);

// 14 Conclusion
C.push(H1("14. Conclusion"),
  p("Au terme de ces deux premières phases, nous disposons d'une conception complète et justifiée du site. C'est un data center **Tier III** d'environ **1 MW**, organisé en trois bâtiments, dans lequel chaque choix répond à un enjeu critique du cours. La redondance N+1 et les deux voies électriques garantissent la continuité et la haute disponibilité. La chaîne de froid, avec free cooling, maîtrise la température. La défense en profondeur protège les équipements."),
  p("La maquette 3D photoréaliste, les cinq rendus et la vidéo de survol rendent cette conception concrète et présentable. Grâce à la modélisation procédurale, la maquette reste modifiable. Le dépôt Git et la documentation technique fournissent une base solide pour les phases suivantes : l'aménagement intérieur, puis la conception du réseau sous GNS3."),
);

// Annexes
C.push(H1("Annexe A – Glossaire"),
  ...table(["Terme", "Définition"], [
    ["ATS", "Automatic Transfer Switch – inverseur de source qui bascule automatiquement vers les groupes électrogènes"],
    ["CRAH", "Computer Room Air Handler – armoire de climatisation à eau glacée de la salle informatique"],
    ["Dry cooler", "Aéroréfrigérant : échangeur qui refroidit l'eau avec l'air extérieur"],
    ["Free cooling", "Refroidissement utilisant l'air extérieur frais, sans groupe froid"],
    ["N+1", "Redondance : N équipements nécessaires plus un en secours"],
    ["2N", "Redondance totale : deux fois les équipements nécessaires"],
    ["NOC", "Network Operations Center – centre de supervision"],
    ["PDU", "Power Distribution Unit – distribution électrique dans la baie"],
    ["PUE", "Power Usage Effectiveness – énergie totale du site / énergie IT"],
    ["TGBT", "Tableau Général Basse Tension"],
    ["Tier", "Niveau de disponibilité défini par l'Uptime Institute (I à IV)"],
    ["UPS / Onduleur", "Alimentation sans interruption, avec batteries"],
    ["Git LFS", "Extension de Git pour stocker efficacement les fichiers volumineux"],
    ["Geometry Nodes", "Système de génération procédurale de géométrie dans Blender"],
  ], [2200, 7438]),
  new Paragraph({ heading: HeadingLevel.HEADING_1, children: [t("Annexe B – Dimensions principales")] }),
  ...table(["Élément", "Dimensions / position (m)"], [
    ["Site clôturé", "276 × 186"],
    ["Bâtiment informatique", "70 × 40 × 11, centre (5 ; 20)"],
    ["Bâtiment technique", "36 × 30 × 10, centre (73 ; 27)"],
    ["Bâtiment logistique", "44 × 22 × 13,2 (3 niveaux), centre (−40 ; −18)"],
    ["Bloc NOC", "12 × 23 × 14, centre (−68 ; −18)"],
    ["Groupes électrogènes", "6 unités de 3,6 × 12 × 3,8"],
    ["Poste HT", "26 × 56, centre (122 ; 15)"],
    ["Pylônes HT", "Hauteur 43 m, 4 par ligne"],
    ["Parking", "60 × 40, ≈ 80 places"],
  ], [3600, 6038]),
  new Paragraph({ spacing: { before: 200 }, children: [t("Source : maquette Blender DC_Exterior_v04.blend. Axe X vers l'est, axe Y vers le nord, origine au centre du campus.", { italics: true, size: 18, color: MUTED })] }),
);

const doc = new Document({
  creator: "Mohamed Ben Naima", title: "Conception d'un Data Center – Phases 1 et 2", language: "fr-FR",
  styles: {
    default: { document: { run: { font: FONT, size: 22, color: INK } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 34, bold: true, font: FONT, color: DARK }, paragraph: { spacing: { before: 240, after: 200 }, outlineLevel: 0,
          border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: ACCENT, space: 4 } } } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 27, bold: true, font: FONT, color: ACCENT }, paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 1, keepNext: true } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 23, bold: true, font: FONT, color: DARK }, paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 2, keepNext: true } },
    ],
  },
  numbering: { config: [
    { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
    { reference: "num", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 540, hanging: 300 } } } }] },
  ] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } }, titlePage: true },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
      children: [t("ESPRIM Data Center – Rapport de conception (phases 1 et 2)", { size: 16, color: MUTED })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [t("Page ", { size: 16, color: MUTED }), new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: MUTED }),
        t(" / ", { size: 16, color: MUTED }), new TextRun({ children: [PageNumber.TOTAL_PAGES], font: FONT, size: 16, color: MUTED })] })] }) },
    children: C,
  }],
});
Packer.toBuffer(doc).then(b => { fs.writeFileSync("Rapport_Conception_DataCenter_Phases1-2.docx", b); console.log("written", b.length); });
