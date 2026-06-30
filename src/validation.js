'use strict'

const vm = require('node:vm')

// NOTE FOR CALLERS / PIPELINE OWNERS:
// This module performs JavaScript syntax validation only.
// It does not detect source format (e.g., JSON vs JS) and does not execute code.
// Upstream ingestion should perform any required format parsing/validation first
// (for example, JSON.parse for JSON payloads) before invoking this validator.
//
// NOTE ON COMPILATION BOUNDARIES:
// `vm.Script` compiles source but does not execute it. This function intentionally
// does not call `.runInContext()` / `.runInNewContext()`.
// If strict runtime/resource boundaries are required for broader workflows,
// enforce size/time limits upstream; non-syntax compilation failures surface as
// `compile-error` in this API.

// Defensive ceiling to reduce memory/event-loop risk from unusually large inputs.
// This is defense-in-depth; upstream should still enforce payload limits.
const MAX_SOURCE_LENGTH_BYTES = 10 * 1024 * 1024 // 10 MiB

// Bound output size so error payloads remain predictable.
const MAX_OUTPUT_LENGTH = 512

// Named failure kinds so callers can branch on constants instead of string literals.
const VALIDATION_FAILURE_KINDS = Object.freeze({
  EMPTY_DRAFT: 'empty-draft',
  SYNTAX_ERROR: 'syntax-error',
  COMPILE_ERROR: 'compile-error',
})

/**
 * Safely stringifies and bounds output text.
 *
 * @param {unknown} value
 * @returns {string}
 */
function safeOutput(value) {
  return String(value ?? '').slice(0, MAX_OUTPUT_LENGTH)
}

/**
 * Validation result for JavaScript syntax checks.
 *
 * @typedef {object} JavaScriptSyntaxValidationPassResult
 * @property {true} passed - The draft passed syntax validation.
 *
 * @typedef {object} JavaScriptSyntaxValidationFailResult
 * @property {false} passed - The draft failed syntax validation.
 * @property {'empty-draft'|'syntax-error'|'compile-error'} failureKind - Categorical failure identifier.
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
 * Error detail note: `output` may include Node/V8 parser messages, but is
 * truncated to a fixed maximum length.
 *
 * @param {unknown} draft - Candidate JavaScript source to validate.
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

  if (Buffer.byteLength(draft, 'utf8') > MAX_SOURCE_LENGTH_BYTES) {
    return {
      passed: false,
      failureKind: VALIDATION_FAILURE_KINDS.COMPILE_ERROR,
      output: 'Source exceeds compilation size limits.',
    }
  }

  try {
    new vm.Script(draft, { filename: 'draft.js' })
    return { passed: true }
  }
  catch (err) {
    // instanceof catches the common case; the name check is the cross-realm fallback.
    if (err instanceof SyntaxError || (err && err.name === 'SyntaxError')) {
      return {
        passed: false,
        failureKind: VALIDATION_FAILURE_KINDS.SYNTAX_ERROR,
        output: safeOutput((err && err.message) || 'Syntax validation failed.'),
      }
    }

    // Non-syntax VM errors (e.g. resource limits) — surface as a distinct failure rather than silently passing.
    return {
      passed: false,
      failureKind: VALIDATION_FAILURE_KINDS.COMPILE_ERROR,
      output: safeOutput((err && err.message) || 'Compilation failed.'),
    }
  }
}

module.exports = Object.freeze({ validateJavaScriptSyntax, VALIDATION_FAILURE_KINDS })
