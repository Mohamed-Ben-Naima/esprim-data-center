// Builds ../Rapport_Reseau_GNS3_DC_Casablanca.docx from ../content/*.md (French network report).
// Same visual language as 05_Report/_source/build.js (Calibri, teal accent, dark table headers).
//
// Markdown subset understood:
//   # H1 (new page, auto-numbered)  ## H2  ### H3      "{-}" at the end of a heading = unnumbered
//   paragraphs, **bold**, *italic*, `code`               - bullet (2-space indent = level 2), 1. numbered
//   Table: <caption>  (line right before a pipe table)   | a | b |  pipe tables (first row = header)
//   ![caption](path){width=600}                          figure, path relative to report/
//   > [!NOTE|INFO|OK|WARN|DEV] Title  + "> text" lines   callout box
//   ```lang title="..."  ...  ```                        code / config block
//   @include path/to/file.md                             include (generated tables)
//   ---pagebreak---
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, ImageRun, Table, TableRow, TableCell,
  WidthType, ShadingType, BorderStyle, LevelFormat, TableOfContents, Header, Footer, PageNumber, PageBreak,
  VerticalAlign, TabStopType,
} = require("docx");

const ROOT = path.resolve(__dirname, "..");            // 03_Network/report
const CONTENT = path.join(ROOT, "content");
const OUT = path.join(ROOT, "Rapport_Reseau_GNS3_DC_Casablanca.docx");

const FONT = "Calibri", MONO = "Consolas";
const INK = "1F2328", ACCENT = "00838F", MUTED = "5B6168", DARK = "23272E", ZEBRA = "F4F6F8", RULE = "C9CDD2";
const W = 9638; // A4 content width (DXA) with 2 cm margins
const CALLOUT = {
  NOTE: { fill: "E8F4F5", bar: ACCENT, label: "À retenir" },
  INFO: { fill: "EEF2F8", bar: "3B6EA8", label: "Information" },
  OK:   { fill: "EAF5EC", bar: "2E7D32", label: "Validé" },
  WARN: { fill: "FFF6E5", bar: "C77700", label: "Attention" },
  DEV:  { fill: "F3EEF8", bar: "6A4C93", label: "Écart par rapport à la conception" },
};

// ---------------------------------------------------------------- inline text
const t = (text, o = {}) => new TextRun({ text, font: FONT, ...o });
function inline(s, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)/g;
  let last = 0, m;
  while ((m = re.exec(s))) {
    if (m.index > last) out.push(t(s.slice(last, m.index), base));
    const seg = m[0];
    if (seg.startsWith("**")) out.push(t(seg.slice(2, -2), { ...base, bold: true }));
    else if (seg.startsWith("`")) out.push(new TextRun({ text: seg.slice(1, -1), font: MONO, size: 18, color: "0B5560", ...base.mono }));
    else out.push(t(seg.slice(1, -1), { ...base, italics: true }));
    last = m.index + seg.length;
  }
  if (last < s.length) out.push(t(s.slice(last), base));
  return out;
}

// ---------------------------------------------------------------- numbering state
let h1 = 0, h2 = 0, h3 = 0, figN = 0, tabN = 0;
function heading(level, raw) {
  let text = raw.trim(), numbered = true;
  if (text.endsWith("{-}")) { numbered = false; text = text.slice(0, -3).trim(); }
  if (/^annexe/i.test(text)) numbered = false;
  let label = text;
  if (numbered) {
    if (level === 1) { h1++; h2 = 0; h3 = 0; label = `${h1}. ${text}`; }
    if (level === 2) { h2++; h3 = 0; label = `${h1}.${h2} ${text}`; }
    if (level === 3) { h3++; label = `${h1}.${h2}.${h3} ${text}`; }
  }
  const hl = [HeadingLevel.HEADING_1, HeadingLevel.HEADING_2, HeadingLevel.HEADING_3][level - 1];
  return new Paragraph({ heading: hl, pageBreakBefore: level === 1, keepNext: true, children: [t(label)] });
}

// ---------------------------------------------------------------- blocks
const border = { style: BorderStyle.SINGLE, size: 4, color: RULE };
const borders = { top: border, bottom: border, left: border, right: border };
const none = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };

function caption(kind, n, text) {
  return new Paragraph({ alignment: kind === "Figure" ? AlignmentType.CENTER : AlignmentType.LEFT,
    spacing: kind === "Figure" ? { after: 220 } : { before: 160, after: 80 }, keepNext: kind !== "Figure",
    children: [t(`${kind} ${n} – `, { bold: true, size: 18, color: MUTED }), t(text, { italics: true, size: 18, color: MUTED })] });
}

