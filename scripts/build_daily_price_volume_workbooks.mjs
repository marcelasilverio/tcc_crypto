import fs from "node:fs/promises";
import path from "node:path";

import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [packetDirectory, outputDirectory, qaDirectory] = process.argv.slice(2);
if (!packetDirectory || !outputDirectory || !qaDirectory) {
  throw new Error(
    "Usage: node build_daily_price_volume_workbooks.mjs <packet-directory> <output-directory> <qa-directory>",
  );
}

const fontFamily = "Arial";
const colors = {
  navy: "#17365D",
  blue: "#2F75B5",
  lightBlue: "#D9EAF7",
  orange: "#ED7D31",
  green: "#548235",
  lightGreen: "#E2F0D9",
  gray: "#666666",
  lightGray: "#F2F2F2",
  border: "#B7C9D6",
  white: "#FFFFFF",
  amber: "#FFF2CC",
};

const statisticsColumns = [
  "Field",
  "Unit",
  "Observations",
  "Missing values",
  "Zero observations",
  "Zero share",
  "Total",
  "Mean",
  "Median",
  "Sample standard deviation",
  "Sample variance",
  "Minimum",
  "Q1",
  "Q3",
  "Maximum",
  "Range",
  "Interquartile range",
  "Coefficient of variation",
  "Skewness",
  "Excess kurtosis",
];

function columnLetter(columnNumber) {
  let number = columnNumber;
  let result = "";
  while (number > 0) {
    number -= 1;
    result = String.fromCharCode(65 + (number % 26)) + result;
    number = Math.floor(number / 26);
  }
  return result;
}

function safeValue(value) {
  return value === undefined ? null : value;
}

function writeMatrix(sheet, startRow, startColumn, rows) {
  if (rows.length === 0 || rows[0].length === 0) return null;
  const range = sheet.getRangeByIndexes(
    startRow - 1,
    startColumn - 1,
    rows.length,
    rows[0].length,
  );
  range.values = rows.map((row) => row.map(safeValue));
  return range;
}

function applyFont(range, options = {}) {
  range.format.font = {
    name: fontFamily,
    size: options.size ?? 10,
    bold: options.bold ?? false,
    italic: options.italic ?? false,
    color: options.color ?? "#222222",
  };
}

function styleTitle(sheet, title, subtitle) {
  sheet.getRange("A2").values = [[title]];
  applyFont(sheet.getRange("A2"), { size: 16, bold: true, color: colors.navy });
  sheet.getRange("A3").values = [[subtitle]];
  applyFont(sheet.getRange("A3"), { italic: true, color: colors.gray });
  sheet.getRange("A4:R4").format.borders = {
    bottom: { style: "thin", color: colors.blue },
  };
}

function styleHeader(range) {
  range.format.fill = colors.navy;
  range.format.font = {
    name: fontFamily,
    size: 10,
    bold: true,
    color: colors.white,
  };
  range.format.horizontalAlignment = "center";
  range.format.verticalAlignment = "center";
  range.format.wrapText = true;
  range.format.borders = {
    insideVertical: { style: "thin", color: colors.white },
    bottom: { style: "thin", color: colors.navy },
  };
}

function styleSection(sheet, address, label) {
  const range = sheet.getRange(address);
  sheet.getRange(address.split(":", 1)[0]).values = [[label]];
  range.format.fill = colors.lightBlue;
  range.format.font = {
    name: fontFamily,
    size: 11,
    bold: true,
    color: colors.navy,
  };
  range.format.borders = {
    bottom: { style: "thin", color: colors.blue },
  };
}

function formatTableBody(range) {
  applyFont(range);
  range.format.verticalAlignment = "center";
  range.format.borders = {
    bottom: { style: "thin", color: "#E6E6E6" },
  };
}

function overviewPriceMatrix(statistics) {
  const prices = statistics.filter((row) => row.Field !== "quote_asset_volume");
  const byField = Object.fromEntries(prices.map((row) => [row.Field, row]));
  const metrics = [
    "Observations",
    "Missing values",
    "Mean",
    "Median",
    "Sample standard deviation",
    "Sample variance",
    "Minimum",
    "Q1",
    "Q3",
    "Maximum",
    "Range",
    "Interquartile range",
    "Coefficient of variation",
    "Skewness",
    "Excess kurtosis",
  ];
  return [
    ["Metric", "Open", "High", "Low", "Close"],
    ...metrics.map((metric) => [
      metric,
      byField.open[metric],
      byField.high[metric],
      byField.low[metric],
      byField.close[metric],
    ]),
  ];
}

