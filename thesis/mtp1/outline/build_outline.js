const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType } = require("docx");
const FONT = "Times New Roman", BLACK = "000000";
const abs = ["Rakes of Indian Railways are routinely detained at loading terminals well beyond the free time allowed by the rules. Published benchmarks put detention at 14–17 h per rake, while mechanised loading of a rake takes about 5 h or less. Detention costs the client demurrage, the Railway wagon time and the terminal line capacity. Its causes sit across four parties (terminal, Railway, client and road transporter) and are operational, commercial and managerial at once, so no single intervention can be judged in isolation, and siding-level time records were not available. The problem is to find which constraints detain rakes, by how much, and which interventions release them fastest, cheapest and with the most capacity gained.", "This work builds a discrete-event simulation of a private coal siding in ten verified layers: the physical chain; eight administrative steps (M1–M8) with office calendars and rework; the road side; dispatch rules with an optimisation bound; a scenario campaign; the individual effect of every factor with bounds; ten commodity profiles calibrated from 220,395 Eastern Railway freight records; an omitted-factor stress test; an exact breakdown of time and money; and a capacity study. The model is defined by a full mathematical formulation, charges follow the Ministry of Railways demurrage compendium (2024), every parameter is tagged as cited or assumed, 107 automated checks guard the code, and the simulated queue is checked against queueing theory.", "The calibrated siding detains a rake for 15.53 h against 4.05 h of physical work. In a congested test case, about 78 % of rake waiting is administrative (office hours and rework), at most 8 % is recoverable by optimal sequencing and 14 % is congestion. Procedural levers save about 15.5 times more detention than capital ones. For a coal siding, round-the-clock terminal paperwork with digital release reporting, which needs no construction, cuts detention from 17.0 to 9.5 h and demurrage by 78 % (Rs 2.05 crore a year), and lets the same line take 556 rakes a year instead of 292 at today's waiting time (+90 %); with a second line and crew, 1,262. The ranking of interventions is unchanged in eight stress tests (Kendall τ = 1.00). Rupee and capacity figures rest on assumed paperwork times and are read as directions and orders of magnitude until siding time logs are available."];
const T = (text, o = {}) => new TextRun({ text, font: FONT, color: BLACK, ...o });
const H = (lvl, text) => new Paragraph({ heading: lvl, children: [T(text)] });
const P = (text, o = {}) => new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 160, line: 300 }, children: [T(text, o)] });
const item = (text, indent) => new Paragraph({ spacing: { after: 60 }, indent: { left: indent }, children: [T(text, { size: 22 })] });

