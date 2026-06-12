const express = require("express");
const fs = require("fs");
const path = require("path");
const dotenv = require("dotenv");

const automationRoutes = require("../routes/automationRoutes");
const logger = require("../utils/logger");

dotenv.config();

const app = express();
const rootDir = path.resolve(__dirname, "..");
const uploadsDir = path.join(rootDir, "uploads");
const outputsDir = path.join(rootDir, "outputs");
const clientDir = path.join(rootDir, "client");

[uploadsDir, outputsDir].forEach((dirPath) => {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
  }
});

app.use(express.json());
app.use(express.urlencoded({ extended: true }));

app.get("/health", (_req, res) => {
  res.json({ status: "ok" });
});

app.use("/api/automation", automationRoutes);
app.use(express.static(clientDir));

app.get("*", (req, res, next) => {
  if (req.path.startsWith("/api/")) {
    return next();
  }
  return res.sendFile(path.join(clientDir, "index.html"));
});

app.use((err, _req, res, _next) => {
  logger.error("Unhandled server error", { error: err.message });
  res.status(500).json({ message: "Internal server error" });
});

const port = Number(process.env.PORT || 4000);

app.listen(port, () => {
  logger.info(`Server running on http://localhost:${port}`);
});