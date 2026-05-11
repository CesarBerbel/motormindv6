import { describe, expect, it } from "vitest";
import { sanitizeRichHtml, sanitizePlainText } from "./sanitizeHtml";

describe("sanitizeRichHtml", () => {
  it("remove scripts, event handlers and iframe payloads", () => {
    const unsafe = '<p onclick="alert(1)">Olá</p><script>alert(1)</script><iframe srcdoc="<script>alert(1)</script>"></iframe>';
    const output = sanitizeRichHtml(unsafe);

    expect(output).toContain("Olá");
    expect(output).not.toContain("onclick");
    expect(output).not.toContain("script");
    expect(output).not.toContain("iframe");
    expect(output).not.toContain("srcdoc");
  });

  it("removes javascript links and unsafe target attributes", () => {
    const unsafe = '<a href="javascript:alert(1)" target="_self">ruim</a><a href="https://example.com" target="_blank">bom</a>';
    const output = sanitizeRichHtml(unsafe);

    expect(output).toContain("ruim");
    expect(output).not.toContain("javascript:");
    expect(output).not.toContain('target="_self"');
    expect(output).not.toContain('target="_blank"');
    expect(output).toContain('href="https://example.com"');
  });

  it("keeps safe Quill formatting and removes unsafe classes", () => {
    const html = '<p class="ql-align-center injected" style="color: rgb(255, 0, 0); position: absolute; background-image: url(javascript:alert(1))"><strong>Texto</strong></p>';
    const output = sanitizeRichHtml(html);

    expect(output).toContain("ql-align-center");
    expect(output).not.toContain("injected");
    expect(output).toContain("color:");
    expect(output).not.toContain("position");
    expect(output).not.toContain("background-image");
    expect(output).not.toContain("javascript:");
  });
});

describe("sanitizePlainText", () => {
  it("removes null bytes and trims text", () => {
    expect(sanitizePlainText("  abc\u0000  ")).toBe("abc");
  });
});