function overviewVolumeMatrix(statistics) {
  const volume = statistics.find((row) => row.Field === "quote_asset_volume");
  const metrics = [
    "Observations",
    "Missing values",
    "Zero observations",
    "Zero share",
    "Total",
    "Mean",
    "Median",
    "Sample standard deviation",
    "Sample variance",
    "Minimum",
    "Q1",
    "Q3",
    "Maximum",
    "Range",
    "Interquartile range",
    "Coefficient of variation",
    "Skewness",
    "Excess kurtosis",
  ];
  return [
    ["Metric", "Value", "Unit"],
    ...metrics.map((metric) => [metric, volume[metric], volume.Unit]),
  ];
}

function configureSheet(sheet) {
  sheet.showGridLines = false;
}

function populateOverview(workbook, payload, chartDataSheet) {
  const sheet = workbook.worksheets.getItem("Overview");
  configureSheet(sheet);
  styleTitle(
    sheet,
    `${payload.symbol} daily price and USDT-volume analysis`,
    `Observed daily Binance Spot candles from ${payload.coverage["First open (UTC)"].slice(0, 10)} through ${payload.coverage["Last open (UTC)"].slice(0, 10)} (UTC)`,
  );

  styleSection(sheet, "A6:B6", "Coverage");
  const coverageRows = [
    ["Trading pair", payload.symbol],
    ["Configured start (UTC)", payload.configured_start_utc],
    ["Configured end (UTC)", payload.configured_end_utc],
    ["Effective first open (UTC)", payload.coverage["First open (UTC)"]],
    ["Effective last open (UTC)", payload.coverage["Last open (UTC)"]],
    ["Observed daily candles", payload.coverage.Observations],
    ["Missing daily openings", payload.coverage["Missing daily openings within observed span"]],
    ["Final semester", "2026-H2 (Partial through 2026-09-01)"],
  ];
  const coverageRange = writeMatrix(sheet, 7, 1, coverageRows);
  formatTableBody(coverageRange);
  sheet.getRange("A7:A14").format.font.bold = true;
  sheet.getRange("A7:A14").format.fill = colors.lightGray;
  sheet.getRange("B8:B11").setNumberFormat("yyyy-mm-dd");

  styleSection(sheet, "A17:E17", "Overall price statistics");
  const priceMatrix = overviewPriceMatrix(payload.overall_statistics);
  writeMatrix(sheet, 18, 1, priceMatrix);
  styleHeader(sheet.getRange("A18:E18"));
  formatTableBody(sheet.getRange(`A19:E${17 + priceMatrix.length}`));
  sheet.getRange("B21:E30").setNumberFormat("#,##0.00000000");
  sheet.getRange("B19:E20").setNumberFormat("#,##0");
  sheet.getRange("B31:E31").setNumberFormat("0.00%");
  sheet.getRange("B32:E33").setNumberFormat("0.0000");

  styleSection(sheet, "G17:I17", "Overall quote-volume statistics");
  const volumeMatrix = overviewVolumeMatrix(payload.overall_statistics);
  writeMatrix(sheet, 18, 7, volumeMatrix);
  styleHeader(sheet.getRange("G18:I18"));
  formatTableBody(sheet.getRange(`G19:I${17 + volumeMatrix.length}`));
  sheet.getRange("H19:H21").setNumberFormat("#,##0");
  sheet.getRange("H22:H22").setNumberFormat("0.00%");
  sheet.getRange("H23:H33").setNumberFormat("#,##0.00");
  sheet.getRange("H34:H34").setNumberFormat("0.00%");
  sheet.getRange("H35:H36").setNumberFormat("0.0000");

  const dataEndRow = payload.chart_data.length + 4;
  const priceChart = sheet.charts.add("line", [
    chartDataSheet.getRange(`A4:A${dataEndRow}`),
    chartDataSheet.getRange(`B4:B${dataEndRow}`),
    chartDataSheet.getRange(`C4:C${dataEndRow}`),
  ]);
  priceChart.setPosition("A39", "I57");
  priceChart.title = `${payload.symbol} daily opening and closing prices`;
  priceChart.titleTextStyle.fontSize = 12;
  priceChart.titleTextStyle.typeface = fontFamily;
  priceChart.legend = { position: "top", textStyle: { typeface: fontFamily } };
  priceChart.xAxis = { axisType: "textAxis", textStyle: { typeface: fontFamily, fontSize: 9 } };
  priceChart.yAxis = {
    numberFormatCode: "#,##0.########",
    numberFormatSourceLinked: false,
    textStyle: { typeface: fontFamily, fontSize: 9 },
  };
  priceChart.yAxis.title.text = "Price (USDT per base-asset unit)";
  priceChart.series.items[0].line = { fill: colors.blue, style: "solid", width: 1.5 };
  priceChart.series.items[1].line = { fill: colors.orange, style: "solid", width: 1.5 };

  const volumeChart = sheet.charts.add("line", [
    chartDataSheet.getRange(`A4:A${dataEndRow}`),
    chartDataSheet.getRange(`D4:D${dataEndRow}`),
  ]);
  volumeChart.setPosition("J39", "R57");
  volumeChart.title = `${payload.symbol} daily quote-asset volume`;
  volumeChart.titleTextStyle.fontSize = 12;
  volumeChart.titleTextStyle.typeface = fontFamily;
  volumeChart.legend = { position: "top", textStyle: { typeface: fontFamily } };
  volumeChart.xAxis = { axisType: "textAxis", textStyle: { typeface: fontFamily, fontSize: 9 } };
  volumeChart.yAxis = {
    numberFormatCode: '#,##0,,"M"',
    numberFormatSourceLinked: false,
    textStyle: { typeface: fontFamily, fontSize: 9 },
  };
  volumeChart.yAxis.title.text = "Volume (USDT)";
  volumeChart.series.items[0].line = { fill: colors.green, style: "solid", width: 1.5 };

  sheet.getRange("A1:R58").format.font.name = fontFamily;
  sheet.getRange("A:A").format.columnWidth = 31;
  sheet.getRange("B:E").format.columnWidth = 16;
  sheet.getRange("F:F").format.columnWidth = 3;
  sheet.getRange("G:G").format.columnWidth = 31;
  sheet.getRange("H:H").format.columnWidth = 18;
  sheet.getRange("I:I").format.columnWidth = 25;
  sheet.getRange("J:R").format.columnWidth = 12;
  sheet.getRange("A2:R58").format.rowHeight = 19;
  sheet.getRange("A2").format.rowHeight = 25;
  sheet.getRange("A3").format.rowHeight = 20;
}

