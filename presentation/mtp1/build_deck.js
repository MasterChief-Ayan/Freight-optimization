// Final MTP-1 presentation, Ayan Ahmed. Style follows the mid-term Canva deck
// (charcoal 241E20, red 960000 tags/pills, purple 5E17EB dashed boxes, white text).
// Content rules follow academic-pptx: action titles, one exhibit per result, citations, conclusions last.
// Every number comes from the final report / results CSVs (see NUMBERS below).
const pptxgen = require("pptxgenjs");
const path = require("path");
// Optional: the pptx skill's apply_theme.js writes THEME into the deck. Set PPTX_SKILL_DIR to use it.
let applyTheme = async () => {};
try { applyTheme = require(path.join(process.env.PPTX_SKILL_DIR || "", "scripts/apply_theme.js")).applyTheme; } catch (e) { /* theme colours stay as hex */ }

const A = (f) => path.join(__dirname, "assets", f);
const OUT = path.join(__dirname, "MTP1_Final_Presentation_Ayan_Ahmed.pptx");

const BG = "241E20", CARD = "2E282A", BOX = "3A3436";
const RED = "960000", BRED = "ED1D2B", PURP = "5E17EB", PURPL = "9B6CF5";
const WHITE = "FFFFFF", MUTED = "C7C8C7", GREY = "8A8487", GRID = "4A4446";
const HF = "Montserrat", BF = "Arial";

const THEME = {
  name: "MTP Dark Red", headFontFace: HF, bodyFontFace: BF,
  colors: { dk1: BG, lt1: WHITE, dk2: "3A3436", lt2: "EFEDED", accent1: RED, accent2: BRED,
            accent3: PURP, accent4: GREY, accent5: "C9A227", accent6: "009900", hlink: PURPL, folHlink: GREY },
};

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in
pres.author = "Ayan Ahmed";
pres.title = "Quick release of rolling stock at a freight terminal - MTP Part I";
pres.theme = { headFontFace: HF, bodyFontFace: BF };

pres.defineSlideMaster({
  title: "TITLE_DARK",
  background: { color: BG },
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: BG },
  objects: [
    { image: { x: 0, y: 0, w: 4.6, h: 0.62, path: A("tag.png") } },
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.74, w: 9.0, h: 0.82,
        fontFace: HF, fontSize: 20, bold: true, color: WHITE, valign: "top", align: "left", margin: 0 },
        text: "" } },
  ],
  slideNumber: { x: 9.3, y: 5.2, w: 0.45, h: 0.3, color: MUTED, fontFace: BF, fontSize: 11, align: "right" },
});

// ---------- helpers ----------
let curSection = null;
function sec(t) { if (t !== curSection) { pres.addSection({ title: t }); curSection = t; } }
function content(section, title, sectionTitle) {
  sec(sectionTitle);
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle });
  s.addText(section, { x: 0.22, y: 0.03, w: 3.4, h: 0.38, fontFace: HF, fontSize: 14, bold: true,
    color: WHITE, margin: 0, valign: "middle", isTextBox: true, objectName: "section tag" });
  s.addText(title, { placeholder: "title" });
  return s;
}
function cite(s, text) {
  s.addText(text, { x: 0.5, y: 5.2, w: 8.6, h: 0.3, fontFace: BF, fontSize: 10, color: GREY,
    margin: 0, valign: "middle", isTextBox: true, objectName: "citation" });
}
function pill(s, text, x, y, w, h, o = {}) {
  s.addText(text, { shape: pres.shapes.ROUNDED_RECTANGLE, x, y, w, h, rectRadius: 0.05,
    fill: { color: o.fill || RED }, line: { color: o.fill || RED, width: 0.5 },
    fontFace: o.font || HF, fontSize: o.size || 14, bold: o.bold !== false, color: WHITE,
    align: o.align || "center", valign: "middle", margin: o.margin ?? 4, objectName: o.name || "pill" });
}
function box(s, x, y, w, h, o = {}) {
  s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: o.fill || CARD },
    line: { color: o.line || PURP, width: o.lw || 1.5, dashType: o.dash || "dash" }, objectName: o.name || "card" });
}
function txt(s, text, x, y, w, h, o = {}) {
  s.addText(text, { x, y, w, h, fontFace: o.font || BF, fontSize: o.size || 16, bold: !!o.bold,
    italic: !!o.italic, color: o.color || WHITE, align: o.align || "left", valign: o.valign || "top",
    margin: o.margin ?? 0, paraSpaceAfter: o.psa || 0, isTextBox: true, objectName: o.name || "text",
    lineSpacingMultiple: o.lsm });
}
function hbar(s, labels, values, colors, o) {
  s.addChart(pres.charts.BAR, [{ name: o.name || "series", labels, values }], {
    x: o.x, y: o.y, w: o.w, h: o.h, barDir: "bar", chartColors: colors,
    catAxisOrientation: "maxMin", catAxisLabelColor: "E6E6E6", catAxisLabelFontFace: BF,
    catAxisLabelFontSize: o.catSize || 13, catAxisLineShow: false, catAxisLabelPos: o.labelLow ? "low" : "nextTo", catGridLine: { style: "none" },
    valAxisHidden: true, valGridLine: { style: "none" }, valAxisMinVal: o.min, valAxisMaxVal: o.max,
    showValue: true, dataLabelPosition: "outEnd", dataLabelColor: WHITE, dataLabelFontFace: BF,
    dataLabelFontSize: o.dlSize || 14, dataLabelFontBold: true, dataLabelFormatCode: o.fmt || "0.0",
    showLegend: false, barGapWidthPct: o.gap || 45,
    plotArea: { fill: { color: BG } }, chartArea: { fill: { color: BG } }, objectName: o.objName || "chart",
  });
}

