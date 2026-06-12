const fs = require("fs");
const path = require("path");

const logsDir = path.join(__dirname, "..", "logs");
const logFilePath = path.join(logsDir, "app.log");

if (!fs.existsSync(logsDir)) {
  fs.mkdirSync(logsDir, { recursive: true });
}

function serialize(data) {
  if (!data) {
    return "";
  }
  if (typeof data === "string") {
    return data;
  }
  return JSON.stringify(data);
}

function write(level, message, meta) {
  const line = `[${new Date().toISOString()}] [${level}] ${message}${meta ? ` ${serialize(meta)}` : ""}`;
  if (level === "ERROR") {
    console.error(line);
  } else if (level === "WARN") {
    console.warn(line);
  } else {
    console.log(line);
  }
  fs.appendFile(logFilePath, `${line}\n`, () => {});
}

module.exports = {
  info: (message, meta) => write("INFO", message, meta),
  warn: (message, meta) => write("WARN", message, meta),
  error: (message, meta) => write("ERROR", message, meta),
};