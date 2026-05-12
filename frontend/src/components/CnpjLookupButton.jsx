import React, { useState } from "react";
import { Button } from "react-bootstrap";
import { lookupCnpj } from "../utils/cnpj";

export default function CnpjLookupButton({ cnpj, onFound, onError, className = "px-2 text-nowrap" }) {
  const [loading, setLoading] = useState(false);

  async function handleClick() {
    setLoading(true);
    try {
      const company = await lookupCnpj(cnpj);
      onFound(company);
    } catch (error) {
      onError?.(error.message || "Não foi possível buscar o CNPJ.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Button type="button" size="sm" variant="outline-secondary" className={className} onClick={handleClick} disabled={loading} title="Buscar dados do CNPJ na BrasilAPI">
      {loading ? "..." : "Buscar"}
    </Button>
  );
}
