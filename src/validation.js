'use strict'

const vm = require('node:vm')

// NOTE FOR CALLERS / PIPELINE OWNERS:
// This module performs JavaScript syntax validation only.
// It does not detect source format (e.g., JSON vs JS) and does not execute code.
// Upstream ingestion should perform any required format parsing/validation first
// (for example, JSON.parse for JSON payloads) before invoking this validator.

// Named failure kinds so callers can branch on constants instead of string literals.
const VALIDATION_FAILURE_KINDS = Object.freeze({
  EMPTY_DRAFT: 'empty-draft',
  SYNTAX_ERROR: 'syntax-error',
  COMPILE_ERROR: 'compile-error',
})

/**
 * Validation result for JavaScript syntax checks.
 *
 * @typedef {object} JavaScriptSyntaxValidationPassResult
 * @property {true} passed - The draft passed syntax validation.
 *
 * @typedef {object} JavaScriptSyntaxValidationFailResult
 * @property {false} passed - The draft failed syntax validation.
 * @property {string} failureKind - One of VALIDATION_FAILURE_KINDS.
 * @property {string} [output] - Human-readable detail about the validation outcome.
 *
 * @typedef {JavaScriptSyntaxValidationPassResult | JavaScriptSyntaxValidationFailResult} JavaScriptSyntaxValidationResult
 */

/**
 * Checks JavaScript syntax only via Node's vm module.
 * Non-JS content that parses as valid JS is accepted; caller is responsible
 * for any upstream format validation (e.g. JSON.parse before this).
 *
 * Runtime behavior is defensive: non-string input is handled and returned
 * as a structured validation failure rather than throwing.
 *
 * Error detail note: `output` may include raw Node/V8 parser messages.
 * If returning results to untrusted clients, sanitize/truncate `output`
 * in an outer middleware layer.
 *
 * @param {*} draft - Candidate JavaScript source to validate.
 * @returns {JavaScriptSyntaxValidationResult} Validation result with pass/fail status and optional failure detail.
 */
function validateJavaScriptSyntax(draft) {
  if (typeof draft !== 'string') {
    return {
      passed: false,
      failureKind: VALIDATION_FAILURE_KINDS.EMPTY_DRAFT,
      output: 'Draft must be a string.',
    }
  }
  if (!draft.trim()) {
    return {
      passed: false,
      failureKind: VALIDATION_FAILURE_KINDS.EMPTY_DRAFT,
      output: 'Draft is empty or whitespace only.',
    }
  }

  try {
    new vm.Script(draft)
    return { passed: true }
  }
  catch (err) {
    // instanceof catches the common case; the name check is the cross-realm fallback.
    if (err instanceof SyntaxError || (err && err.name === 'SyntaxError')) {
      return {
        passed: false,
        failureKind: VALIDATION_FAILURE_KINDS.SYNTAX_ERROR,
        output: err.message,
      }
    }

    // Non-syntax VM errors (e.g. resource limits) — surface as a distinct failure rather than silently passing.
    return {
      passed: false,
      failureKind: VALIDATION_FAILURE_KINDS.COMPILE_ERROR,
      output: err instanceof Error ? err.message : 'Compilation failed.',
    }
  }
}

module.exports = { validateJavaScriptSyntax, VALIDATION_FAILURE_KINDS }