function table(rows, cap) {
  const head = rows[0], body = rows.slice(1), n = head.length;
  // column widths proportional to content length (bounded), summing to W
  const len = head.map((h, i) => Math.min(48, Math.max(6, ...rows.map(r => (r[i] || "").replace(/[*`]/g, "").length))));
  const tot = len.reduce((a, b) => a + b, 0);
  const widths = len.map(l => Math.floor(W * l / tot));
  widths[n - 1] += W - widths.reduce((a, b) => a + b, 0);
  const small = n >= 6 ? 16 : 18;
  const cell = (txt, i, isHead, zebra) => new TableCell({
    borders, width: { size: widths[i], type: WidthType.DXA }, verticalAlign: VerticalAlign.CENTER,
    shading: isHead ? { fill: DARK, type: ShadingType.CLEAR, color: "auto" } : zebra ? { fill: ZEBRA, type: ShadingType.CLEAR, color: "auto" } : undefined,
    margins: { top: 50, bottom: 50, left: 90, right: 90 },
    children: [new Paragraph({ spacing: { after: 0, line: 252 },
      children: isHead ? [t(txt, { bold: true, color: "FFFFFF", size: small })] : inline(txt, { size: small }) })],
  });
  const out = [];
  if (cap) { tabN++; out.push(caption("Tableau", tabN, cap)); }
  out.push(new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: widths,
    rows: [new TableRow({ tableHeader: true, cantSplit: true, children: head.map((h, i) => cell(h, i, true)) }),
      ...body.map((r, ri) => new TableRow({ cantSplit: true, children: head.map((_, i) => cell(r[i] || "", i, false, ri % 2 === 1)) }))] }),
    new Paragraph({ spacing: { after: 160 }, children: [] }));
  return out;
}

function imageSize(buf, file) {
  if (file.endsWith(".png")) return [buf.readUInt32BE(16), buf.readUInt32BE(20)];
  let i = 2;
  while (i < buf.length) {
    if (buf[i] !== 0xFF) { i++; continue; }
    const m = buf[i + 1], l = buf.readUInt16BE(i + 2);
    if (m >= 0xC0 && m <= 0xC3) return [buf.readUInt16BE(i + 7), buf.readUInt16BE(i + 5)];
    i += 2 + l;
  }
  return [800, 600];
}
function figure(rel, cap, widthPx = 620) {
  const file = path.resolve(ROOT, rel);
  if (!fs.existsSync(file)) {
    return [callout("WARN", "Figure manquante", `\`${rel}\` – sera ajoutée lors de la sous-tâche correspondante.`)];
  }
  const buf = fs.readFileSync(file);
  const [w, h] = imageSize(buf, file);
  const width = Math.min(widthPx, 640), height = Math.round(width * h / w);
  figN++;
  return [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 }, keepNext: true,
      children: [new ImageRun({ type: file.endsWith(".png") ? "png" : "jpg", data: buf, transformation: { width, height },
        altText: { title: cap, description: cap, name: `fig${figN}` } })] }),
    caption("Figure", figN, cap)];
}

function callout(kind, title, text) {
  const k = CALLOUT[kind] || CALLOUT.NOTE;
  const paras = [new Paragraph({ spacing: { after: 60 }, children: [t(title || k.label, { bold: true, color: k.bar })] })];
  const items = [];
  for (const line of text.split("\n")) {
    const b = line.match(/^\s*-\s+(.*)/);
    if (!line.trim()) items.push(null);
    else if (b) items.push({ bullet: true, text: b[1] });
    else if (items.length && items[items.length - 1]) items[items.length - 1].text += " " + line.trim();
    else items.push({ bullet: false, text: line.trim() });
  }
  for (const it of items.filter(Boolean)) {
    paras.push(it.bullet ? new Paragraph({ numbering: { reference: "bul", level: 0 }, spacing: { after: 30, line: 268 }, children: inline(it.text) })
                         : new Paragraph({ spacing: { after: 40, line: 276 }, children: inline(it.text) }));
  }
  return new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [W], rows: [new TableRow({ cantSplit: true, children: [
    new TableCell({ width: { size: W, type: WidthType.DXA }, borders: { top: none, bottom: none, right: none, left: { style: BorderStyle.SINGLE, size: 24, color: k.bar } },
      shading: { fill: k.fill, type: ShadingType.CLEAR, color: "auto" }, margins: { top: 110, bottom: 110, left: 200, right: 200 },
      children: paras })] })] });
}

