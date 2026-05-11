import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Button, Form, InputGroup } from "react-bootstrap";
import { normalizeSearchText } from "../utils/search";

function normalizeSuggestion(suggestion) {
  if (typeof suggestion === "string") {
    return { key: suggestion, value: suggestion, label: suggestion, searchText: suggestion };
  }

  return {
    key: suggestion.key ?? suggestion.value ?? suggestion.label,
    value: suggestion.value ?? suggestion.label ?? "",
    label: suggestion.label ?? suggestion.value ?? "",
    description: suggestion.description ?? "",
    meta: suggestion.meta ?? "",
    searchText: suggestion.searchText ?? [suggestion.label, suggestion.value, suggestion.description, suggestion.meta].filter(Boolean).join(" "),
  };
}

export default function SearchAutocompleteInput({
  id,
  value,
  onChange,
  onSearch,
  onSelect,
  suggestions = [],
  placeholder = "Buscar",
  disabled = false,
  className = "",
  clearLabel = "Limpar pesquisa",
  allowClear = false,
}) {
  const [open, setOpen] = useState(false);
  const [menuStyle, setMenuStyle] = useState(null);
  const controlRef = useRef(null);

  const filteredSuggestions = useMemo(() => {
    const term = normalizeSearchText(value);
    const unique = [];
    const seen = new Set();

    suggestions.forEach((suggestion) => {
      const option = normalizeSuggestion(suggestion);
      const searchable = normalizeSearchText(option.searchText);
      const key = String(option.key || searchable).trim();
      if (!option.label || !searchable || seen.has(key)) return;
      if (term && !searchable.includes(term)) return;
      seen.add(key);
      unique.push(option);
    });

    return unique.slice(0, 10);
  }, [suggestions, value]);

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
  }, [open, updateMenuPosition, filteredSuggestions.length]);

  useEffect(() => {
    if (!open) return undefined;
    window.addEventListener("resize", updateMenuPosition);
    window.addEventListener("scroll", updateMenuPosition, true);
    return () => {
      window.removeEventListener("resize", updateMenuPosition);
      window.removeEventListener("scroll", updateMenuPosition, true);
    };
  }, [open, updateMenuPosition]);

  function runSearch(nextValue) {
    setOpen(false);
    onSearch?.(String(nextValue || "").trim());
  }

  function clearSearch() {
    onChange("");
    setOpen(false);
    onSearch?.("");
    controlRef.current?.focus();
  }

  function selectSuggestion(suggestion) {
    const nextValue = suggestion.value || suggestion.label || "";
    onChange(nextValue);
    setOpen(false);
    if (onSelect) {
      onSelect(suggestion, nextValue);
      return;
    }
    runSearch(nextValue);
  }

  const menu = open && filteredSuggestions.length > 0 && menuStyle ? (
    <div className="autocomplete-menu autocomplete-menu-portal shadow-lg" style={menuStyle}>
      {filteredSuggestions.map((suggestion) => (
        <button
          key={suggestion.key}
          type="button"
          className="autocomplete-item"
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => selectSuggestion(suggestion)}
        >
          <span className="autocomplete-item-main">{suggestion.label}</span>
          {suggestion.description ? <span className="autocomplete-item-description">{suggestion.description}</span> : null}
          {suggestion.meta ? <span className="autocomplete-item-meta">{suggestion.meta}</span> : null}
        </button>
      ))}
    </div>
  ) : null;

  const canClear = allowClear && !disabled && Boolean(String(value || "").trim());

  return (
    <div className={`autocomplete-box ${className}`.trim()}>
      <InputGroup>
        <Form.Control
          ref={controlRef}
          id={id}
          placeholder={placeholder}
          value={value || ""}
          disabled={disabled}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 140)}
          onChange={(event) => {
            onChange(event.target.value);
            setOpen(true);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              runSearch(event.currentTarget.value);
            }
          }}
          autoComplete="off"
        />
        {allowClear ? (
          <Button variant="outline-secondary" type="button" disabled={!canClear} onMouseDown={(event) => event.preventDefault()} onClick={clearSearch}>
            {clearLabel}
          </Button>
        ) : null}
      </InputGroup>
      {menu ? createPortal(menu, document.body) : null}
    </div>
  );
}
