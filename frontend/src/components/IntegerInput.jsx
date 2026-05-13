import React from "react";
import { Form } from "react-bootstrap";

function isDecimalMode(step) {
  if (step === "any") return true;
  if (step === undefined || step === null || step === "") return false;
  const stepText = String(step);
  const parsed = Number(stepText);
  return stepText.includes(".") || (Number.isFinite(parsed) && !Number.isInteger(parsed));
}

function normalizeInteger(value) {
  if (value === "" || value === null || value === undefined) return "";
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    const digits = String(value).replace(/\D/g, "");
    return digits ? String(Number(digits)) : "";
  }
  return String(Math.trunc(parsed));
}

function normalizeDecimal(value) {
  if (value === "" || value === null || value === undefined) return "";

  const normalized = String(value).replace(",", ".");
  const sign = normalized.trim().startsWith("-") ? "-" : "";
  const unsigned = normalized.replace(/^-/, "").replace(/[^\d.]/g, "");
  const [integerPart = "", ...decimalParts] = unsigned.split(".");
  const decimals = decimalParts.join("");

  if (!integerPart && !decimals) return sign ? "-" : "";
  if (!decimalParts.length) return `${sign}${integerPart || "0"}`;

  return `${sign}${integerPart || "0"}.${decimals}`;
}

export default function IntegerInput({ value, onChange, placeholder = "0", min, step = "1", ...props }) {
  const decimalMode = isDecimalMode(step);
  const normalizedValue = decimalMode ? normalizeDecimal(value) : normalizeInteger(value);

  function emitChange(event, nextValue) {
    onChange?.({
      ...event,
      target: { ...event.target, value: nextValue },
      currentTarget: { ...event.currentTarget, value: nextValue },
    });
  }

  function handleChange(event) {
    const raw = event.target.value;
    const allowNegative = min === undefined || Number(min) < 0;
    const rawText = String(raw).trim();
    const sign = allowNegative && rawText.startsWith("-") ? "-" : "";

    if (decimalMode) {
      const nextValue = normalizeDecimal(`${sign}${String(raw).replace(/^-/, "")}`);
      emitChange(event, nextValue);
      return;
    }

    const digits = String(raw).replace(/\D/g, "");
    const nextValue = digits ? `${sign}${Number(digits)}` : "";
    emitChange(event, nextValue);
  }

  return (
    <Form.Control
      {...props}
      type="number"
      inputMode={decimalMode ? "decimal" : "numeric"}
      min={min}
      step={step}
      placeholder={placeholder}
      value={normalizedValue}
      onChange={handleChange}
    />
  );
}