// =====================================================================
// 1  TITLE
// =====================================================================
{
  sec("Introduction");
  const s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "Introduction" });
  s.addImage({ path: A("logo.png"), x: 0.5, y: 0.38, w: 0.72, h: 0.72, objectName: "IIT Kharagpur logo" });
  txt(s, "Department of Industrial and Systems Engineering\nIndian Institute of Technology Kharagpur",
      1.38, 0.45, 4.6, 0.6, { size: 12, color: MUTED, valign: "middle" });
  pill(s, "M.Tech Thesis Project  ·  Part I  ·  Final Review", 0.5, 1.4, 4.2, 0.4, { size: 12 });
  txt(s, "Analysis of Operational, Commercial and Managerial Constraints at a Freight Terminal, and Solutions for Quick Release of Rolling Stock",
      0.5, 1.95, 5.2, 1.7, { font: HF, size: 19, bold: true });
  txt(s, "Office hours and paperwork, not equipment, hold the rakes, and fixing them also adds capacity",
      0.5, 3.78, 5.2, 0.6, { size: 14, italic: true, color: "F3B0B0" });
  txt(s, [
      { text: "Ayan Ahmed  |  22MF3IM04", options: { bold: true, fontSize: 15, breakLine: true } },
      { text: "Supervisor: Prof. Biswajit Mahanty", options: { fontSize: 13, color: MUTED } },
    ], 0.5, 4.6, 5.0, 0.62, {});
  s.addShape(pres.shapes.RECTANGLE, { x: 6.12, y: 1.52, w: 3.5, h: 2.33, fill: { color: RED },
    line: { color: RED, width: 0 }, objectName: "photo frame" });
  s.addImage({ path: A("train.png"), x: 5.95, y: 1.35, w: 3.5, h: 2.33, objectName: "freight train photo" });
  s.addNotes("Good morning. My thesis looks at why freight rakes stand so long at a loading terminal, and what releases them fastest. One line summary: it is office hours and paperwork, not equipment, that hold the rakes, and fixing them also lets the same siding handle more rakes.");
}

// =====================================================================
// 2  PROBLEM
// =====================================================================
{
  const s = content("1 · INTRODUCTION", "A rake stands 14–17 h at an Indian terminal, although loading it takes 5 h or less", "Introduction");
  const cards = [
    ["14–17 h", "detention per rake at Indian terminals"],
    ["≤ 5 h", "to load a full rake with a payloader (≈ 1 h with rapid loading)"],
    ["80–85 %", "of terminal restrictions come from poor release of rakes"],
  ];
  cards.forEach(([big, lab], i) => {
    const x = 0.5 + i * 3.1;
    box(s, x, 1.72, 2.8, 2.05, { name: "stat card" });
    txt(s, big, x + 0.2, 1.88, 2.4, 0.75, { font: HF, size: 34, bold: true, color: i === 1 ? WHITE : BRED, valign: "middle" });
    txt(s, lab, x + 0.2, 2.68, 2.45, 0.95, { size: 15, color: WHITE });
  });
  txt(s, "Who pays:", 0.5, 4.12, 1.3, 0.45, { size: 16, bold: true, valign: "middle" });
  pill(s, "Client → demurrage", 1.75, 4.12, 2.25, 0.45, { size: 14 });
  pill(s, "Railway → wagon time", 4.12, 4.12, 2.48, 0.45, { size: 14 });
  pill(s, "Terminal → line capacity", 6.72, 4.12, 2.78, 0.45, { size: 14 });
  cite(s, "TERI (2023), Vol. I: Terminal Operations;  PIB, Ministry of Coal (07.10.2024)");
  s.addNotes("TERI puts rake detention at Indian terminals at 14 to 17 hours, and attributes most terminal restrictions to poor release of rakes. Yet loading a rake mechanically takes 5 hours or less. So most of the detention is not loading. Everyone pays: the client pays demurrage, the Railway loses wagon time, and the terminal loses line capacity because a standing rake blocks the next one.");
}

// =====================================================================
// 3  RESEARCH QUESTION
// =====================================================================
{
  const s = content("1 · INTRODUCTION", "The question: which constraints hold a rake, by how much, and which levers release it", "Introduction");
  box(s, 0.5, 1.7, 9.0, 1.2, { name: "research question box" });
  txt(s, "Which operational, commercial and managerial constraints detain rakes at a private coal siding, and which interventions release them fastest, cheapest and with the most capacity gained?",
      0.75, 1.8, 8.5, 1.0, { size: 17, bold: true, valign: "middle" });
  const cols = [["TIME", "Detention: placement → release (h)"], ["COST", "Demurrage under IR's graded tariff (₹)"], ["CAPACITY", "Rakes a year the siding can take"]];
  cols.forEach(([h, d], i) => {
    const x = 0.5 + i * 3.1;
    pill(s, h, x, 3.15, 2.8, 0.45, { size: 16 });
    txt(s, d, x + 0.05, 3.7, 2.75, 0.75, { size: 15, align: "center" });
  });
  txt(s, "Scope: one private coal siding (Eastern Railway context)  ·  1 line, 1 crew, 1 shunting loco  ·  wagon demand → loaded rake departs",
      0.5, 4.6, 9.0, 0.45, { size: 12, color: MUTED });
  s.addNotes("The research question has three measures. Time: detention from placement to release, which is what the Railway bills. Cost: demurrage under the graded tariff. And capacity, which my supervisor asked me to add: how many rakes a year the siding can take. The base case is one private coal siding with one line, one crew and one shunting locomotive.");
}

