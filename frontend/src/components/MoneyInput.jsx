import React, { useEffect, useMemo, useRef, useState } from "react";
import { Form } from "react-bootstrap";
import { formatMoneyEditingValue, formatMoneyInput, parseMoneyInput } from "../workshopOptions";

function formatEditingDraft(value) {
  if (value === "" || value === null || value === undefined) return "";
  const editable = formatMoneyEditingValue(value);
  return editable ? `R$ ${editable}` : "";
}

function normalizeEditingDraft(value) {
  const raw = String(value ?? "");
  const cleaned = raw.replace(/[^\d,.-]/g, "");
  if (!/\d/.test(cleaned)) return "";

  const sign = cleaned.includes("-") ? "-" : "";
  const unsigned = cleaned.replace(/-/g, "");
  return `R$ ${sign}${unsigned}`;
}

export default function MoneyInput({ value, onChange, onFocus, onBlur, ...props }) {
  const inputRef = useRef(null);
  const [isEditing, setIsEditing] = useState(false);
  const [draftValue, setDraftValue] = useState("");

  const formattedValue = useMemo(() => formatMoneyInput(value), [value]);

  useEffect(() => {
    if (!isEditing) {
      setDraftValue(formattedValue);
    }
  }, [formattedValue, isEditing]);

  function handleFocus(event) {
    setIsEditing(true);
    setDraftValue(formatEditingDraft(value));
    onFocus?.(event);

    window.requestAnimationFrame(() => {
      inputRef.current?.select();
    });
  }

  function handleChange(event) {
    const nextDraftValue = normalizeEditingDraft(event.target.value);
    setDraftValue(nextDraftValue);
    onChange?.(parseMoneyInput(nextDraftValue));
  }

  function handleBlur(event) {
    const parsedValue = parseMoneyInput(draftValue);
    setIsEditing(false);
    setDraftValue(formatMoneyInput(parsedValue));
    onChange?.(parsedValue);
    onBlur?.(event);
  }

  return (
    <Form.Control
      ref={inputRef}
      placeholder="R$ 0,00"
      {...props}
      type="text"
      inputMode="decimal"
      value={isEditing ? draftValue : formattedValue}
      onChange={handleChange}
      onFocus={handleFocus}
      onBlur={handleBlur}
    />
  );
}