function populateSemesterStatistics(workbook, payload) {
  const sheet = workbook.worksheets.getItem("Semester Statistics");
  configureSheet(sheet);
  styleTitle(
    sheet,
    `${payload.symbol} semester statistics`,
    "UTC calendar semesters; partial periods are labeled explicitly and missing daily openings are not filled.",
  );
  const columns = [
    "Semester",
    "Status",
    "Observed start (UTC)",
    "Observed end (UTC)",
    ...statisticsColumns,
  ];
  const rows = [
    columns,
    ...payload.semester_statistics.map((record) =>
      columns.map((column) => safeValue(record[column])),
    ),
  ];
  writeMatrix(sheet, 6, 1, rows);
  const lastRow = 5 + rows.length;
  const lastColumn = columnLetter(columns.length);
  styleHeader(sheet.getRange(`A6:${lastColumn}6`));
  formatTableBody(sheet.getRange(`A7:${lastColumn}${lastRow}`));
  sheet.getRange(`G7:I${lastRow}`).setNumberFormat("#,##0");
  sheet.getRange(`J7:J${lastRow}`).setNumberFormat("0.00%");
  sheet.getRange(`K7:U${lastRow}`).setNumberFormat("#,##0.00000000");
  sheet.getRange(`V7:V${lastRow}`).setNumberFormat("0.00%");
  sheet.getRange(`W7:X${lastRow}`).setNumberFormat("0.0000");
  sheet.getRange(`C7:D${lastRow}`).setNumberFormat("yyyy-mm-dd");
  sheet.getRange(`B7:B${lastRow}`).conditionalFormats.add("containsText", {
    text: "Partial",
    format: { fill: colors.amber, font: { bold: true, color: "#7F6000" } },
  });
  sheet.freezePanes.freezeRows(6);
  sheet.freezePanes.freezeColumns(5);
  sheet.getRange("A:A").format.columnWidth = 13;
  sheet.getRange("B:B").format.columnWidth = 11;
  sheet.getRange("C:D").format.columnWidth = 24;
  sheet.getRange("E:E").format.columnWidth = 25;
  sheet.getRange("F:F").format.columnWidth = 27;
  sheet.getRange(`G:${lastColumn}`).format.columnWidth = 16;
  sheet.getRange(`A6:${lastColumn}${lastRow}`).format.rowHeight = 21;
}

