'use strict'

const vm = require('node:vm')

// Named failure kinds so callers can branch on a constant instead of a literal.
const VALIDATION_FAILURE_KINDS = Object.freeze({
  EMPTY_DRAFT: 'empty-draft',
  SYNTAX_ERROR: 'syntax-error',
  COMPILE_ERROR: 'compile-error',
})

// Checks JavaScript syntax only via Node's vm module.
// Non-JS content that parses as valid JS is accepted; caller is responsible
// for any upstream format validation (e.g. JSON.parse before this).
function validateJavaScriptSyntax(draft) {
  if (typeof draft !== 'string' || draft.trim() === '') {
    return { passed: false, failureKind: VALIDATION_FAILURE_KINDS.EMPTY_DRAFT, output: 'Draft is empty.' }
  }

  try {
    void new vm.Script(draft)
    return { passed: true }
  }
  catch (err) {
    // instanceof catches the common case; the name check is the cross-realm fallback.
    if (err instanceof SyntaxError || (err && err.name === 'SyntaxError')) {
      return { passed: false, failureKind: VALIDATION_FAILURE_KINDS.SYNTAX_ERROR, output: err.message }
    }
    // Non-syntax VM errors (e.g. resource limits) — surface as a distinct failure rather than silently passing.
    return { passed: false, failureKind: VALIDATION_FAILURE_KINDS.COMPILE_ERROR, output: err instanceof Error ? err.message : 'Compilation failed.' }
  }
}

module.exports = { validateJavaScriptSyntax, VALIDATION_FAILURE_KINDS }
