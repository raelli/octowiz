'use strict'

// Checks JavaScript syntax only via Node's vm module.
// Non-JS content that parses as valid JS is accepted; caller is responsible
// for any upstream format validation (e.g. JSON.parse before this).
function validateJavaScriptSyntax(draft) {
  if (!draft || typeof draft !== 'string' || draft.trim() === '') {
    return { passed: false, failureKind: 'empty-draft', output: 'Draft is empty.' }
  }

  try {
    const vm = require('node:vm')
    void new vm.Script(draft, { displayErrors: false })
    return { passed: true }
  }
  catch (err) {
    if (err.name === 'SyntaxError') {
      return { passed: false, failureKind: 'syntax-error', output: err.message }
    }
    // Non-syntax errors (e.g. resource limits) — pass through; don't block.
    return { passed: true }
  }
}

module.exports = { validateJavaScriptSyntax }
