'use strict'

const http = require('node:http')

// Helper — spin up a real HTTP server that serves programmed responses in order.
// Each entry in `responses` is served to one incoming request; the last entry
// repeats if the client makes more calls than entries.
function makeServer(responses) {
  let i = 0
  const requests = []
  const server = http.createServer((req, res) => {
    let body = ''
    req.on('data', c => (body += c))
    req.on('end', () => {
      try { requests.push(JSON.parse(body)) }
      catch { requests.push(body) }
      const r = responses[Math.min(i++, responses.length - 1)]
      res.writeHead(r.status, { 'Content-Type': 'application/json' })
      res.end(JSON.stringify(r.body ?? {}))
    })
  })
  return new Promise((resolve) => {
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address()
      resolve({ server, port, requests })
    })
  })
}

function closeServer(server) {
  return new Promise(resolve => server.close(resolve))
}

// ── claimTask ──────────────────────────────────────────────────────────────

describe('claimTask', () => {
  let server, port, claimTask

  afterEach(async () => {
    if (server)
      await closeServer(server)
    jest.resetModules()
    delete process.env.AELLI_BASE_URL
  })

  it('returns ok:true with leaseToken on 200', async () => {
    ({ server, port } = await makeServer([{ status: 200, body: { leaseToken: 'tok-abc' } }]))
    process.env.AELLI_BASE_URL = `http://127.0.0.1:${port}`;
    ({ claimTask } = require('../src/task-queue-client'))

    const result = await claimTask('task-1')

    expect(result).toEqual({ ok: true, leaseToken: 'tok-abc' })
  })

  it('returns ok:false with body error message on non-200', async () => {
    ({ server, port } = await makeServer([{ status: 409, body: { error: 'already claimed' } }]))
    process.env.AELLI_BASE_URL = `http://127.0.0.1:${port}`;
    ({ claimTask } = require('../src/task-queue-client'))

    const result = await claimTask('task-2')

    expect(result).toEqual({ ok: false, reason: 'already claimed' })
  })

  it('returns ok:false with HTTP <N> reason when body has no error field', async () => {
    ({ server, port } = await makeServer([{ status: 404, body: {} }]))
    process.env.AELLI_BASE_URL = `http://127.0.0.1:${port}`;
    ({ claimTask } = require('../src/task-queue-client'))

    const result = await claimTask('task-3')

    expect(result).toEqual({ ok: false, reason: 'HTTP 404' })
  })
})

// ── postResult ─────────────────────────────────────────────────────────────

describe('postResult', () => {
  let server, port, postResult

  afterEach(async () => {
    if (server)
      await closeServer(server)
    jest.resetModules()
    delete process.env.AELLI_BASE_URL
  })

  it('resolves after one call on 200', async () => {
    const ctx = await makeServer([{ status: 200 }])
    server = ctx.server; port = ctx.port
    process.env.AELLI_BASE_URL = `http://127.0.0.1:${port}`;
    ({ postResult } = require('../src/task-queue-client'))

    await postResult('task-1', 'lease-1', { status: 'completed' })

    expect(ctx.requests).toHaveLength(1)
    expect(ctx.requests[0]).toMatchObject({ leaseToken: 'lease-1', status: 'completed' })
  })

  it('resolves after one call on 409 (lease expired — silent discard)', async () => {
    const ctx = await makeServer([{ status: 409 }])
    server = ctx.server; port = ctx.port
    process.env.AELLI_BASE_URL = `http://127.0.0.1:${port}`;
    ({ postResult } = require('../src/task-queue-client'))

    await postResult('task-2', 'stale-lease', { status: 'completed' })

    expect(ctx.requests).toHaveLength(1)
  })

  it('retries exactly 3 times on persistent 500, then resolves', async () => {
    const ctx = await makeServer([{ status: 500 }]) // repeats on every call
    server = ctx.server; port = ctx.port
    process.env.AELLI_BASE_URL = `http://127.0.0.1:${port}`;
    ({ postResult } = require('../src/task-queue-client'))

    await postResult('task-3', 'lease-3', { status: 'completed' })

    expect(ctx.requests).toHaveLength(3)
  })

  it('retries on 503 (5xx is retried)', async () => {
    const ctx = await makeServer([{ status: 503 }])
    server = ctx.server; port = ctx.port
    process.env.AELLI_BASE_URL = `http://127.0.0.1:${port}`;
    ({ postResult } = require('../src/task-queue-client'))

    await postResult('task-4', 'lease-4', { status: 'completed' })

    expect(ctx.requests).toHaveLength(3)
  })

  it('resolves after first attempt on 4xx without retrying', async () => {
    const ctx = await makeServer([{ status: 400 }])
    server = ctx.server; port = ctx.port
    process.env.AELLI_BASE_URL = `http://127.0.0.1:${port}`;
    ({ postResult } = require('../src/task-queue-client'))

    await postResult('task-5', 'lease-5', { status: 'completed' })

    expect(ctx.requests).toHaveLength(1)
  })

  it('retries on network error and logs after all retries exhausted', async () => {
    server = null // no server — connections will be refused
    process.env.AELLI_BASE_URL = 'http://127.0.0.1:1' // port 1 always refuses
    jest.resetModules();
    ({ postResult } = require('../src/task-queue-client'))

    const logger = require('../src/logger')
    const errorSpy = jest.spyOn(logger, 'error').mockImplementation(() => {})

    await postResult('task-6', 'lease-6', { status: 'completed' })

    expect(errorSpy).toHaveBeenCalledWith(
      expect.stringContaining('postResult failed after retries:'),
    )
    errorSpy.mockRestore()
  })
})
