const express = require("express");
const fs = require("fs");
const multer = require("multer");
const path = require("path");

const {
  startProcessing,
  getProcessingStatus,
  downloadProcessedFile,
} = require("../controllers/automationController");

const router = express.Router();
const uploadsDir = path.join(__dirname, "..", "uploads");

if (!fs.existsSync(uploadsDir)) {
  fs.mkdirSync(uploadsDir, { recursive: true });
}

const storage = multer.diskStorage({
  destination: (_req, _file, cb) => cb(null, uploadsDir),
  filename: (_req, file, cb) => {
    const safeOriginal = file.originalname.replace(/[^a-zA-Z0-9._-]/g, "_");
    cb(null, `${Date.now()}-${safeOriginal}`);
  },
});

const upload = multer({
  storage,
  limits: { fileSize: 25 * 1024 * 1024 },
  fileFilter: (_req, file, cb) => {
    const ext = path.extname(file.originalname || "").toLowerCase();
    if (ext !== ".csv") {
      return cb(new Error("Only CSV files are allowed"));
    }
    return cb(null, true);
  },
});

router.post("/process", upload.single("file"), startProcessing);
router.get("/status/:jobId", getProcessingStatus);
router.get("/download/:jobId", downloadProcessedFile);

module.exports = router;