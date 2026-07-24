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
    expect(VALIDATION_FAILURE_KINDS).toEqual({ EMPTY_DRAFT: 'empty-draft', SYNTAX_ERROR: 'syntax-error', COMPILE_ERROR: 'compile-error' })
    expect(Object.isFrozen(VALIDATION_FAILURE_KINDS)).toBe(true)
    expect(validateJavaScriptSyntax('').failureKind).toBe(VALIDATION_FAILURE_KINDS.EMPTY_DRAFT)
    expect(validateJavaScriptSyntax('function broken( {').failureKind).toBe(VALIDATION_FAILURE_KINDS.SYNTAX_ERROR)
  })
})

// ── error-message fallback (err?.message ?? default) ───────────────────────
// vm.Script's real SyntaxErrors always populate `.message`, so these paths
// can only be exercised by controlling what `vm.Script` throws.
describe('validateJavaScriptSyntax — error message fallback', () => {
  afterEach(() => {
    jest.dontMock('node:vm')
    jest.resetModules()
  })

  function withThrownError(thrown) {
    jest.resetModules()
    jest.doMock('node:vm', () => ({
      Script: class {
        constructor() {
          throw thrown
        }
      },
    }))
    return require('../src/validation').validateJavaScriptSyntax
  }

  it('uses err.message when present (syntax-error)', () => {
    const validate = withThrownError(new SyntaxError('Unexpected token )'))
    expect(validate('x')).toEqual({ passed: false, failureKind: 'syntax-error', output: 'Unexpected token )' })
  })

  it('falls back to default text when err.message is undefined (syntax-error)', () => {
    // A plain object with name 'SyntaxError' (not an Error instance) exercises the
    // `err?.name === 'SyntaxError'` cross-realm fallback and has no inherited
    // `.message` from Error.prototype (which otherwise defaults to '').
    const err = { name: 'SyntaxError' }
    const validate = withThrownError(err)
    expect(validate('x').output).toBe('Syntax validation failed.')
  })

  it('falls back to default text when err.message is null (syntax-error)', () => {
    // eslint-disable-next-line unicorn/error-message -- message is overwritten below to test the null case
    const err = new SyntaxError()
    err.message = null
    const validate = withThrownError(err)
    expect(validate('x').output).toBe('Syntax validation failed.')
  })

  it('preserves an empty-string err.message as-is rather than falling back (syntax-error)', () => {
    // eslint-disable-next-line unicorn/error-message -- message is overwritten below to test the empty-string case
    const err = new SyntaxError()
    err.message = ''
    const validate = withThrownError(err)
    // Documents the `??` behavior: an empty string is "present" and is not
    // replaced by the default fallback text, unlike the previous `||`.
    expect(validate('x').output).toBe('')
  })

  it('stringifies a non-string-like err.message (syntax-error)', () => {
    // eslint-disable-next-line unicorn/error-message -- message is overwritten below to test a non-string message
    const err = new SyntaxError()
    err.message = 404
    const validate = withThrownError(err)
    expect(validate('x').output).toBe('404')
  })

  it('falls back to default text when err.message is undefined (compile-error)', () => {
    // Plain object, no 'message' own or inherited property, and no name
    // matching 'SyntaxError' — falls into the compile-error branch.
    const err = {}
    const validate = withThrownError(err)
    const result = validate('x')
    expect(result.failureKind).toBe('compile-error')
    expect(result.output).toBe('Compilation failed.')
  })

  it('preserves an empty-string err.message as-is for compile-error too', () => {
    class NonSyntaxError extends Error {}
    const err = new NonSyntaxError('')
    const validate = withThrownError(err)
    const result = validate('x')
    expect(result.failureKind).toBe('compile-error')
    expect(result.output).toBe('')
  })
})
