const csvParser = require("csv-parser");
const { format } = require("fast-csv");
const fs = require("fs");
const path = require("path");
const { finished } = require("stream/promises");

const { sendWhatsAppMessage } = require("./whatsappService");
const { incrementJobProgress, updateJob } = require("../utils/jobStore");
const logger = require("../utils/logger");
const { normalizePhoneNumber } = require("../utils/numberUtils");

const REQUIRED_HEADERS = ["name", "email", "phone", "website", "whatsapp"];
const OUTPUT_HEADERS = ["name", "email", "phone", "website", "whatsapp", "wa_link", "status"];

const normalizeHeader = (header) => String(header || "").trim().toLowerCase();

function validateHeaders(headers = []) {
  const normalized = headers.map(normalizeHeader);
  const missing = REQUIRED_HEADERS.filter((header) => !normalized.includes(header));

  if (missing.length > 0) {
    throw new Error(`Invalid CSV headers. Missing required columns: ${missing.join(", ")}`);
  }
}

function countCsvRows(filePath) {
  return new Promise((resolve, reject) => {
    let count = 0;
    fs.createReadStream(filePath)
      .pipe(csvParser())
      .on("data", () => {
        count += 1;
      })
      .on("end", () => resolve(count))
      .on("error", reject);
  });
}

function buildOutputRecord(row, waLink, status) {
  return {
    name: String(row.name || "").trim(),
    email: String(row.email || "").trim(),
    phone: String(row.phone || "").trim(),
    website: String(row.website || "").trim(),
    whatsapp: String(row.whatsapp || "").trim(),
    wa_link: waLink,
    status,
  };
}

async function processCsvFile(jobId, options) {
  const { inputFilePath, originalFileName, sendMessages, messageText } = options;

  updateJob(jobId, {
    status: "processing",
    startedAt: new Date().toISOString(),
  });

  const totalRows = await countCsvRows(inputFilePath);
  updateJob(jobId, { totalRows });

  const outputsDir = path.join(__dirname, "..", "outputs");
  const baseName = path.parse(originalFileName || "leads").name.replace(/[^a-zA-Z0-9_-]/g, "_");
  const outputFilePath = path.join(outputsDir, `${baseName}-${jobId}-processed.csv`);

  const writeStream = fs.createWriteStream(outputFilePath);
  const csvWriter = format({ headers: OUTPUT_HEADERS });
  csvWriter.pipe(writeStream);

  const readStream = fs.createReadStream(inputFilePath);
  const parser = csvParser({
    mapHeaders: ({ header }) => normalizeHeader(header),
  });

  let headersChecked = false;

  parser.on("headers", (headers) => {
    validateHeaders(headers);
    headersChecked = true;
  });

  try {
    const source = readStream.pipe(parser);

    for await (const row of source) {
      if (!headersChecked) {
        continue;
      }

      const contactSource = String(row.whatsapp || row.phone || "").trim();
      const normalized = normalizePhoneNumber(contactSource, process.env.DEFAULT_COUNTRY_CODE || "92");

      let waLink = "";
      let status = "skipped";

      if (!normalized.isValid) {
        status = "failed";
      } else {
        waLink = `https://wa.me/${normalized.value}`;

        if (sendMessages) {
          try {
            await sendWhatsAppMessage({
              to: normalized.value,
              messageText: messageText || "Hello ",
            });
            status = "sent";
          } catch (error) {
            status = "failed";
            logger.warn("Failed to send WhatsApp message", {
              jobId,
              number: normalized.value,
              error: error.message,
            });
          }
        }
      }

      csvWriter.write(buildOutputRecord(row, waLink, status));
      incrementJobProgress(jobId, status);
    }

    csvWriter.end();
    await finished(writeStream);

    updateJob(jobId, {
      status: "completed",
      outputFilePath,
      completedAt: new Date().toISOString(),
    });

    logger.info("CSV processing completed", { jobId, outputFilePath });
  } catch (error) {
    logger.error("CSV processing failed", { jobId, error: error.message });

    csvWriter.end();
    await finished(writeStream).catch(() => {});

    updateJob(jobId, {
      status: "failed",
      error: error.message,
      completedAt: new Date().toISOString(),
    });

    throw error;
  }
}

function streamFilteredCsv({ sourceFilePath, filter, downloadFileName, res }) {
  res.setHeader("Content-Type", "text/csv");
  res.setHeader("Content-Disposition", `attachment; filename=\"${downloadFileName}\"`);

  const parser = csvParser();

  const escapeCsv = (value) => {
    const stringValue = String(value || "");
    if (/[",\n]/.test(stringValue)) {
      return `"${stringValue.replace(/"/g, '""')}"`;
    }
    return stringValue;
  };

  res.write(`${OUTPUT_HEADERS.join(",")}\n`);

  parser.on("data", (row) => {
    if (String(row.status || "").toLowerCase() === filter) {
      const line = OUTPUT_HEADERS.map((header) => escapeCsv(row[header])).join(",");
      res.write(`${line}\n`);
    }
  });

  parser.on("end", () => {
    res.end();
  });

  parser.on("error", (error) => {
    logger.error("Filtered CSV stream failed", { error: error.message });
    res.end();
  });

  fs.createReadStream(sourceFilePath).pipe(parser);
}

module.exports = {
  processCsvFile,
  streamFilteredCsv,
};