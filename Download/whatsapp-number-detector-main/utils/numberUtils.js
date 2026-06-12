function normalizePhoneNumber(rawValue, defaultCountryCode = "92") {
  const raw = String(rawValue || "").trim();

  if (!raw) {
    return { isValid: false, value: "", reason: "empty" };
  }

  let digits = raw.replace(/[^0-9+]/g, "").replace(/^\+/, "");

  if (digits.startsWith("00")) {
    digits = digits.slice(2);
  }

  if (digits.startsWith("0")) {
    digits = `${defaultCountryCode}${digits.replace(/^0+/, "")}`;
  } else if (!digits.startsWith(defaultCountryCode) && /^\d{10}$/.test(digits)) {
    digits = `${defaultCountryCode}${digits}`;
  }

  const valid = /^\d{10,15}$/.test(digits);
  if (!valid) {
    return { isValid: false, value: "", reason: "invalid_length_or_format" };
  }

  return { isValid: true, value: digits };
}

module.exports = {
  normalizePhoneNumber,
};