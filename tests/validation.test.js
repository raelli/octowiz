"use strict";

const { validateDraft } = require("../src/validation");

describe("validateDraft", () => {
  it("passes valid JavaScript", () => {
    expect(validateDraft("const x = 1 + 2;")).toEqual({ passed: true });
  });

  it("passes a multi-line async function", () => {
    const code = `
      async function fetchData(url) {
        const res = await fetch(url);
        return res.json();
      }
    `;
    expect(validateDraft(code)).toEqual({ passed: true });
  });

  it("fails empty string with empty-draft", () => {
    expect(validateDraft("")).toMatchObject({ passed: false, failureKind: "empty-draft" });
    expect(validateDraft("   ")).toMatchObject({ passed: false, failureKind: "empty-draft" });
  });

  it("fails null with empty-draft", () => {
    expect(validateDraft(null)).toMatchObject({ passed: false, failureKind: "empty-draft" });
  });

  it("fails undefined with empty-draft", () => {
    expect(validateDraft(undefined)).toMatchObject({ passed: false, failureKind: "empty-draft" });
  });

  it("fails a JS syntax error with syntax-error and error message", () => {
    const result = validateDraft("function broken( {");
    expect(result).toMatchObject({ passed: false, failureKind: "syntax-error" });
    expect(typeof result.output).toBe("string");
    expect(result.output.length).toBeGreaterThan(0);
  });

  it("fails mismatched braces with syntax-error", () => {
    const result = validateDraft("const obj = { a: 1;");
    expect(result.passed).toBe(false);
    expect(result.failureKind).toBe("syntax-error");
  });
});
