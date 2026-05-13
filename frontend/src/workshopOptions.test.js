import { describe, expect, it } from "vitest";
import { parseMoneyInput } from "./workshopOptions";

describe("parseMoneyInput", () => {
  it("interpreta números inteiros digitados como reais, não centavos", () => {
    expect(parseMoneyInput("1")).toBe("1.00");
    expect(parseMoneyInput("10")).toBe("10.00");
    expect(parseMoneyInput("100")).toBe("100.00");
  });

  it("aceita valores monetários formatados em pt-BR", () => {
    expect(parseMoneyInput("1,00")).toBe("1.00");
    expect(parseMoneyInput("R$ 1,00")).toBe("1.00");
    expect(parseMoneyInput("1.234,56")).toBe("1234.56");
  });

  it("aceita valores com ponto decimal e separador de milhar", () => {
    expect(parseMoneyInput("1.00")).toBe("1.00");
    expect(parseMoneyInput("1.234")).toBe("1234.00");
    expect(parseMoneyInput("1,234.56")).toBe("1234.56");
  });

  it("mantém campo vazio quando não há dígitos", () => {
    expect(parseMoneyInput("")).toBe("");
    expect(parseMoneyInput("R$")).toBe("");
  });
});