// =====================================================================
// 4  JOURNEY: BEFORE / AFTER MID-TERM
// =====================================================================
{
  const s = content("2 · MODELLING", "Before mid-term we built and tested the model; after it we measured, generalised and sized it", "Modelling");
  const before = [["L0", "Physical chain: place, load, release"], ["L1", "Paperwork M1–M8, office hours, rework"], ["L2", "Road side: trucks, gate, appointments"], ["L3", "Dispatch rules + CP-SAT lower bound"], ["L4", "Nine interventions, paired runs"]];
  const after = [["L5", "Effect of every factor (39 parameters)"], ["L6", "Ten commodities, 220,395 ER records"], ["L7", "Stress tests for omitted factors"], ["L8", "Hours, rupees and who gains"], ["L9", "Capacity: how many more rakes"]];
  const col = (x, head, items, foot, fill) => {
    box(s, x, 1.7, 4.15, 3.35, { name: "phase card" });
    pill(s, head, x + 0.15, 1.82, 3.85, 0.42, { size: 13, fill });
    items.forEach(([k, v], i) => {
      txt(s, [{ text: k + "  ", options: { bold: true, color: fill === RED ? "F3B0B0" : BRED } }, { text: v }],
          x + 0.25, 2.38 + i * 0.42, 3.8, 0.4, { size: 14, valign: "middle" });
    });
    txt(s, foot, x + 0.25, 4.55, 3.8, 0.35, { size: 12, color: MUTED, italic: true, valign: "middle" });
  };
  col(0.5, "BEFORE MID-TERM  ·  Layers 0–4", before, "57 checks  ·  TERI-calibrated base", RED);
  col(5.35, "AFTER MID-TERM  ·  Layers 5–9", after, "107 checks  ·  final report (41 pages)", BRED);
  s.addShape(pres.shapes.CHEVRON, { x: 4.78, y: 3.15, w: 0.45, h: 0.5, fill: { color: WHITE }, line: { color: WHITE, width: 0 }, objectName: "arrow" });
  cite(s, "Layer 9 (capacity) added after the final meeting with the supervisor");
  s.addNotes("Before the mid-term I built the model layer by layer: the physical chain, the eight paperwork steps with office hours and rework, the road side, dispatch rules with an optimisation bound, and a campaign of nine interventions. After the mid-term I measured the effect of every factor, extended the model to ten commodities using 220,395 Eastern Railway freight records, stress-tested what the model leaves out, broke every saving into hours, rupees and parties, and finally measured capacity. The automated checks grew from 57 to 107.");
}

// =====================================================================
// 5  HOW THE MODEL WORKS
// =====================================================================
{
  const s = content("2 · MODELLING", "Each rake moves through physical steps that wait for paperwork and office hours", "Modelling");
  const steps = ["Arrive", "Queue", "Place", "Load", "Weigh", "Release", "Remove", "Depart"];
  const bw = 1.0, gap = 0.143, y = 2.2;
  steps.forEach((t, i) => {
    const x = 0.5 + i * (bw + gap);
    s.addText(t, { shape: pres.shapes.RECTANGLE, x, y, w: bw, h: 0.55, fill: { color: BOX },
      line: { color: i >= 2 && i <= 5 ? BRED : "5A5456", width: 1.25 }, fontFace: BF, fontSize: 14, bold: true,
      color: WHITE, align: "center", valign: "middle", margin: 0, objectName: "step " + t });
  });
  // billed window bracket (Place .. Release)
  const bx = 0.5 + 2 * (bw + gap), bxe = 0.5 + 5 * (bw + gap) + bw;
  s.addShape(pres.shapes.LINE, { x: bx, y: 2.05, w: bxe - bx, h: 0, line: { color: BRED, width: 2 }, objectName: "billed bracket" });
  s.addShape(pres.shapes.LINE, { x: bx, y: 2.05, w: 0, h: 0.15, line: { color: BRED, width: 2 } });
  s.addShape(pres.shapes.LINE, { x: bxe, y: 2.05, w: 0, h: 0.15, line: { color: BRED, width: 2 } });
  txt(s, "Billed window: 8 h free, then graded demurrage", bx, 1.68, bxe - bx, 0.32, { size: 13, bold: true, color: BRED, align: "center", valign: "bottom" });
  // admin steps gating the physical events
  const adm = [[2, "M3 forwarding note"], [3, "M4 placement advice"], [4, "M5 weighment"], [5, "M6 release report"], [7, "M7 RR + payment"]];
  adm.forEach(([i, t]) => {
    const x = 0.5 + i * (bw + gap);
    s.addShape(pres.shapes.LINE, { x: x + bw / 2, y: 2.75, w: 0, h: 0.32, line: { color: PURPL, width: 1.5, dashType: "dash" }, objectName: "gate" });
    pill(s, t, x - 0.02, 3.07, bw + 0.04, 0.62, { size: 11, font: BF, margin: 2 });
  });
  box(s, 0.5, 4.0, 9.0, 1.0, { name: "office step rules" });
  txt(s, "Every paperwork step has:", 0.7, 4.08, 2.5, 0.84, { size: 15, bold: true, valign: "middle" });
  const rules = ["an office calendar\n(opens and closes)", "a working time\n(random, lognormal)", "rejection → rework\n(up to 5 attempts)"];
  rules.forEach((r, i) => txt(s, r, 3.2 + i * 2.1, 4.08, 2.0, 0.84, { size: 14, valign: "middle", align: "center" }));
  cite(s, "Discrete-event simulation in Python (SimPy); charging rules: MoR Compendium (2024)");
  s.addNotes("This is the model in one picture. A rake arrives, queues for the line, is placed, loaded, weighed, released, removed and departs. The Railway bills only from placement to release: 8 hours free, then graded demurrage. The physical events wait for documents: the forwarding note, the placement advice, weighment, the release report, and the railway receipt with payment. Every paperwork step has an office that opens and closes, a random working time, and a chance of rejection that sends it back.");
}

