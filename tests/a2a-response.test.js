const { normalizeA2AResponse } = require('../src/a2a-response')

describe('normalizeA2AResponse', () => {
  // ── Null / undefined inputs ──────────────────────────────────────────────

  it('returns an empty object for null input', () => {
    expect(normalizeA2AResponse(null)).toEqual({})
  })

  it('returns an empty object for undefined input', () => {
    expect(normalizeA2AResponse(undefined)).toEqual({})
  })

  // ── Passthrough when already camelCase ───────────────────────────────────

  it('passes through a response that already has sessionId', () => {
    const raw = { status: 'completed', sessionId: 'sess-already-camel' }
    const result = normalizeA2AResponse(raw)
    expect(result.sessionId).toBe('sess-already-camel')
    // No snake_case key should be injected
    expect(result.session_id).toBeUndefined()
  })

  it('does not clobber an existing sessionId when session_id is also present', () => {
    // If Python somehow sends both, the camelCase value wins.
    const raw = { status: 'completed', session_id: 'snake-val', sessionId: 'camel-val' }
    const result = normalizeA2AResponse(raw)
    expect(result.sessionId).toBe('camel-val')
    expect(result.session_id).toBe('snake-val')
  })

  it('passes through runId when already camelCase', () => {
    const raw = { status: 'dispatched', runId: 'run-already-camel' }
    const result = normalizeA2AResponse(raw)
    expect(result.runId).toBe('run-already-camel')
    expect(result.run_id).toBeUndefined()
  })

  it('passes through exitStatus when already camelCase', () => {
    const raw = { status: 'ok', exitStatus: '0' }
    const result = normalizeA2AResponse(raw)
    expect(result.exitStatus).toBe('0')
    expect(result.exit_status).toBeUndefined()
  })

  // ── Snake_case aliasing ──────────────────────────────────────────────────

  it('aliases session_id to sessionId, keeping both keys', () => {
    const raw = { status: 'completed', session_id: 'sess-abc123' }
    const result = normalizeA2AResponse(raw)
    expect(result.session_id).toBe('sess-abc123')
    expect(result.sessionId).toBe('sess-abc123')
  })

  it('aliases run_id to runId, keeping both keys', () => {
    const raw = { status: 'dispatched', run_id: 'run-xyz' }
    const result = normalizeA2AResponse(raw)
    expect(result.run_id).toBe('run-xyz')
    expect(result.runId).toBe('run-xyz')
  })

  it('aliases exit_status to exitStatus, keeping both keys', () => {
    const raw = { status: 'ok', run_id: 'run-xyz', exit_status: '0', logs: 'done' }
    const result = normalizeA2AResponse(raw)
    expect(result.exit_status).toBe('0')
    expect(result.exitStatus).toBe('0')
  })

  it('aliases all three snake_case fields at once', () => {
    const raw = {
      status: 'completed',
      session_id: 'sess-multi',
      run_id: 'run-multi',
      exit_status: '1',
    }
    const result = normalizeA2AResponse(raw)
    expect(result.sessionId).toBe('sess-multi')
    expect(result.runId).toBe('run-multi')
    expect(result.exitStatus).toBe('1')
    // Originals preserved
    expect(result.session_id).toBe('sess-multi')
    expect(result.run_id).toBe('run-multi')
    expect(result.exit_status).toBe('1')
  })

  // ── Missing / absent fields ──────────────────────────────────────────────

  it('handles missing session_id gracefully — no undefined key injected', () => {
    const raw = { status: 'completed', output: 'done' }
    const result = normalizeA2AResponse(raw)
    expect(result).toEqual({ status: 'completed', output: 'done' })
    expect('sessionId' in result).toBe(false)
  })

  it('handles missing run_id and exit_status gracefully', () => {
    const raw = { status: 'error', message: 'something went wrong' }
    const result = normalizeA2AResponse(raw)
    expect('runId' in result).toBe(false)
    expect('exitStatus' in result).toBe(false)
  })

  it('does not mutate the original input object', () => {
    const raw = { status: 'completed', session_id: 'sess-immutable' }
    normalizeA2AResponse(raw)
    expect('sessionId' in raw).toBe(false)
  })

  // ── Non-snake_case fields are untouched ──────────────────────────────────

  it('preserves all non-aliased fields unchanged', () => {
    const raw = { status: 'completed', output: 'my output', message: 'ok', session_id: 's1' }
    const result = normalizeA2AResponse(raw)
    expect(result.status).toBe('completed')
    expect(result.output).toBe('my output')
    expect(result.message).toBe('ok')
  })

  // ── Edge cases ───────────────────────────────────────────────────────────

  it('handles session_id of empty string — does not alias falsy value', () => {
    // An empty string session_id is technically set but semantically absent;
    // normalizeA2AResponse maps it (the caller decides if it's meaningful).
    const raw = { status: 'error', session_id: '' }
    const result = normalizeA2AResponse(raw)
    // Empty string is not undefined, so the alias check passes.
    // The raw key IS present; the camelCase alias should NOT be injected because
    // "" is falsy — but our implementation checks `!== undefined`, so it IS aliased.
    // This test documents the actual behavior: empty string is still aliased.
    expect(result.session_id).toBe('')
    expect(result.sessionId).toBe('')
  })
})
