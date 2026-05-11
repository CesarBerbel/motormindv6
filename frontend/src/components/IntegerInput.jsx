import React from "react";
import { Form } from "react-bootstrap";

function normalizeInteger(value) {
  if (value === "" || value === null || value === undefined) return "";
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    const digits = String(value).replace(/\D/g, "");
    return digits ? String(Number(digits)) : "";
  }
  return String(Math.trunc(parsed));
}

export default function IntegerInput({ value, onChange, placeholder = "0", min, step, ...props }) {
  const normalizedValue = normalizeInteger(value);

  function handleChange(event) {
    const raw = event.target.value;
    const allowNegative = min === undefined || Number(min) < 0;
    const sign = allowNegative && String(raw).trim().startsWith("-") ? "-" : "";
    const digits = String(raw).replace(/\D/g, "");
    const nextValue = digits ? `${sign}${Number(digits)}` : "";

    onChange?.({
      ...event,
      target: { ...event.target, value: nextValue },
      currentTarget: { ...event.currentTarget, value: nextValue },
    });
  }

  return (
    <Form.Control
      {...props}
      type="number"
      inputMode="numeric"
      min={min}
      step="1"
      placeholder={placeholder}
      value={normalizedValue}
      onChange={handleChange}
    />
  );
}