// =====================================================================
// 6  ANCHORS + VERIFICATION
// =====================================================================
{
  const s = content("2 · MODELLING", "IR rules, field data and 107 checks anchor the model; it reproduces TERI's 14–17 h", "Modelling");
  box(s, 0.5, 1.7, 5.4, 3.35, { name: "calibration exhibit" });
  txt(s, "Mean detention per rake (h)", 0.75, 1.82, 5.0, 0.35, { size: 14, bold: true });
  const ax0 = 0.85, ax1 = 5.55, ay = 3.75, scale = (ax1 - ax0) / 20; // 0..20 h
  const X = (h) => ax0 + h * scale;
  s.addShape(pres.shapes.RECTANGLE, { x: X(14), y: 2.55, w: X(17) - X(14), h: 1.2, fill: { color: "1F5F2E" }, line: { color: "3FA35B", width: 1 }, objectName: "TERI band" });
  txt(s, "TERI\n14–17 h", X(14) - 0.05, 2.25, X(17) - X(14) + 0.1, 0.3, { size: 11, color: "7FD493", align: "center", valign: "bottom" });
  s.addShape(pres.shapes.LINE, { x: ax0, y: ay, w: ax1 - ax0, h: 0, line: { color: MUTED, width: 1.5 }, objectName: "axis" });
  [0, 5, 10, 15, 20].forEach((h) => {
    s.addShape(pres.shapes.LINE, { x: X(h), y: ay, w: 0, h: 0.08, line: { color: MUTED, width: 1 } });
    txt(s, String(h), X(h) - 0.25, ay + 0.1, 0.5, 0.28, { size: 12, color: MUTED, align: "center" });
  });
  s.addShape(pres.shapes.OVAL, { x: X(15.53) - 0.13, y: 3.0, w: 0.26, h: 0.26, fill: { color: BRED }, line: { color: WHITE, width: 1 }, objectName: "model dot" });
  txt(s, "Model 15.5 h", X(15.53) - 0.75, 3.3, 1.5, 0.3, { size: 13, bold: true, color: WHITE, align: "center" });
  s.addShape(pres.shapes.OVAL, { x: X(4.05) - 0.11, y: 3.03, w: 0.22, h: 0.22, fill: { color: GREY }, line: { color: WHITE, width: 1 }, objectName: "physical dot" });
  txt(s, "Physical work\nonly 4.05 h", X(4.05) - 0.75, 2.45, 1.5, 0.52, { size: 12, color: MUTED, align: "center", valign: "bottom" });
  txt(s, "The 11.5 h gap is what the paperwork layers explain", 0.75, 4.42, 5.0, 0.45, { size: 14, italic: true, color: "F3B0B0", valign: "middle" });
  const chips = [
    ["MoR Compendium 2024", "Free time 8 h; ₹150 per wagon-hour, graded ×1 to ×3"],
    ["220,395 freight records", "Eastern Railway register 2022–26; coal = 61 % of tonnes"],
    ["107 / 107 checks pass", "Conservation, Little's law, bound never beaten"],
  ];
  chips.forEach(([h, d], i) => {
    const y = 1.7 + i * 1.15;
    s.addShape(pres.shapes.RECTANGLE, { x: 6.15, y, w: 3.35, h: 1.0, fill: { color: CARD }, line: { color: RED, width: 1.5 }, objectName: "anchor chip" });
    txt(s, h, 6.3, y + 0.08, 3.1, 0.36, { font: HF, size: 14, bold: true, color: BRED, valign: "middle" });
    txt(s, d, 6.3, y + 0.45, 3.1, 0.5, { size: 12, color: WHITE });
  });
  cite(s, "TERI (2023); MoR Compendium (03.04.2024); Eastern Railway FOIS RR register (2022–26); Little (1961)");
  s.addNotes("Three things anchor the model. Charging rules come straight from the Ministry of Railways compendium. Commodity attributes come from 220,395 Eastern Railway freight records. And 107 automated checks guard the code. With paperwork, the calibrated model gives 15.5 hours, inside TERI's 14 to 17 hour range; the physical work alone is only about 4 hours. The paperwork durations are assumed, so I report directions and rankings, not exact rupees.");
}