function codeBlock(lines, title) {
  const paras = [];
  if (title) paras.push(new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: title, font: FONT, bold: true, size: 17, color: "9FE3EA" })] }));
  for (const l of lines) paras.push(new Paragraph({ spacing: { after: 0, line: 228 },
    children: [new TextRun({ text: l.length ? l : " ", font: MONO, size: 16, color: "E6EDF3" })] }));
  return [new Table({ width: { size: W, type: WidthType.DXA }, columnWidths: [W], rows: [new TableRow({ children: [
    new TableCell({ width: { size: W, type: WidthType.DXA }, borders: { top: none, bottom: none, left: none, right: none },
      shading: { fill: "1E242C", type: ShadingType.CLEAR, color: "auto" }, margins: { top: 100, bottom: 100, left: 160, right: 160 },
      children: paras })] })] }), new Paragraph({ spacing: { after: 140 }, children: [] })];
}

// ---------------------------------------------------------------- markdown -> blocks
function readWithIncludes(file, depth = 0) {
  const txt = fs.readFileSync(file, "utf8").replace(/\r\n/g, "\n");
  return txt.split("\n").flatMap(line => {
    const m = line.match(/^@include\s+(.+)$/);
    if (!m || depth > 5) return [line];
    const inc = path.resolve(path.dirname(file), m[1].trim());
    return fs.existsSync(inc) ? readWithIncludes(inc, depth + 1)
      : [`> [!WARN] Contenu généré manquant`, `> \`${m[1].trim()}\` n'existe pas encore.`];
  });
}

