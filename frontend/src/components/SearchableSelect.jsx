import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Button, Form, InputGroup } from "react-bootstrap";

function normalize(value) {
  return String(value || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

export default function SearchableSelect({
  id,
  label,
  value,
  options = [],
  onChange,
  placeholder = "Pesquisar e selecionar",
  disabled = false,
  required = false,
  helpText = "",
  emptyMessage = "Nenhuma opção encontrada.",
  clearLabel = "Limpar",
  allowClear = true,
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [menuStyle, setMenuStyle] = useState(null);
  const controlRef = useRef(null);

  const selected = options.find((option) => String(option.value) === String(value ?? ""));
  const filtered = useMemo(() => {
    const term = normalize(query);
    if (!term) return options;
    return options.filter((option) => normalize(`${option.label || ""} ${option.description || ""} ${option.meta || ""}`).includes(term));
  }, [options, query]);

  const updateMenuPosition = useCallback(() => {
    if (!controlRef.current) return;
    const rect = controlRef.current.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom - 12;
    const spaceAbove = rect.top - 12;
    const openUp = spaceBelow < 180 && spaceAbove > spaceBelow;
    const maxHeight = Math.min(320, Math.max(140, openUp ? spaceAbove : spaceBelow));

    setMenuStyle({
      position: "fixed",
      top: openUp ? undefined : rect.bottom + 6,
      bottom: openUp ? window.innerHeight - rect.top + 6 : undefined,
      left: rect.left,
      width: rect.width,
      maxHeight,
    });
  }, []);

  useLayoutEffect(() => {
    if (!open) return undefined;
    updateMenuPosition();
    return undefined;
  }, [open, updateMenuPosition, filtered.length]);

  useEffect(() => {
    if (!open) return undefined;
    window.addEventListener("resize", updateMenuPosition);
    window.addEventListener("scroll", updateMenuPosition, true);
    return () => {
      window.removeEventListener("resize", updateMenuPosition);
      window.removeEventListener("scroll", updateMenuPosition, true);
    };
  }, [open, updateMenuPosition]);

  useEffect(() => {
    if (!open) setQuery(selected?.label || "");
  }, [selected?.label, open]);

  function selectOption(option) {
    onChange(option.value);
    setQuery(option.label || "");
    setOpen(false);
  }

  function clearSelection() {
    onChange("");
    setQuery("");
    setOpen(false);
    controlRef.current?.focus();
  }

  const inputValue = open ? query : selected?.label || "";
  const canClear = allowClear && !disabled && Boolean(String(value || "").trim() || String(query || "").trim());

  const menu = open && !disabled && menuStyle ? (
    <div className="autocomplete-menu autocomplete-menu-portal shadow-lg" style={menuStyle}>
      {filtered.length === 0 ? (
        <div className="px-3 py-2 text-muted small">{emptyMessage}</div>
      ) : (
        filtered.map((option) => (
          <button
            key={`${option.value}-${option.label}`}
            type="button"
            className="autocomplete-item"
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => selectOption(option)}
          >
            <span className="autocomplete-item-main">{option.label}</span>
            {option.description ? <span className="autocomplete-item-description">{option.description}</span> : null}
            {option.meta ? <span className="autocomplete-item-meta">{option.meta}</span> : null}
          </button>
        ))
      )}
    </div>
  ) : null;

  return (
    <Form.Group className="autocomplete-box">
      {label ? <Form.Label htmlFor={id}>{label}</Form.Label> : null}
      <InputGroup>
        <Form.Control
          ref={controlRef}
          id={id}
          value={inputValue}
          placeholder={placeholder}
          disabled={disabled}
          required={required && !value}
          onFocus={() => {
            setQuery("");
            setOpen(true);
          }}
          onBlur={() => setTimeout(() => setOpen(false), 140)}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
          }}
          autoComplete="off"
        />
        {allowClear ? (
          <Button
            variant="outline-secondary"
            type="button"
            disabled={!canClear}
            onMouseDown={(event) => event.preventDefault()}
            onClick={clearSelection}
          >
            {clearLabel}
          </Button>
        ) : null}
      </InputGroup>
      {helpText ? <div className="form-text">{helpText}</div> : null}
      {menu ? createPortal(menu, document.body) : null}
    </Form.Group>
  );
}