// =====================================================================
// 7  R1: WHERE WAITING COMES FROM
// =====================================================================
{
  const s = content("3 · RESULTS", "78 % of a rake's waiting comes from office hours and rejected documents", "Results");
  const x0 = 0.5, W = 9.0, y = 1.95, h = 0.95;
  const seg = [[78, RED, "78 %"], [8, PURP, "8 %"], [14, "6B6567", "14 %"]];
  let x = x0;
  const centers = [];
  seg.forEach(([p, c, l]) => {
    const w = (W * p) / 100;
    s.addText(l, { shape: pres.shapes.RECTANGLE, x, y, w, h, fill: { color: c }, line: { color: BG, width: 1 },
      fontFace: HF, fontSize: p > 10 ? 26 : 16, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0, objectName: "segment " + l });
    centers.push(x + w / 2); x += w;
  });
  const labs = [
    [0.5, 4.3, "Administrative", "office hours + rejected documents"],
    [5.05, 2.25, "Sequencing", "the most any order could recover (CP-SAT bound)"],
    [7.5, 2.0, "Congestion", "irreducible"],
  ];
  labs.forEach(([lx, lw, h1, h2], i) => {
    s.addShape(pres.shapes.LINE, { x: centers[i], y: y + h, w: 0, h: 0.22, line: { color: MUTED, width: 1 }, objectName: "leader" });
    if (i > 0) s.addShape(pres.shapes.LINE, { x: Math.min(centers[i], lx + 0.1), y: y + h + 0.22, w: Math.abs(centers[i] - (lx + 0.1)), h: 0, line: { color: MUTED, width: 1 } });
    txt(s, [{ text: h1, options: { bold: true, fontSize: 16, breakLine: true } }, { text: h2, options: { fontSize: 13, color: MUTED } }],
        lx, y + h + 0.3, lw, 0.75, {});
  });
  box(s, 0.5, 4.12, 4.35, 0.9, { name: "stat" });
  txt(s, [{ text: "15.5 h", options: { bold: true, color: BRED, fontSize: 20 } }, { text: " detention vs ", options: { fontSize: 13 } }, { text: "4.05 h", options: { bold: true, fontSize: 20 } }, { text: " physical work", options: { fontSize: 13 } }],
      0.7, 4.17, 4.1, 0.8, { valign: "middle" });
  box(s, 5.15, 4.12, 4.35, 0.9, { name: "stat" });
  txt(s, "Rakes wait for offices and documents, not for their turn in the queue", 5.35, 4.17, 4.0, 0.8, { size: 15, bold: true, valign: "middle" });
  cite(s, "Layer 3 exact split of rake waiting; sequencing bound from CP-SAT (Google OR-Tools)");
  s.addNotes("First result. If I split a rake's waiting exactly, about 78 percent comes from offices being closed and documents being rejected. The best possible sequencing, from the CP-SAT bound, could recover at most 8 percent, and 14 percent is congestion no rule can remove. So the rakes wait for offices and documents, not for their turn.");
}

// =====================================================================
// 8  R2: PROCEDURE VS CAPITAL
// =====================================================================
{
  const s = content("3 · RESULTS", "Digital paperwork saves 15.5× more detention than a second line with its crew", "Results");
  txt(s, "Detention saved per rake (h)", 0.5, 1.62, 5.9, 0.32, { size: 13, bold: true, color: MUTED });
  const labels = ["Digitalise all paperwork", "Digitalise weighment + release", "Terminal works 24/7", "Loading 50 % faster", "No rework anywhere", "2nd line + 2nd crew", "2nd shunting loco", "2nd line alone (−0.28)"];
  const vals = [8.98, 7.65, 5.28, 2.08, 1.40, 0.58, 0.00, -0.28];
  const cols = [BRED, BRED, BRED, GREY, BRED, GREY, GREY, GREY];
  hbar(s, labels, vals, cols, { x: 0.3, y: 1.9, w: 6.2, h: 3.2, min: -1, max: 10.5, fmt: "0.00;;0.00", catSize: 13, dlSize: 13, labelLow: true, objName: "interventions chart" });
  txt(s, "15.5×", 6.75, 1.75, 2.8, 0.85, { font: HF, size: 44, bold: true, color: BRED });
  txt(s, "8.98 h vs 0.58 h saved per rake", 6.75, 2.6, 2.8, 0.4, { size: 15, bold: true });
  txt(s, [
      { text: "Red: procedure  ·  Grey: capital", options: { breakLine: true, color: MUTED, fontSize: 13 } },
      { text: "2nd line alone: no gain (+0.28 h, n.s.)", options: { bullet: true, breakLine: true } },
      { text: "2nd loco: zero, shunting is outside the billed window", options: { bullet: true } },
    ], 6.75, 3.15, 2.8, 1.9, { size: 14, psa: 6 });
  cite(s, "Layer 4: 10 runs × 25 rakes, common random numbers, paired 95 % CI; base 16.07 h at this operating point");
  s.addNotes("Second result. Ranking nine interventions on the same random numbers: each of the three paperwork levers beats every capital lever. Digitalising the paperwork saves 8.98 hours per rake; a second line with its own crew saves 0.58, about 15.5 times less. A second line alone does not help at all, and a second shunting locomotive changes nothing because shunting is outside the billed window.");
}