function populateExtrema(workbook, payload) {
  const sheet = workbook.worksheets.getItem("Extrema");
  configureSheet(sheet);
  styleTitle(
    sheet,
    `${payload.symbol} observed extrema`,
    "Minimum and maximum values with the exact daily candle opening date in UTC.",
  );
  const columns = [
    "Symbol",
    "Field",
    "Unit",
    "Minimum",
    "Minimum date (UTC)",
    "Maximum",
    "Maximum date (UTC)",
  ];
  const rows = [columns, ...payload.extrema.map((record) => columns.map((column) => record[column]))];
  writeMatrix(sheet, 6, 1, rows);
  const lastRow = 5 + rows.length;
  styleHeader(sheet.getRange("A6:G6"));
  formatTableBody(sheet.getRange(`A7:G${lastRow}`));
  sheet.getRange(`D7:D${lastRow}`).setNumberFormat("#,##0.00000000");
  sheet.getRange(`F7:F${lastRow}`).setNumberFormat("#,##0.00000000");
  sheet.getRange(`E7:E${lastRow}`).setNumberFormat("yyyy-mm-dd");
  sheet.getRange(`G7:G${lastRow}`).setNumberFormat("yyyy-mm-dd");
  sheet.freezePanes.freezeRows(6);
  sheet.getRange("A:A").format.columnWidth = 15;
  sheet.getRange("B:B").format.columnWidth = 25;
  sheet.getRange("C:C").format.columnWidth = 27;
  sheet.getRange("D:D").format.columnWidth = 20;
  sheet.getRange("E:E").format.columnWidth = 27;
  sheet.getRange("F:F").format.columnWidth = 20;
  sheet.getRange("G:G").format.columnWidth = 27;
}

function populateChartData(workbook, payload) {
  const sheet = workbook.worksheets.getItem("Chart Data");
  configureSheet(sheet);
  sheet.getRange("A1").values = [[`Source: ${payload.source.relative_path}`]];
  sheet.getRange("A2").values = [[`SHA-256: ${payload.source.sha256}`]];
  applyFont(sheet.getRange("A1:A2"), { italic: true, color: colors.gray });
  const columns = ["Date (UTC)", "Open (USDT)", "Close (USDT)", "Quote asset volume (USDT)"];
  const rows = [
    columns,
    ...payload.chart_data.map((record) => [
      record.open_time_utc,
      record.open,
      record.close,
      record.quote_asset_volume,
    ]),
  ];
  writeMatrix(sheet, 4, 1, rows);
  const lastRow = 3 + rows.length;
  styleHeader(sheet.getRange("A4:D4"));
  formatTableBody(sheet.getRange(`A5:D${lastRow}`));
  sheet.getRange(`B5:C${lastRow}`).setNumberFormat("#,##0.########");
  sheet.getRange(`D5:D${lastRow}`).setNumberFormat("#,##0.00");
  sheet.freezePanes.freezeRows(4);
  sheet.getRange("A:A").format.columnWidth = 15;
  sheet.getRange("B:C").format.columnWidth = 18;
  sheet.getRange("D:D").format.columnWidth = 26;
}

function populateDefinitions(workbook, payload) {
  const sheet = workbook.worksheets.getItem("Definitions");
  configureSheet(sheet);
  styleTitle(
    sheet,
    `${payload.symbol} definitions and interpretation`,
    "Definitions apply to the overall and semester statistics in this workbook.",
  );
  const rows = [
    ["Item", "Definition"],
    ...payload.definitions.map((record) => [record.Item, record.Definition]),
  ];
  writeMatrix(sheet, 6, 1, rows);
  const lastRow = 5 + rows.length;
  styleHeader(sheet.getRange("A6:B6"));
  formatTableBody(sheet.getRange(`A7:B${lastRow}`));
  sheet.getRange(`B7:B${lastRow}`).format.wrapText = true;
  sheet.getRange(`B7:B${lastRow}`).format.verticalAlignment = "top";
  sheet.freezePanes.freezeRows(6);
  sheet.getRange("A:A").format.columnWidth = 31;
  sheet.getRange("B:B").format.columnWidth = 95;
  sheet.getRange(`A7:B${lastRow}`).format.rowHeight = 34;
}

async function buildWorkbook(payload) {
  const workbook = Workbook.create();
  workbook.worksheets.add("Overview");
  workbook.worksheets.add("Semester Statistics");
  workbook.worksheets.add("Extrema");
  const chartDataSheet = workbook.worksheets.add("Chart Data");
  workbook.worksheets.add("Definitions");

  populateChartData(workbook, payload);
  populateOverview(workbook, payload, chartDataSheet);
  populateSemesterStatistics(workbook, payload);
  populateExtrema(workbook, payload);
  populateDefinitions(workbook, payload);
  workbook.recalculate();
  return workbook;
}

