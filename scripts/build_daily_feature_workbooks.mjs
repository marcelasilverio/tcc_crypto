import fs from "node:fs/promises";
import path from "node:path";

import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [packetDirectory, outputDirectory, qaDirectory, expectedCountText] =
  process.argv.slice(2);
if (!packetDirectory || !outputDirectory || !qaDirectory || !expectedCountText) {
  throw new Error(
    "Usage: node build_daily_feature_workbooks.mjs <packet-directory> <output-directory> <qa-directory> <expected-count>",
  );
}
const expectedCount = Number(expectedCountText);
if (!Number.isInteger(expectedCount) || expectedCount < 1) {
  throw new Error("expected-count must be a positive integer.");
}

const fontFamily = "Arial";
const colors = {
  navy: "#17365D",
  blue: "#2F75B5",
  lightBlue: "#D9EAF7",
  lightGray: "#F2F2F2",
  white: "#FFFFFF",
  gray: "#666666",
  amber: "#FFF2CC",
  amberText: "#7F6000",
  red: "#FCE4D6",
  redText: "#9C0006",
  border: "#D9E2F3",
};

function safeValue(value) {
  return value === undefined || Number.isNaN(value) ? null : value;
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

function configureSheet(sheet) {
  sheet.showGridLines = false;
}

function styleTitle(sheet, title, subtitle, width = "H") {
  sheet.getRange("A2").values = [[title]];
  applyFont(sheet.getRange("A2"), { size: 16, bold: true, color: colors.navy });
  sheet.getRange("A3").values = [[subtitle]];
  applyFont(sheet.getRange("A3"), { italic: true, color: colors.gray });
  sheet.getRange(`A4:${width}4`).format.borders = {
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

function formatBody(range) {
  applyFont(range);
  range.format.verticalAlignment = "center";
  range.format.borders = {
    bottom: { style: "thin", color: "#E6E6E6" },
  };
}

function populateReadySummary(workbook, payload) {
  const sheet = workbook.worksheets.getItem("Summary");
  configureSheet(sheet);
  styleTitle(
    sheet,
    `${payload.symbol} daily feature analysis`,
    "Binance Spot daily observations in UTC; feature selection uses training data only.",
  );

  styleSection(sheet, "A6:B6", "Feature coverage");
  const coverageRows = [
    ["Trading pair", payload.symbol],
    ["Status", payload.status],
    ["Raw daily observations", payload.coverage.raw_rows],
    ["Warm-up rows removed", payload.coverage.warmup_rows_removed],
    ["Complete feature observations", payload.coverage.complete_feature_rows],
    ["First feature date (UTC)", new Date(payload.coverage.first_feature_time_utc)],
    ["Last feature date (UTC)", new Date(payload.coverage.last_feature_time_utc)],
    ["Active features", payload.parameters.active_features.length],
    ["Source", payload.source],
  ];
  writeMatrix(sheet, 7, 1, coverageRows);
  formatBody(sheet.getRange("A7:B15"));
  sheet.getRange("A7:A15").format.fill = colors.lightGray;
  sheet.getRange("A7:A15").format.font.bold = true;
  sheet.getRange("B12:B13").setNumberFormat("yyyy-mm-dd");

  styleSection(sheet, "D6:H6", "Approved selection settings");
  const settingsRows = [
    ["Setting", "Value", "Status", "Unit", "Note"],
    ["Variance threshold", payload.parameters.variance_threshold, "Approved", "variance", "Refitted for every prediction"],
    ["Correlation threshold", payload.parameters.correlation_threshold, "Approved", "absolute Pearson correlation", "Applied after variance filtering"],
    ["Training windows", payload.parameters.training_window_sizes.join(", "), "Approved", "daily observations", "Separate rolling analyses"],
    ["Prediction step", 1, "Approved", "daily observation", "Next observation is excluded from fitting"],
    ["Parabolic SAR acceleration", 0, "Verify later", "parameter", "Provisional Silva-reference value"],
    ["Parabolic SAR maximum", 0, "Verify later", "parameter", "Provisional Silva-reference value"],
  ];
  writeMatrix(sheet, 7, 4, settingsRows);
  styleHeader(sheet.getRange("D7:H7"));
  formatBody(sheet.getRange("D8:H13"));
  sheet.getRange("F12:F13").format.fill = colors.amber;
  sheet.getRange("F12:F13").format.font = {
    name: fontFamily,
    size: 10,
    bold: true,
    color: colors.amberText,
  };
  sheet.getRange("E8:E9").setNumberFormat("0.00");

  styleSection(sheet, "A18:F18", "Rolling-selection summary");
  const windowRows = [
    ["Window", "Predictions", "Minimum selected", "Mean selected", "Maximum selected"],
    ...payload.window_summary.map((row) => [
      row.window_size,
      row.prediction_count,
      row.minimum_selected,
      row.mean_selected,
      row.maximum_selected,
    ]),
  ];
  writeMatrix(sheet, 19, 1, windowRows.map((row) => row.slice(0, 2)));
  writeMatrix(sheet, 19, 4, windowRows.map((row) => row.slice(2)));
  styleHeader(sheet.getRange("A19:B19"));
  styleHeader(sheet.getRange("D19:F19"));
  formatBody(sheet.getRange(`A20:B${18 + windowRows.length}`));
  formatBody(sheet.getRange(`D20:F${18 + windowRows.length}`));
  sheet.getRange(`A20:B${18 + windowRows.length}`).setNumberFormat("#,##0");
  sheet.getRange(`D20:D${18 + windowRows.length}`).setNumberFormat("#,##0");
  sheet.getRange(`E20:E${18 + windowRows.length}`).setNumberFormat("0.00");
  sheet.getRange(`F20:F${18 + windowRows.length}`).setNumberFormat("#,##0");

  sheet.getRange("A:A").format.columnWidth = 31;
  sheet.getRange("B:B").format.columnWidth = 42;
  sheet.getRange("C:C").format.columnWidth = 3;
  sheet.getRange("D:D").format.columnWidth = 28;
  sheet.getRange("E:E").format.columnWidth = 20;
  sheet.getRange("F:F").format.columnWidth = 16;
  sheet.getRange("G:G").format.columnWidth = 24;
  sheet.getRange("H:H").format.columnWidth = 38;
  sheet.getRange("A2:H24").format.rowHeight = 20;
  sheet.getRange("A2").format.rowHeight = 25;
}

function populateFeatures(workbook, payload) {
  const sheet = workbook.worksheets.getItem("Features");
  configureSheet(sheet);
  const columns = ["Date (UTC)", ...payload.parameters.active_features];
  const rows = [
    columns,
    ...payload.features.map((record) => [
      new Date(record.open_time_utc),
      ...payload.parameters.active_features.map((feature) => record[feature]),
    ]),
  ];
  writeMatrix(sheet, 1, 1, rows);
  const lastRow = rows.length;
  styleHeader(sheet.getRange("A1:W1"));
  formatBody(sheet.getRange(`A2:W${lastRow}`));
  sheet.getRange(`A2:A${lastRow}`).setNumberFormat("yyyy-mm-dd");
  sheet.getRange(`B2:U${lastRow}`).setNumberFormat("0.00000000");
  sheet.getRange(`V2:W${lastRow}`).setNumberFormat("#,##0.00");
  sheet.freezePanes.freezeRows(1);
  sheet.freezePanes.freezeColumns(1);
  sheet.getRange("A:A").format.columnWidth = 14;
  sheet.getRange("B:W").format.columnWidth = 15;
  sheet.getRange("A1:W1").format.rowHeight = 34;
}

function populateSelectionFrequency(workbook, payload) {
  const sheet = workbook.worksheets.getItem("Selection frequency");
  configureSheet(sheet);
  styleTitle(
    sheet,
    `${payload.symbol} feature-selection frequency`,
    "Selection rate is descriptive filter behavior, not predictive importance.",
    "E",
  );
  const rows = [
    ["Window", "Feature", "Selected", "Predictions", "Selection rate"],
    ...payload.selection_frequency.map((record) => [
      record.window_size,
      record.feature,
      record.selection_count,
      record.prediction_count,
      record.selection_rate,
    ]),
  ];
  writeMatrix(sheet, 6, 1, rows);
  const lastRow = 5 + rows.length;
  styleHeader(sheet.getRange("A6:E6"));
  formatBody(sheet.getRange(`A7:E${lastRow}`));
  sheet.getRange(`A7:A${lastRow}`).setNumberFormat("#,##0");
  sheet.getRange(`C7:D${lastRow}`).setNumberFormat("#,##0");
  sheet.getRange(`E7:E${lastRow}`).setNumberFormat("0.0%");
  sheet.getRange(`E7:E${lastRow}`).conditionalFormats.add("colorScale", {
    colors: ["#F8696B", "#FFEB84", "#63BE7B"],
    thresholds: ["min", { type: "percentile", value: 50 }, "max"],
  });
  sheet.freezePanes.freezeRows(6);
  sheet.getRange("A:A").format.columnWidth = 13;
  sheet.getRange("B:B").format.columnWidth = 25;
  sheet.getRange("C:E").format.columnWidth = 16;
}

function populateWindowSummary(workbook, payload) {
  const sheet = workbook.worksheets.getItem("Window summary");
  configureSheet(sheet);
  styleTitle(
    sheet,
    `${payload.symbol} rolling-window summary`,
    "Number of retained features across every next-day selection step.",
    "E",
  );
  const rows = [
    ["Window", "Predictions", "Minimum selected", "Mean selected", "Maximum selected"],
    ...payload.window_summary.map((record) => [
      record.window_size,
      record.prediction_count,
      record.minimum_selected,
      record.mean_selected,
      record.maximum_selected,
    ]),
  ];
  writeMatrix(sheet, 6, 1, rows);
  const lastRow = 5 + rows.length;
  styleHeader(sheet.getRange("A6:E6"));
  formatBody(sheet.getRange(`A7:E${lastRow}`));
  sheet.getRange(`A7:C${lastRow}`).setNumberFormat("#,##0");
  sheet.getRange(`D7:D${lastRow}`).setNumberFormat("0.00");
  sheet.getRange(`E7:E${lastRow}`).setNumberFormat("#,##0");
  sheet.getRange("A:E").format.columnWidth = 20;
}

function populateSelectionHistory(workbook, payload) {
  const sheet = workbook.worksheets.getItem("Selection history");
  configureSheet(sheet);
  const rows = [
    [
      "Window",
      "Training start (UTC)",
      "Training end (UTC)",
      "Prediction date (UTC)",
      "Selected feature count",
      "Selected features",
    ],
    ...payload.selection_history.map((record) => [
      record.window_size,
      new Date(record.training_start_utc),
      new Date(record.training_end_utc),
      new Date(record.prediction_time_utc),
      record.selected_feature_count,
      record.selected_features,
    ]),
  ];
  writeMatrix(sheet, 1, 1, rows);
  const lastRow = rows.length;
  styleHeader(sheet.getRange("A1:F1"));
  formatBody(sheet.getRange(`A2:F${lastRow}`));
  sheet.getRange(`A2:A${lastRow}`).setNumberFormat("#,##0");
  sheet.getRange(`B2:D${lastRow}`).setNumberFormat("yyyy-mm-dd");
  sheet.getRange(`E2:E${lastRow}`).setNumberFormat("#,##0");
  sheet.freezePanes.freezeRows(1);
  sheet.freezePanes.freezeColumns(1);
  sheet.getRange("A:A").format.columnWidth = 12;
  sheet.getRange("B:D").format.columnWidth = 22;
  sheet.getRange("E:E").format.columnWidth = 22;
  sheet.getRange("F:F").format.columnWidth = 95;
}

function populateBlockedSummary(workbook, payload) {
  const sheet = workbook.worksheets.getItem("Summary");
  configureSheet(sheet);
  styleTitle(
    sheet,
    `${payload.symbol} daily feature analysis`,
    "Feature calculation is unavailable until the documented data gap receives an approved treatment.",
  );
  styleSection(sheet, "A6:B6", "Processing status");
  const rows = [
    ["Trading pair", payload.symbol],
    ["Status", payload.status],
    ["Diagnostic", payload.diagnostic],
    ["Missing UTC days", payload.missing_dates.length],
    ["Source", payload.source],
    ["Required action", "Approve a missing-data treatment before feature calculation"],
  ];
  writeMatrix(sheet, 7, 1, rows);
  formatBody(sheet.getRange("A7:B12"));
  sheet.getRange("A7:A12").format.fill = colors.lightGray;
  sheet.getRange("A7:A12").format.font.bold = true;
  sheet.getRange("B8:B10").format.fill = colors.red;
  sheet.getRange("B8:B10").format.font = {
    name: fontFamily,
    size: 10,
    bold: true,
    color: colors.redText,
  };
  sheet.getRange("A:A").format.columnWidth = 30;
  sheet.getRange("B:B").format.columnWidth = 90;
  sheet.getRange("B7:B12").format.wrapText = true;
  sheet.getRange("A2:H14").format.rowHeight = 22;
}

function populateMissingDates(workbook, payload) {
  const sheet = workbook.worksheets.getItem("Missing dates");
  configureSheet(sheet);
  const rows = [
    ["Missing date (UTC)", "Status"],
    ...payload.missing_dates.map((date) => [new Date(date), "No Binance daily candle in raw series"]),
  ];
  writeMatrix(sheet, 1, 1, rows);
  styleHeader(sheet.getRange("A1:B1"));
  formatBody(sheet.getRange(`A2:B${rows.length}`));
  sheet.getRange(`A2:A${rows.length}`).setNumberFormat("yyyy-mm-dd");
  sheet.freezePanes.freezeRows(1);
  sheet.getRange("A:A").format.columnWidth = 22;
  sheet.getRange("B:B").format.columnWidth = 48;
}

async function buildWorkbook(payload) {
  const workbook = Workbook.create();
  workbook.worksheets.add("Summary");
  if (payload.status === "READY") {
    workbook.worksheets.add("Features");
    workbook.worksheets.add("Selection frequency");
    workbook.worksheets.add("Window summary");
    workbook.worksheets.add("Selection history");
    populateReadySummary(workbook, payload);
    populateFeatures(workbook, payload);
    populateSelectionFrequency(workbook, payload);
    populateWindowSummary(workbook, payload);
    populateSelectionHistory(workbook, payload);
  } else {
    workbook.worksheets.add("Missing dates");
    populateBlockedSummary(workbook, payload);
    populateMissingDates(workbook, payload);
  }
  workbook.recalculate();
  return workbook;
}

function csvEscape(value) {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

await fs.mkdir(outputDirectory, { recursive: true });
await fs.mkdir(qaDirectory, { recursive: true });

const packetFiles = (await fs.readdir(packetDirectory))
  .filter((name) => name.endsWith(".json"))
  .sort();
if (packetFiles.length !== expectedCount) {
  throw new Error(`Expected ${expectedCount} packets, found ${packetFiles.length}.`);
}

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
  const summaryCheck = await workbook.inspect({
    kind: "table",
    range: payload.status === "READY" ? "Summary!A1:H24" : "Summary!A1:B12",
    include: "values,formulas",
    tableMaxRows: 24,
    tableMaxCols: 8,
  });

  const renderRanges = payload.status === "READY"
    ? {
        Summary: "A1:H24",
        Features: "A1:W20",
        "Selection frequency": "A1:E30",
        "Window summary": "A1:E10",
        "Selection history": "A1:F20",
      }
    : {
        Summary: "A1:B12",
        "Missing dates": `A1:B${payload.missing_dates.length + 1}`,
      };
  const qaSymbolDirectory = path.join(qaDirectory, payload.symbol);
  await fs.mkdir(qaSymbolDirectory, { recursive: true });
  for (const [sheetName, range] of Object.entries(renderRanges)) {
    const preview = await workbook.render({
      sheetName,
      range,
      scale: sheetName === "Features" || sheetName === "Selection history" ? 0.7 : 1,
      format: "png",
    });
    const safeSheetName = sheetName.toLowerCase().replaceAll(" ", "_");
    await fs.writeFile(
      path.join(qaSymbolDirectory, `${safeSheetName}.png`),
      new Uint8Array(await preview.arrayBuffer()),
    );
  }

  const filename = `${payload.symbol}_daily_feature_analysis.xlsx`;
  const workbookPath = path.join(outputDirectory, filename);
  const exported = await SpreadsheetFile.exportXlsx(workbook);
  await exported.save(workbookPath);
  await fs.rm(`${workbookPath}.inspect.ndjson`, { force: true });
  manifestRows.push([
    payload.symbol,
    payload.status,
    payload.status === "READY" ? payload.coverage.complete_feature_rows : "",
    payload.status === "READY" ? payload.selection_history.length : "",
    payload.missing_dates.length,
    filename,
  ]);
  qaSummary.push({
    symbol: payload.symbol,
    status: payload.status,
    sheets: Object.keys(renderRanges),
    errorScan: errorScan.ndjson,
    summaryCheck: summaryCheck.ndjson,
  });
  process.stdout.write(`Generated ${filename} (${payload.status})\n`);
}

const manifestHeader = [
  "Symbol",
  "Status",
  "Complete feature rows",
  "Rolling selection rows",
  "Missing UTC days",
  "Workbook",
];
const manifestCsv = [manifestHeader, ...manifestRows]
  .map((row) => row.map(csvEscape).join(","))
  .join("\n");
await fs.writeFile(
  path.join(outputDirectory, "workbook_manifest.csv"),
  `${manifestCsv}\n`,
  "utf8",
);
await fs.writeFile(
  path.join(qaDirectory, "qa_summary.json"),
  JSON.stringify(qaSummary, null, 2),
  "utf8",
);

if (manifestRows.length !== expectedCount) {
  throw new Error(`Expected ${expectedCount} workbooks, generated ${manifestRows.length}.`);
}
