const axios = require("axios");

const logger = require("../utils/logger");

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function sendWhatsAppMessage({ to, messageText }) {
  const shouldSend = String(process.env.ENABLE_WHATSAPP_SEND || "false").toLowerCase() === "true";

  if (!shouldSend) {
    return { skipped: true, reason: "WhatsApp sending disabled by env" };
  }

  const phoneNumberId = process.env.WA_PHONE_NUMBER_ID;
  const accessToken = process.env.WA_ACCESS_TOKEN;
  const apiVersion = process.env.WA_API_VERSION || "v20.0";
  const retryCount = Number(process.env.WA_RETRY_COUNT || 2);

  if (!phoneNumberId || !accessToken) {
    throw new Error("Missing WA_PHONE_NUMBER_ID or WA_ACCESS_TOKEN in environment");
  }

  const endpoint = `https://graph.facebook.com/${apiVersion}/${phoneNumberId}/messages`;
  const payload = {
    messaging_product: "whatsapp",
    to,
    type: "text",
    text: { body: messageText || "Hello " },
  };

  let lastError = null;

  for (let attempt = 0; attempt <= retryCount; attempt += 1) {
    try {
      const response = await axios.post(endpoint, payload, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
        timeout: 15000,
      });

      return {
        success: true,
        data: response.data,
        sender: process.env.WA_SENDER_NUMBER || "",
      };
    } catch (error) {
      lastError = error;
      logger.warn("WhatsApp API call failed", {
        attempt,
        retryCount,
        to,
        error: error.response?.data || error.message,
      });

      if (attempt < retryCount) {
        await sleep(1200 * (attempt + 1));
      }
    }
  }

  throw new Error(
    `WhatsApp send failed after retries: ${lastError?.response?.data?.error?.message || lastError?.message || "Unknown error"}`
  );
}

module.exports = {
  sendWhatsAppMessage,
};