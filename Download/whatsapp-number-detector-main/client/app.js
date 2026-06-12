const uploadForm = document.getElementById("upload-form");
const csvFileInput = document.getElementById("csv-file");
const sendMessagesInput = document.getElementById("send-messages");
const messageTextInput = document.getElementById("message-text");
const uploadBtn = document.getElementById("upload-btn");
const downloadBtn = document.getElementById("download-btn");
const downloadFilter = document.getElementById("download-filter");
const progressLabel = document.getElementById("progress-label");
const progressBar = document.getElementById("progress-bar");
const statusText = document.getElementById("status-text");
const countText = document.getElementById("count-text");
const previewHead = document.getElementById("preview-head");
const previewBody = document.getElementById("preview-body");

const state = {
  jobId: "",
  pollIntervalId: null,
};

function setStatus(text, mode) {
  statusText.textContent = text;
  statusText.className = `status ${mode || "neutral"}`;
}

function updateProgress(processed, total) {
  progressLabel.textContent = `${processed} / ${total}`;
  const percentage = total > 0 ? Math.min(100, Math.round((processed / total) * 100)) : 0;
  progressBar.style.width = `${percentage}%`;
}

function parseCsvLine(line) {
  const values = [];
  let current = "";
  let inQuotes = false;

  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    const nextChar = line[i + 1];

    if (char === '"') {
      if (inQuotes && nextChar === '"') {
        current += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (char === "," && !inQuotes) {
      values.push(current.trim());
      current = "";
      continue;
    }

    current += char;
  }

  values.push(current.trim());
  return values;
}

function renderPreview(text) {
  const rows = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  previewHead.innerHTML = "";
  previewBody.innerHTML = "";

  if (rows.length === 0) {
    return;
  }

  const headers = parseCsvLine(rows[0]);
  const headerRow = document.createElement("tr");
  headers.forEach((header) => {
    const th = document.createElement("th");
    th.textContent = header;
    headerRow.appendChild(th);
  });
  previewHead.appendChild(headerRow);

  rows.slice(1, 9).forEach((line) => {
    const values = parseCsvLine(line);
    const tr = document.createElement("tr");

    headers.forEach((_header, index) => {
      const td = document.createElement("td");
      td.textContent = values[index] || "";
      tr.appendChild(td);
    });

    previewBody.appendChild(tr);
  });
}

async function pollJobStatus(jobId) {
  try {
    const response = await fetch(`/api/automation/status/${encodeURIComponent(jobId)}`);
    if (!response.ok) {
      throw new Error("Status request failed");
    }

    const job = await response.json();
    updateProgress(job.processedRows || 0, job.totalRows || 0);
    countText.textContent = `Sent: ${job.sentCount || 0} | Failed: ${job.failedCount || 0} | Skipped: ${job.skippedCount || 0}`;

    if (job.status === "processing" || job.status === "queued") {
      setStatus(`Processing job ${job.id}...`, "neutral");
      return;
    }

    if (job.status === "completed") {
      setStatus("Processing completed successfully.", "ok");
      downloadBtn.disabled = false;
      if (state.pollIntervalId) {
        clearInterval(state.pollIntervalId);
        state.pollIntervalId = null;
      }
      return;
    }

    if (job.status === "failed") {
      setStatus(`Processing failed: ${job.error || "Unknown error"}`, "bad");
      if (state.pollIntervalId) {
        clearInterval(state.pollIntervalId);
        state.pollIntervalId = null;
      }
    }
  } catch (error) {
    setStatus(`Status polling error: ${error.message}`, "bad");
  }
}

csvFileInput.addEventListener("change", async (event) => {
  const file = event.target.files?.[0];
  previewHead.innerHTML = "";
  previewBody.innerHTML = "";

  if (!file) {
    return;
  }

  if (!file.name.toLowerCase().endsWith(".csv")) {
    setStatus("Please select a valid .csv file", "bad");
    csvFileInput.value = "";
    return;
  }

  const text = await file.text();
  renderPreview(text);
  setStatus("CSV selected and preview loaded.", "neutral");
});

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  downloadBtn.disabled = true;

  const file = csvFileInput.files?.[0];
  if (!file) {
    setStatus("Please choose a CSV file first.", "bad");
    return;
  }

  uploadBtn.disabled = true;
  updateProgress(0, 0);
  countText.textContent = "Sent: 0 | Failed: 0 | Skipped: 0";
  setStatus("Uploading file...", "neutral");

  const formData = new FormData();
  formData.append("file", file);
  formData.append("sendMessages", String(sendMessagesInput.checked));
  formData.append("messageText", messageTextInput.value || "Hello ");

  try {
    const response = await fetch("/api/automation/process", {
      method: "POST",
      body: formData,
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.message || "Upload failed");
    }

    state.jobId = payload.jobId;
    setStatus("Upload successful. Processing started.", "neutral");

    if (state.pollIntervalId) {
      clearInterval(state.pollIntervalId);
    }

    await pollJobStatus(state.jobId);
    state.pollIntervalId = setInterval(() => {
      pollJobStatus(state.jobId);
    }, 1200);
  } catch (error) {
    setStatus(`Upload failed: ${error.message}`, "bad");
  } finally {
    uploadBtn.disabled = false;
  }
});

downloadBtn.addEventListener("click", () => {
  if (!state.jobId) {
    setStatus("No completed job available for download.", "bad");
    return;
  }
  const filter = downloadFilter.value || "all";
  const target = `/api/automation/download/${encodeURIComponent(state.jobId)}?filter=${encodeURIComponent(filter)}`;
  window.location.href = target;
});