const kids = [
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: [T("Analysis of Operational, Commercial and Managerial Constraints at a Freight Terminal, and Solutions for Quick Release of Rolling Stock", { bold: true, size: 30 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 360 }, children: [T("MTP Report (Part I): structure for review", { size: 22 })] }),
  H(HeadingLevel.HEADING_1, "Front matter"),
  ...["Title page", "Declaration", "Certificate", "Acknowledgements", "Abstract", "Contents", "List of Figures", "List of Tables", "List of Abbreviations"].map((t) => item(t, 360)),
  H(HeadingLevel.HEADING_1, "Abstract"),
  ...abs.map((t) => P(t)),
  H(HeadingLevel.HEADING_1, "Chapter 1  Introduction"),
  H(HeadingLevel.HEADING_2, "1.1  Background"),
  H(HeadingLevel.HEADING_2, "1.2  The Loading Siding and the Charging Rules"),
  H(HeadingLevel.HEADING_2, "1.3  Literature Review"),
  H(HeadingLevel.HEADING_3, "1.3.1  Terminal Performance and Dwell Time"),
  H(HeadingLevel.HEADING_3, "1.3.2  Terminal Coordination and Appointment Systems"),
  H(HeadingLevel.HEADING_3, "1.3.3  Scheduling with Availability Constraints"),
  H(HeadingLevel.HEADING_3, "1.3.4  Simulation, Sensitivity and Attribution Methods"),
  H(HeadingLevel.HEADING_3, "1.3.5  Research Gap"),
  H(HeadingLevel.HEADING_2, "1.4  Problem Statement"),
  H(HeadingLevel.HEADING_2, "1.5  Objectives"),
  H(HeadingLevel.HEADING_2, "1.6  Scope and Key Assumptions"),
  H(HeadingLevel.HEADING_2, "1.7  Organisation of the Report"),
  H(HeadingLevel.HEADING_1, "Chapter 2  Modelling"),
  H(HeadingLevel.HEADING_2, "2.1  Modelling Approach"),
  H(HeadingLevel.HEADING_2, "2.2  System Description"),
  H(HeadingLevel.HEADING_2, "2.3  Selection of Variables"),
  H(HeadingLevel.HEADING_2, "2.4  Field Data"),
  H(HeadingLevel.HEADING_2, "2.5  Mathematical Formulation"),
  H(HeadingLevel.HEADING_3, "2.5.1  Inputs and Distributions"),
  H(HeadingLevel.HEADING_3, "2.5.2  Office Calendars"),
  H(HeadingLevel.HEADING_3, "2.5.3  Rework"),
  H(HeadingLevel.HEADING_3, "2.5.4  Event Recursion (Gates)"),
  H(HeadingLevel.HEADING_3, "2.5.5  Performance Measures and IR Charges"),
  H(HeadingLevel.HEADING_3, "2.5.6  Capacity of the Siding"),
  H(HeadingLevel.HEADING_3, "2.5.7  Dispatch and Optimisation"),
  H(HeadingLevel.HEADING_3, "2.5.8  Statistical Design and Analysis"),
  H(HeadingLevel.HEADING_3, "2.5.9  Wagon Damage (Optional Module)"),
  H(HeadingLevel.HEADING_2, "2.6  Parameters and Calibration"),
  H(HeadingLevel.HEADING_2, "2.7  Experimental Design"),
  H(HeadingLevel.HEADING_2, "2.8  Implementation and Verification"),
  H(HeadingLevel.HEADING_1, "Chapter 3  Results and Discussion"),
  H(HeadingLevel.HEADING_2, "3.1  Calibrated Baseline"),
  H(HeadingLevel.HEADING_2, "3.2  Where Detention Comes From"),
  H(HeadingLevel.HEADING_2, "3.3  Procedural versus Capital Interventions"),
  H(HeadingLevel.HEADING_2, "3.4  Individual Effect of Every Factor"),
  H(HeadingLevel.HEADING_2, "3.5  Materials and Labour"),
  H(HeadingLevel.HEADING_2, "3.6  Breakdown of Time and Money"),
  H(HeadingLevel.HEADING_3, "3.6.1  Where the Hours Come From"),
  H(HeadingLevel.HEADING_3, "3.6.2  Where the Rupees Come From"),
  H(HeadingLevel.HEADING_3, "3.6.3  Fair Split between Levers"),
  H(HeadingLevel.HEADING_3, "3.6.4  Who Gains What"),
  H(HeadingLevel.HEADING_2, "3.7  Capacity of the Siding"),
  H(HeadingLevel.HEADING_2, "3.8  Wagon Damage and the Locomotive"),
  H(HeadingLevel.HEADING_2, "3.9  Sufficiency of the Variable Set"),
  H(HeadingLevel.HEADING_2, "3.10  Summary: Time, Cost and Capacity"),
  H(HeadingLevel.HEADING_1, "Chapter 4  Conclusion"),
  H(HeadingLevel.HEADING_2, "4.1  Summary of Findings"),
  H(HeadingLevel.HEADING_2, "4.2  Recommendations"),
  H(HeadingLevel.HEADING_2, "4.3  Limitations"),
  H(HeadingLevel.HEADING_2, "4.4  Future Work (MTP Part II)"),
  H(HeadingLevel.HEADING_1, "References"),
];
const hs = (id, name, size, before, after, indent) => ({ id, name, basedOn: "Normal", next: "Normal", quickFormat: true,
  run: { font: FONT, size, bold: true, color: BLACK },
  paragraph: { spacing: { before, after }, indent: { left: indent }, outlineLevel: Number(id.slice(-1)) - 1 } });
const doc = new Document({
  creator: "Ayan Ahmed", title: "MTP Report (Part I) - structure",
  styles: { default: { document: { run: { font: FONT, size: 24, color: BLACK } } },
    paragraphStyles: [hs("Heading1", "Heading 1", 28, 300, 120, 0), hs("Heading2", "Heading 2", 24, 160, 60, 360), hs("Heading3", "Heading 3", 22, 80, 40, 720)] },
  sections: [{ properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } }, children: kids }],
});
Packer.toBuffer(doc).then((b) => { fs.writeFileSync(process.argv[2], b); console.log("ok"); });