// =====================================================================
// 9  R3: TERMINAL HOURS
// =====================================================================
{
  const s = content("3 · RESULTS", "Terminal working hours alone move detention by 21 h, more than all physical factors together", "Results");
  txt(s, "Swing in detention over each factor's range (h)", 0.5, 1.62, 5.9, 0.32, { size: 13, bold: true, color: MUTED });
  const labels = ["Terminal working hours (8→24 h/day)", "Release reporting time (M6)", "Loading rate", "Weighment time (M5)", "Payload per wagon", "Wagons per rake"];
  const vals = [21.17, 6.63, 6.60, 3.59, 1.98, 1.79];
  hbar(s, labels, vals, [BRED, GREY, GREY, GREY, GREY, GREY], { x: 0.3, y: 1.9, w: 6.3, h: 3.2, min: 0, max: 25, fmt: "0.0", catSize: 13, dlSize: 14, objName: "sensitivity chart" });
  box(s, 6.8, 1.75, 2.7, 1.75, { name: "callout" });
  txt(s, [{ text: "16 h → 18 h", options: { bold: true, color: BRED, fontSize: 24, breakLine: true } }, { text: "a day already gives 43 % of the round-the-clock gain", options: { fontSize: 14 } }],
      6.95, 1.85, 2.45, 1.55, { valign: "middle" });
  txt(s, [{ text: "Morris screening of 39 parameters confirms the same top three", options: { bullet: true, breakLine: true } }, { text: "Pricing moves money, not time", options: { bullet: true } }],
      6.8, 3.7, 2.75, 1.35, { size: 14, psa: 6 });
  cite(s, "Layer 5: one-factor-at-a-time bounds and Morris (1991) elementary effects; terminal hours cited, other ranges assumed");
  s.addNotes("Third result. Varying every factor over its range, one calendar decision dominates: the hours a day the terminal's own paperwork runs. Going from 8 to 24 hours moves detention by 21 hours, more than all physical factors together. And it is front-loaded: extending today's 16-hour day to 18 hours already gives 43 percent of the round-the-clock gain. Morris screening agrees on the top factors.");
}

// =====================================================================
// 10 R4: MONEY
// =====================================================================
{
  const s = content("3 · RESULTS", "Package A cuts detention by 44 % but demurrage by 78 %, about ₹2 crore a year", "Results");
  txt(s, "Demurrage per rake (₹ thousand)  ·  detention below each bar", 0.5, 1.62, 5.6, 0.32, { size: 13, bold: true, color: MUTED });
  s.addChart(pres.charts.BAR, [{ name: "Demurrage per rake", labels: ["Today · 17.0 h", "A · 9.5 h", "B · 8.8 h", "C · 7.3 h"], values: [89.8, 19.7, 14.2, 6.3] }], {
    x: 0.4, y: 1.95, w: 5.6, h: 2.75, barDir: "col", chartColors: [GREY, BRED, BRED, BRED],
    catAxisLabelColor: "E6E6E6", catAxisLabelFontFace: BF, catAxisLabelFontSize: 13, catAxisLineShow: true,
    catAxisLineColor: GRID, catGridLine: { style: "none" }, valAxisHidden: true, valGridLine: { style: "none" },
    valAxisMinVal: 0, valAxisMaxVal: 105, showValue: true, dataLabelPosition: "outEnd", dataLabelColor: WHITE,
    dataLabelFontFace: BF, dataLabelFontSize: 15, dataLabelFontBold: true, dataLabelFormatCode: "0.0",
    showLegend: false, barGapWidthPct: 55, plotArea: { fill: { color: BG } }, chartArea: { fill: { color: BG } }, objectName: "money chart" });
  txt(s, "A = paperwork 24/7 + digital release  ·  B = A + precise loading  ·  C = B + 50 % faster loading", 0.5, 4.72, 5.6, 0.42, { size: 11, color: MUTED });
  const stats = [["−44 %", "detention (17.0 → 9.5 h)"], ["−78 %", "demurrage per rake"], ["₹2.05 cr", "a year avoided (292 rakes)"]];
  stats.forEach(([b, l], i) => {
    const y = 1.72 + i * 0.95;
    txt(s, b, 6.35, y, 1.75, 0.6, { font: HF, size: 26, bold: true, color: i === 0 ? WHITE : BRED, valign: "middle" });
    txt(s, l, 8.05, y, 1.5, 0.6, { size: 13, valign: "middle" });
  });
  box(s, 6.35, 4.55, 3.15, 0.58, { name: "why" });
  txt(s, "Why: the first 8 h are free, so almost every hour saved is a billed hour", 6.45, 4.57, 2.98, 0.54, { size: 12, valign: "middle" });
  cite(s, "Layer 8; rates: MoR Compendium (2024); paperwork times assumed, so read as direction and size, not exact rupees");
  s.addNotes("Fourth result, the money. Package A, round-the-clock terminal paperwork with digital release and no construction, cuts detention by 44 percent but demurrage by 78 percent, about 2 crore rupees a year for 292 rakes. Money falls faster than time because the first 8 hours are free: billed hours fall from about 9.6 to 2.2 per rake, minus 77 percent, and the rising rates add the last point.");
}

