const fs = require("fs");
const path = require("path");

const { processCsvFile, streamFilteredCsv } = require("../services/csvService");
const { createJob, getJob, updateJob } = require("../utils/jobStore");
const logger = require("../utils/logger");

function startProcessing(req, res) {
  if (!req.file) {
    return res.status(400).json({ message: "CSV file is required" });
  }

  const sendMessages = String(req.body.sendMessages || "false").toLowerCase() === "true";
  const messageText =
    typeof req.body.messageText === "string" && req.body.messageText.trim().length
      ? req.body.messageText.trim()
      : "Hello ";

  const job = createJob({
    inputFilePath: req.file.path,
    originalFileName: req.file.originalname,
    sendMessages,
  });

  processCsvFile(job.id, {
    inputFilePath: req.file.path,
    originalFileName: req.file.originalname,
    sendMessages,
    messageText,
  }).catch((error) => {
    logger.error("Background CSV processing failed", { jobId: job.id, error: error.message });
    updateJob(job.id, {
      status: "failed",
      error: error.message,
      completedAt: new Date().toISOString(),
    });
  });

  return res.status(202).json({
    message: "File uploaded. Processing started.",
    jobId: job.id,
  });
}

function getProcessingStatus(req, res) {
  const { jobId } = req.params;
  const job = getJob(jobId);

  if (!job) {
    return res.status(404).json({ message: "Job not found" });
  }

  return res.json(job);
}

function downloadProcessedFile(req, res) {
  const { jobId } = req.params;
  const requestedFilter = String(req.query.filter || "all").toLowerCase();
  const allowedFilters = ["all", "sent", "failed", "skipped"];

  if (!allowedFilters.includes(requestedFilter)) {
    return res.status(400).json({
      message: "Invalid filter. Allowed values: all, sent, failed, skipped",
    });
  }

  const job = getJob(jobId);
  if (!job) {
    return res.status(404).json({ message: "Job not found" });
  }

  if (job.status !== "completed") {
    return res.status(409).json({ message: "Job is not completed yet" });
  }

  if (!job.outputFilePath || !fs.existsSync(job.outputFilePath)) {
    return res.status(404).json({ message: "Processed file not found" });
  }

  const sourceName = path.parse(job.originalFileName || "leads").name;
  const outputName = `${sourceName}-processed-${requestedFilter}.csv`;

  if (requestedFilter === "all") {
    return res.download(job.outputFilePath, outputName);
  }

  return streamFilteredCsv({
    sourceFilePath: job.outputFilePath,
    filter: requestedFilter,
    downloadFileName: outputName,
    res,
  });
}

module.exports = {
  startProcessing,
  getProcessingStatus,
  downloadProcessedFile,
};