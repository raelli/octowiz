'use strict'

const { validateJavaScriptSyntax, VALIDATION_FAILURE_KINDS } = require('../src/validation')

describe('validateJavaScriptSyntax', () => {
  it('passes valid JavaScript', () => {
    expect(validateJavaScriptSyntax('const x = 1 + 2;')).toEqual({ passed: true })
  })

  it('passes a multi-line async function', () => {
    const code = `
      async function fetchData(url) {
        const res = await fetch(url);
        return res.json();
      }
    `
    expect(validateJavaScriptSyntax(code)).toEqual({ passed: true })
  })

  it('fails empty string with empty-draft', () => {
    expect(validateJavaScriptSyntax('')).toMatchObject({ passed: false, failureKind: 'empty-draft' })
    expect(validateJavaScriptSyntax('   ')).toMatchObject({ passed: false, failureKind: 'empty-draft' })
  })

  it('fails null with empty-draft', () => {
    expect(validateJavaScriptSyntax(null)).toMatchObject({ passed: false, failureKind: 'empty-draft' })
  })

  it('fails undefined with empty-draft', () => {
    expect(validateJavaScriptSyntax(undefined)).toMatchObject({ passed: false, failureKind: 'empty-draft' })
  })

  it('fails a JS syntax error with syntax-error and error message', () => {
    const result = validateJavaScriptSyntax('function broken( {')
    expect(result).toMatchObject({ passed: false, failureKind: 'syntax-error' })
    expect(typeof result.output).toBe('string')
    expect(result.output.length).toBeGreaterThan(0)
  })

  it('fails mismatched braces with syntax-error', () => {
    const result = validateJavaScriptSyntax('const obj = { a: 1;')
    expect(result.passed).toBe(false)
    expect(result.failureKind).toBe('syntax-error')
  })

  it('exposes failure kinds as a frozen constant matching emitted values', () => {
    expect(VALIDATION_FAILURE_KINDS).toEqual({ EMPTY_DRAFT: 'empty-draft', SYNTAX_ERROR: 'syntax-error' })
    expect(Object.isFrozen(VALIDATION_FAILURE_KINDS)).toBe(true)
    expect(validateJavaScriptSyntax('').failureKind).toBe(VALIDATION_FAILURE_KINDS.EMPTY_DRAFT)
    expect(validateJavaScriptSyntax('function broken( {').failureKind).toBe(VALIDATION_FAILURE_KINDS.SYNTAX_ERROR)
  })
})
