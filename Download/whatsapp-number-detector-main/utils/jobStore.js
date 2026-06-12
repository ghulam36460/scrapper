const { v4: uuidv4 } = require("uuid");

const jobs = new Map();

function createJob({ inputFilePath, originalFileName, sendMessages }) {
  const id = uuidv4();
  const now = new Date().toISOString();

  const job = {
    id,
    status: "queued",
    inputFilePath,
    outputFilePath: "",
    originalFileName,
    sendMessages,
    totalRows: 0,
    processedRows: 0,
    sentCount: 0,
    failedCount: 0,
    skippedCount: 0,
    error: "",
    createdAt: now,
    startedAt: "",
    completedAt: "",
  };

  jobs.set(id, job);
  return job;
}

function getJob(jobId) {
  return jobs.get(jobId) || null;
}

function updateJob(jobId, patch) {
  const current = jobs.get(jobId);
  if (!current) {
    return null;
  }

  const updated = { ...current, ...patch };
  jobs.set(jobId, updated);
  return updated;
}

function incrementJobProgress(jobId, rowStatus) {
  const current = jobs.get(jobId);
  if (!current) {
    return null;
  }

  const updated = {
    ...current,
    processedRows: current.processedRows + 1,
  };

  if (rowStatus === "sent") {
    updated.sentCount += 1;
  } else if (rowStatus === "failed") {
    updated.failedCount += 1;
  } else {
    updated.skippedCount += 1;
  }

  jobs.set(jobId, updated);
  return updated;
}

module.exports = {
  createJob,
  getJob,
  updateJob,
  incrementJobProgress,
};