// =====================================================================
// 11 R5: CAPACITY
// =====================================================================
{
  const s = content("3 · RESULTS", "At today's wait, package A lets the same line take 556 rakes a year instead of 292", "Results");
  txt(s, "Rakes a year at today's mean wait (35 h)", 0.5, 1.62, 6.0, 0.32, { size: 13, bold: true, color: MUTED });
  const labels = ["Today", "Package A", "Package B", "Package C", "Today + 2nd line & crew", "A + 2nd line & crew"];
  const vals = [292, 556, 613, 732, 710, 1262];
  hbar(s, labels, vals, [GREY, BRED, BRED, BRED, PURPL, PURPL], { x: 0.3, y: 1.9, w: 6.3, h: 3.2, min: 0, max: 1480, fmt: "#,##0", catSize: 13, dlSize: 15, objName: "capacity chart" });
  const stats = [["+90 %", "with package A alone"], ["× 4.3", "with A + a 2nd line"]];
  stats.forEach(([b, l], i) => {
    const y = 1.72 + i * 0.85;
    txt(s, b, 6.8, y, 1.45, 0.6, { font: HF, size: 26, bold: true, color: i === 0 ? BRED : PURPL, valign: "middle" });
    txt(s, l, 8.25, y, 1.3, 0.6, { size: 13, valign: "middle" });
  });
  txt(s, [{ text: "Line is the bottleneck: crew ≤ 34 %, loco ≤ 29 % busy", options: { bullet: true, breakLine: true } },
          { text: "2nd line barely shortens a stay, but doubles the room", options: { bullet: true } }],
      6.8, 3.5, 2.75, 1.6, { size: 14, psa: 8 });
  cite(s, "Layer 9: 200 rakes × 30 runs per traffic level; Red: procedure  ·  Purple: second line with its crew");
  s.addNotes("Fifth result, capacity, which my supervisor asked for. Holding today's waiting time fixed, how many rakes a year can the siding take? Today 292. Package A alone lifts it to 556, plus 90 percent, with no construction. A second line with its crew gives 710, and together with package A 1,262, more than four times today. The line is always the bottleneck; the crew and the locomotive stay below about a third busy.");
}

// =====================================================================
// 12 ROBUSTNESS + LIMITS
// =====================================================================
{
  const s = content("3 · RESULTS", "The ranking holds for ten commodities and eight stress tests; exact rupees await time logs", "Results");
  pill(s, "WHAT HOLDS", 0.5, 1.72, 4.35, 0.42, { size: 14 });
  const holds = [["10 / 10", "commodities: 24/7 paperwork and digital release help every material"], ["8 / 8", "stress tests: identical ranking (Kendall τ = 1.00)"], ["0.91–1.03", "simulated queue ÷ queueing theory, offices open"]];
  holds.forEach(([b, l], i) => {
    const y = 2.3 + i * 0.92;
    txt(s, b, 0.5, y, 1.55, 0.8, { font: HF, size: i === 2 ? 17 : 24, bold: true, color: BRED, valign: "middle" });
    txt(s, l, 2.1, y, 2.75, 0.8, { size: 14, valign: "middle" });
  });
  box(s, 5.15, 1.72, 4.35, 3.35, { name: "limits" });
  pill(s, "LIMITS  →  PART II", 5.3, 1.84, 4.05, 0.42, { size: 14, fill: PURP });
  txt(s, [
      { text: "Calibrated, not validated: ", options: { bold: true } }, { text: "siding time logs requested", options: { breakLine: true } },
      { text: "Gross savings: ", options: { bold: true } }, { text: "implementation cost and payback next", options: { breakLine: true } },
      { text: "One siding; ", options: { bold: true } }, { text: "capacity for coal only", options: {} },
    ], 5.4, 2.42, 3.95, 2.5, { size: 15, psa: 14 });
  cite(s, "Layers 6, 7, 9; Kendall (1938); Pollaczek–Khinchine formula (Gross et al., 2008)");
  s.addNotes("Are these results robust? The same general levers help all ten commodities. Adding each factor the model leaves out, in eight stress tests, changes the level of detention but not the ranking: Kendall tau is 1. And the simulated queue matches queueing theory within 0.91 to 1.03 when offices are open. The honest limits: the paperwork times are calibrated, not validated, until the siding time logs arrive; savings are gross; and it is one siding. These are Part II.");
}

// =====================================================================
// 13 CONCLUSIONS
// =====================================================================
{
  const s = content("4 · CONCLUSION", "Releasing rakes faster is a paperwork problem first and a capital problem second", "Conclusion");
  const take = [
    "Office hours and rejected documents cause ~78 % of rake waiting",
    "Digital paperwork saves 15.5× more detention than a second line",
    "Package A: −44 % time, −78 % demurrage, +90 % capacity",
    "For more traffic, add a 2nd line with its crew, after procedure",
  ];
  take.forEach((t, i) => {
    const y = 1.72 + i * 0.8;
    s.addText(String(i + 1), { shape: pres.shapes.OVAL, x: 0.5, y: y + 0.08, w: 0.5, h: 0.5, fill: { color: RED }, line: { color: RED, width: 0 },
      fontFace: HF, fontSize: 18, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0, objectName: "number" });
    txt(s, t, 1.15, y, 4.6, 0.66, { size: 16, bold: i === 0, valign: "middle" });
  });
  box(s, 6.0, 1.72, 3.5, 3.2, { name: "who acts" });
  txt(s, "Who should act", 6.15, 1.8, 3.2, 0.38, { font: HF, size: 15, bold: true, color: BRED });
  txt(s, [
      { text: "Terminal: ", options: { bold: true } }, { text: "paperwork 24/7 (or 16 → 18 h first), digital release, precise loading", options: { breakLine: true } },
      { text: "Railway: ", options: { bold: true } }, { text: "e-placement and e-release; detach damaged wagons", options: { breakLine: true } },
      { text: "Client: ", options: { bold: true } }, { text: "e-RR and e-payment", options: {} },
    ], 6.15, 2.22, 3.25, 2.65, { size: 14, psa: 10 });
  txt(s, "Ayan Ahmed  ·  22MF3IM04  ·  Dept. of Industrial and Systems Engineering, IIT Kharagpur  ·  Questions and feedback welcome",
      0.5, 5.15, 8.7, 0.35, { size: 11, color: MUTED, valign: "middle" });
  s.addNotes("To conclude: releasing rakes faster is a paperwork problem first and a capital problem second. Office hours and rejected documents cause most of the waiting; digital paperwork beats a second line by about 15 times; package A cuts time by 44 percent, demurrage by 78 percent and adds 90 percent capacity; and for growth beyond that, add a second line with its crew, after the procedural fixes. Thank you; I welcome your questions and feedback.");
}

