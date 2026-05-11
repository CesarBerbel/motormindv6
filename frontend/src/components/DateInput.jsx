import React, { useMemo, useState } from "react";
import { Form } from "react-bootstrap";
import { dateInputValue, formatDate } from "../workshopOptions";

export default function DateInput({ value, placeholder, className = "", onBlur, onFocus, ...props }) {
  const normalizedValue = value || "";
  const [isFocused, setIsFocused] = useState(false);

  const today = useMemo(() => dateInputValue(), []);
  const label = placeholder || formatDate(today);
  const shouldUseDatePicker = Boolean(normalizedValue) || isFocused;

  function handleFocus(event) {
    setIsFocused(true);
    onFocus?.(event);
  }

  function handleBlur(event) {
    setIsFocused(false);
    onBlur?.(event);
  }

  return (
    <Form.Control
      {...props}
      type={shouldUseDatePicker ? "date" : "text"}
      inputMode={shouldUseDatePicker ? undefined : "none"}
      value={normalizedValue}
      placeholder={label}
      className={className}
      onFocus={handleFocus}
      onBlur={handleBlur}
      aria-label={props["aria-label"] || label}
    />
  );
}