// a wrapped line continues the previous bullet unless it starts a new block
const BLOCK = /^(#{1,3}\s|[-*]\s+|\d+\.\s+|>|```|!\[|Table:|\||@include|---pagebreak---|<!--)/;
const isContinuation = (l) => l.trim() !== "" && !BLOCK.test(l.trimStart());

function render(lines) {
  const out = [];
  let i = 0, pendingCaption = null, para = [];
  const flush = () => { if (para.length) { out.push(new Paragraph({ spacing: { after: 120, line: 288 }, alignment: AlignmentType.JUSTIFIED, children: inline(para.join(" ")) })); para = []; } };
  while (i < lines.length) {
    const line = lines[i];
    let m;
    if (!line.trim()) { flush(); i++; continue; }
    if (line.startsWith("<!--")) { while (i < lines.length && !lines[i].includes("-->")) i++; i++; continue; }
    if ((m = line.match(/^(#{1,3})\s+(.*)/))) { flush(); out.push(heading(m[1].length, m[2])); i++; continue; }
    if (line.trim() === "---pagebreak---") { flush(); out.push(new Paragraph({ children: [new PageBreak()] })); i++; continue; }
    if ((m = line.match(/^Table:\s*(.*)/))) { flush(); pendingCaption = m[1]; i++; continue; }
    if (line.trim().startsWith("|")) {
      flush();
      const rows = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        const cells = lines[i].trim().replace(/^\||\|$/g, "").split("|").map(c => c.trim());
        if (!cells.every(c => /^:?-{2,}:?$/.test(c))) rows.push(cells);
        i++;
      }
      out.push(...table(rows, pendingCaption)); pendingCaption = null; continue;
    }
    if ((m = line.match(/^!\[(.*)\]\((.+?)\)(\{width=(\d+)\})?/))) { flush(); out.push(...figure(m[2], m[1], m[4] ? +m[4] : 620)); i++; continue; }
    if ((m = line.match(/^>\s*\[!(\w+)\]\s*(.*)/))) {
      flush(); const kind = m[1].toUpperCase(), title = m[2]; const body = []; i++;
      while (i < lines.length && lines[i].startsWith(">")) { body.push(lines[i].replace(/^>\s?/, "")); i++; }
      out.push(callout(kind, title, body.join("\n")), new Paragraph({ spacing: { after: 120 }, children: [] })); continue;
    }
    if ((m = line.match(/^```(\w*)\s*(?:title="([^"]*)")?/))) {
      flush(); const code = []; i++;
      while (i < lines.length && !lines[i].startsWith("```")) { code.push(lines[i]); i++; }
      i++; out.push(...codeBlock(code, m[2])); continue;
    }
    if ((m = line.match(/^(\s*)[-*]\s+(.*)/))) {
      flush(); const lvl = m[1].length >= 2 ? 1 : 0; let txt = m[2]; i++;
      while (i < lines.length && isContinuation(lines[i])) { txt += " " + lines[i].trim(); i++; }
      out.push(new Paragraph({ numbering: { reference: "bul", level: lvl }, spacing: { after: 50, line: 276 }, children: inline(txt) })); continue;
    }
    if ((m = line.match(/^\d+\.\s+(.*)/))) {
      flush(); let txt = m[1]; i++;
      while (i < lines.length && isContinuation(lines[i])) { txt += " " + lines[i].trim(); i++; }
      out.push(new Paragraph({ numbering: { reference: "num", level: 0 }, spacing: { after: 50, line: 276 }, children: inline(txt) })); continue;
    }
    para.push(line.trim()); i++;
  }
  flush();
  return out;
}

// ---------------------------------------------------------------- document
const files = fs.readdirSync(CONTENT).filter(f => /^\d\d_.*\.md$/.test(f)).sort();
const meta = JSON.parse(fs.readFileSync(path.join(CONTENT, "meta.json"), "utf8"));
const resume = files.find(f => f.startsWith("00_"));
const chapters = files.filter(f => f !== resume);

const today = new Date().toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });
const cover = [
  new Paragraph({ spacing: { before: 200, after: 0 }, children: [t("ESPRIM", { bold: true, size: 26, color: ACCENT })] }),
  new Paragraph({ spacing: { after: 700 }, children: [t(meta.module, { size: 22, color: MUTED })] }),
  new Paragraph({ spacing: { after: 120 }, children: [t(meta.title, { bold: true, size: 52, color: INK })] }),
  new Paragraph({ spacing: { after: 300 }, children: [t(meta.subtitle, { size: 28, color: ACCENT })] }),
  ...(meta.cover_image ? figure(meta.cover_image, meta.cover_caption, 600) : []),
  new Paragraph({ spacing: { before: 400, after: 80 }, children: [t("Réalisé par : ", { bold: true }), t(meta.author)] }),
  new Paragraph({ spacing: { after: 80 }, children: [t("Encadré par : ", { bold: true }), t(meta.supervisor)] }),
  new Paragraph({ spacing: { after: 80 }, children: [t("Année universitaire : ", { bold: true }), t(meta.year)] }),
  new Paragraph({ spacing: { after: 80 }, children: [t("Version : ", { bold: true }), t(`${meta.version} – générée le ${today}`)] }),
];

const body = [
  ...(resume ? render(readWithIncludes(path.join(CONTENT, resume))) : []),
  new Paragraph({ pageBreakBefore: true, spacing: { after: 240 }, border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: ACCENT, space: 6 } },
    children: [t("Table des matières", { bold: true, size: 34 })] }),
  new TableOfContents("Table des matières", { hyperlink: true, headingStyleRange: "1-2" }),
  ...chapters.flatMap(f => render(readWithIncludes(path.join(CONTENT, f)))),
];

const doc = new Document({
  creator: meta.author, title: meta.title, description: meta.subtitle,
  features: { updateFields: true },
  styles: {
    default: { document: { run: { font: FONT, size: 21, color: INK } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 34, bold: true, color: INK, font: FONT }, paragraph: { spacing: { before: 120, after: 240 }, outlineLevel: 0,
          border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: ACCENT, space: 6 } } } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 27, bold: true, color: ACCENT, font: FONT }, paragraph: { spacing: { before: 300, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 23, bold: true, color: DARK, font: FONT }, paragraph: { spacing: { before: 220, after: 100 }, outlineLevel: 2 } },
    ],
  },
  numbering: { config: [
    { reference: "bul", levels: [
      { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 500, hanging: 260 } } } },
      { level: 1, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 900, hanging: 260 } } } }] },
    { reference: "num", levels: [
      { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 500, hanging: 300 } } } }] },
  ] },
  sections: [
    { properties: { page: { margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } }, children: cover },
    { properties: { page: { margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 }, pageNumbers: { start: 2 } } },
      headers: { default: new Header({ children: [new Paragraph({ tabStops: [{ type: TabStopType.RIGHT, position: W }],
        border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: RULE, space: 4 } },
        children: [t(meta.header_left, { size: 16, color: MUTED }), t("\t" + meta.header_right, { size: 16, color: ACCENT, bold: true })] })] }) },
      footers: { default: new Footer({ children: [new Paragraph({ tabStops: [{ type: TabStopType.RIGHT, position: W }],
        children: [t(meta.footer_left, { size: 16, color: MUTED }), t("\tPage ", { size: 16, color: MUTED }),
          new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: MUTED }),
          t(" / ", { size: 16, color: MUTED }), new TextRun({ children: [PageNumber.TOTAL_PAGES], font: FONT, size: 16, color: MUTED })] })] }) },
      children: body },
  ],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(OUT, buf);
  console.log(`OK ${path.basename(OUT)}  chapters=${chapters.length} figures=${figN} tables=${tabN} bytes=${buf.length}`);
});