// =====================================================================
// 14 REFERENCES
// =====================================================================
{
  const s = content("REFERENCES", "References", "References");
  const refs = [
    "Ministry of Railways (2024). Compendium: Demurrage, Stabling, Wharfage, Stacking, Waiver and Write-off (as on 03.04.2024).",
    "TERI (2023). Strategies to Increase Railway's Share in Freight Transport in India, Vol. I: Terminal Operations and Development. New Delhi.",
    "Press Information Bureau, Ministry of Coal (2024, 7 October). Foundation stone of two CCL projects.",
    "Eastern Railway (2022–2026). Inward freight register, RR base, monthly FOIS exports (unpublished data).",
    "Smith, R. G. (1980). The Contract Net Protocol. IEEE Transactions on Computers, C-29(12), 1104–1113.",
    "Perron, L., & Didier, F. CP-SAT solver, Google OR-Tools.   Team SimPy. SimPy: discrete-event simulation for Python.",
    "Morris, M. D. (1991). Factorial sampling plans for preliminary computational experiments. Technometrics, 33(2), 161–174.",
    "Little, J. D. C. (1961). A proof for the queuing formula L = λW. Operations Research, 9(3), 383–387.",
    "Gross, D., Shortle, J. F., Thompson, J. M., & Harris, C. M. (2008). Fundamentals of Queueing Theory (4th ed.). Wiley.",
    "Kendall, M. G. (1938). A new measure of rank correlation. Biometrika, 30(1/2), 81–93.",
    "Shapley, L. S. (1953). A value for n-person games. Contributions to the Theory of Games II, 307–317.",
  ];
  txt(s, refs.map((r, i) => ({ text: r, options: { breakLine: i < refs.length - 1 } })), 0.5, 1.15, 9.0, 3.95, { size: 12, psa: 5, color: "E6E6E6" });
  s.addNotes("Full reference list of the report: 29 sources, in the thesis.");
}

// =====================================================================
// 15 BACKUP (Q&A)
// =====================================================================
{
  const s = content("BACKUP · Q&A", "Backup: formulation, who gains, wagon damage and the queueing check", "Backup");
  const cards = [
    ["Core formulation", [
      "Detention  D = u − p   (placement → release)",
      "Demurrage = wagons × κ × Σ rate × hours, per band",
      "Ceiling  Λ = K · 8760 / H̄   (H̄: line hold)",
      "Capacity R*: most rakes/yr with wait ≤ today's"]],
    ["Who gains (package A)", [
      "Client: ₹2.05 cr/yr less demurrage (a transfer, not a saving)",
      "Railway: ≈ 48 wagons/yr back to the fleet (≈ ₹21 cr)",
      "Terminal: +264 rakes/yr of capacity"]],
    ["Wagon damage (assumed rates)", [
      "Detach unfit wagons at the siding",
      "Returning the whole rake costs the Railway 2.3–2.6× the wagon time"]],
    ["Queue vs theory", [
      "Offices open: simulated ÷ Pollaczek–Khinchine = 0.91–1.03",
      "As modelled: 1.04–1.96, because office hours bunch arrivals"]],
  ];
  cards.forEach(([h, items], i) => {
    const x = 0.5 + (i % 2) * 4.6, y = 1.68 + Math.floor(i / 2) * 1.74;
    box(s, x, y, 4.4, 1.6, { name: "backup card" });
    txt(s, h, x + 0.15, y + 0.08, 4.1, 0.34, { font: HF, size: 14, bold: true, color: BRED });
    txt(s, items.map((t, k) => ({ text: t, options: { bullet: true, breakLine: k < items.length - 1 } })), x + 0.15, y + 0.45, 4.15, 1.1, { size: 12, psa: 3 });
  });
  cite(s, "Report §2.5 (Eqs 2.5–2.9), §3.6.4, §3.8, Table 3.6; wagon value: recent IR wagon order");
  s.addNotes("Backup slide for questions on the formulation, who gains, wagon damage, and the queueing check. Formulation: detention is release minus placement; demurrage sums the graded bands; capacity is the most rakes a year at today's wait. The client's saving is a transfer to the Railway, whose real gain is wagon time. For damaged wagons, detaching at the siding is better than returning the rake. The queue matches theory when offices are open; office hours bunch arrivals, which is why it is longer as modelled.");
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
