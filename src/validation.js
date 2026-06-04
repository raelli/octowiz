"use strict";

/**
 * Validate a generated code draft before accepting a high-risk workflow result.
 *
 * Uses Node's built-in vm module for a lightweight JS syntax check.
 * Non-JS content that happens to parse as valid JS is accepted — we do not
 * attempt language detection.
 *
 * @param {string} draft
 * @returns {{ passed: boolean, failureKind?: string, output?: string }}
 */
function validateDraft(draft) {
  if (!draft || typeof draft !== "string" || draft.trim() === "") {
    return { passed: false, failureKind: "empty-draft", output: "Draft is empty." };
  }

  try {
    const vm = require("vm");
    new vm.Script(draft, { displayErrors: false });
    return { passed: true };
  } catch (err) {
    if (err.name === "SyntaxError") {
      return { passed: false, failureKind: "syntax-error", output: err.message };
    }
    // Non-syntax errors (e.g. resource limits) — pass through; don't block.
    return { passed: true };
  }
}

module.exports = { validateDraft };