function csvEscape(value) {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

await fs.mkdir(outputDirectory, { recursive: true });
await fs.mkdir(path.join(outputDirectory, "by_symbol"), { recursive: true });
await fs.mkdir(qaDirectory, { recursive: true });

const packetFiles = (await fs.readdir(packetDirectory))
  .filter((name) => name.endsWith(".json"))
  .sort();
const manifestRows = [];
const qaSummary = [];

for (const packetFile of packetFiles) {
  const payload = JSON.parse(
    await fs.readFile(path.join(packetDirectory, packetFile), "utf8"),
  );
  const workbook = await buildWorkbook(payload);
  const errorScan = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
    options: { useRegex: true, maxResults: 100 },
    summary: `${payload.symbol} formula error scan`,
  });
  const overviewCheck = await workbook.inspect({
    kind: "table",
    range: "Overview!A1:I36",
    include: "values,formulas",
    tableMaxRows: 36,
    tableMaxCols: 9,
  });
  const drawingCheck = await workbook.inspect({
    kind: "drawing",
    sheetId: "Overview",
    maxChars: 4000,
  });

  const sheetNames = ["Overview", "Semester Statistics", "Extrema", "Chart Data", "Definitions"];
  const renderRanges = {
    Overview: "A1:R58",
    "Semester Statistics": `A1:X${payload.semester_statistics.length + 6}`,
    Extrema: "A1:G12",
    "Chart Data": "A1:D40",
    Definitions: `A1:B${payload.definitions.length + 6}`,
  };
  for (const sheetName of sheetNames) {
    const preview = await workbook.render({
      sheetName,
      range: renderRanges[sheetName],
      scale: sheetName === "Semester Statistics" ? 0.65 : 1,
      format: "png",
    });
    const previewBytes = new Uint8Array(await preview.arrayBuffer());
    const safeSheetName = sheetName.toLowerCase().replaceAll(" ", "_");
    await fs.writeFile(
      path.join(qaDirectory, `${payload.symbol}_${safeSheetName}.png`),
      previewBytes,
    );
  }
  const chartDataLastRow = payload.chart_data.length + 4;
  const chartDataTail = await workbook.render({
    sheetName: "Chart Data",
    range: `A${Math.max(4, chartDataLastRow - 34)}:D${chartDataLastRow}`,
    scale: 1,
    format: "png",
  });
  await fs.writeFile(
    path.join(qaDirectory, `${payload.symbol}_chart_data_tail.png`),
    new Uint8Array(await chartDataTail.arrayBuffer()),
  );

  const filename = `${payload.symbol}_daily_price_volume_analysis_2019H2_2026-09-01.xlsx`;
  const workbookPath = path.join(outputDirectory, "by_symbol", filename);
  const exported = await SpreadsheetFile.exportXlsx(workbook);
  await exported.save(workbookPath);

  manifestRows.push([
    payload.symbol,
    "GENERATED",
    payload.coverage.Observations,
    payload.coverage["First open (UTC)"],
    payload.coverage["Last open (UTC)"],
    payload.coverage["Missing daily openings within observed span"],
    payload.source.relative_path,
    payload.source.sha256,
    path.relative(outputDirectory, workbookPath),
  ]);
  qaSummary.push({
    symbol: payload.symbol,
    sheets: sheetNames,
    chartCount: workbook.worksheets.getItem("Overview").charts.items.length,
    errorScan: errorScan.ndjson,
    overviewCheck: overviewCheck.ndjson,
    drawingCheck: drawingCheck.ndjson,
  });
  process.stdout.write(`Generated ${filename}\n`);
}

const manifestHeader = [
  "Symbol",
  "Status",
  "Observations",
  "First open (UTC)",
  "Last open (UTC)",
  "Missing daily openings",
  "Source CSV",
  "Source CSV SHA-256",
  "Workbook",
];
const manifestCsv = [manifestHeader, ...manifestRows]
  .map((row) => row.map(csvEscape).join(","))
  .join("\n");
await fs.writeFile(
  path.join(outputDirectory, "analysis_manifest.csv"),
  `${manifestCsv}\n`,
  "utf8",
);
await fs.writeFile(
  path.join(qaDirectory, "qa_summary.json"),
  JSON.stringify(qaSummary, null, 2),
  "utf8",
);

if (manifestRows.length !== 40) {
  throw new Error(`Expected 40 workbooks, generated ${manifestRows.length}.`);
}
