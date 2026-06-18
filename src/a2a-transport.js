// A2A TRANSPORT — the single owner of how the Bridge speaks JSON-RPC 2.0
// to A2A endpoints (the Python A2A server, AELLI, the LiteLLM gateway).
//
// Owns: the request envelope, artifact extraction, HTTP POST with timeout,
// and the error vocabulary. Callers say what they want sent where; nothing
// outside this module builds an envelope or walks an RPC response.

const http = require('node:http')
const https = require('node:https')

// JSON-RPC 2.0 envelope around a single text part. `text` may be null for an
// intentionally empty parts array (used by diagnostics probes). id, role, and
// messageId are included only when given — the Python parser and AELLI both
// accept the minimal shape, and existing endpoints see exactly the bytes the
// pre-transport call sites sent.
function buildEnvelope(method, text, opts = {}) {
  const { id, role, messageId } = opts
  return {
    jsonrpc: '2.0',
    method,
    ...(id !== undefined ? { id } : {}),
    params: {
      message: {
        ...(role !== undefined ? { role } : {}),
        ...(messageId !== undefined ? { messageId } : {}),
        parts: text === null || text === undefined ? [] : [{ kind: 'text', text }],
      },
    },
  }
}

// Pull the artifact out of a JSON-RPC response: result.artifacts[0].parts[0].text,
// parsed as JSON. Returns `fallback` when no artifact text is present OR when the
// parsed artifact is null. Throws on malformed artifact JSON — the caller decides
// whether that is fatal or fail-open.
function extractArtifact(rpc, fallback = {}) {
  const text = rpc?.result?.artifacts?.[0]?.parts?.[0]?.text
  if (typeof text !== 'string' || text === '')
    return fallback
  const parsed = JSON.parse(text)
  return parsed === null ? fallback : parsed
}

// JSON-over-HTTP primitive. Resolves { status, body } where body is parsed
// JSON when possible, raw text otherwise. Rejects on network failure and on
// timeout (with an explicit message). Never rejects on HTTP status — status
// policy belongs to the caller.
function httpJson(method, urlStr, body = null, { headers = {}, timeoutMs = 30_000 } = {}) {
  return new Promise((resolve, reject) => {
    const url = new URL(urlStr)
    if (url.protocol !== 'http:' && url.protocol !== 'https:')
      throw new Error(`Unsupported protocol: ${url.protocol}`)

    const isHttps = url.protocol === 'https:'
    const lib = isHttps ? https : http
    const payload = body === null ? null : JSON.stringify(body)

    const options = {
      hostname: url.hostname,
      port: url.port || (isHttps ? 443 : 80),
      path: url.pathname + url.search,
      method,
      headers: {
        ...(payload !== null ? { 'Content-Type': 'application/json' } : {}),
        ...(payload !== null ? { 'Content-Length': Buffer.byteLength(payload) } : {}),
        ...headers,
      },
    }

    let settled = false
    const onceResolve = (value) => {
      if (settled)
        return
      settled = true
      resolve(value)
    }
    const onceReject = (err) => {
      if (settled)
        return
      settled = true
      reject(err)
    }

    const req = lib.request(options, (res) => {
      res.on('error', onceReject)
      const chunks = []
      res.on('data', chunk => chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk)))
      res.on('end', () => {
        const data = Buffer.concat(chunks).toString('utf8')
        let parsed
        try {
          parsed = data === '' ? '' : JSON.parse(data)
        }
        catch {
          parsed = data
        }
        onceResolve({ status: res.statusCode, body: parsed })
      })
    })

    req.setTimeout(timeoutMs, () => {
      req.destroy(new Error(`request timed out after ${timeoutMs}ms`))
    })
    req.on('error', onceReject)

    if (payload !== null)
      req.write(payload)
    req.end()
  })
}

// Send one A2A event and return its artifact.
//
// Serializes `payload` as the envelope's text part, POSTs it, and extracts
// the artifact (`fallback` — default {} — when the response carries none).
// Throws on network error, non-200 status, RPC error object, invalid JSON-RPC
// body shape, or malformed artifact JSON; the caller owns the recovery policy.
async function sendEvent(
  urlStr,
  { method, payload, id, role, messageId, headers = {}, timeoutMs = 30_000, fallback = {} } = {},
) {
  const envelope = buildEnvelope(method, JSON.stringify(payload), { id, role, messageId })
  const { status, body } = await httpJson('POST', urlStr, envelope, { headers, timeoutMs })

  if (status !== 200) {
    const excerpt = typeof body === 'string' ? body : JSON.stringify(body)
    throw new Error(`A2A server returned HTTP ${status}: ${String(excerpt).slice(0, 200)}`)
  }

  // A 200 whose body did not parse as a JSON object (or is an array) is a failure.
  if (typeof body !== 'object' || body === null || Array.isArray(body)) {
    throw new Error(`Failed to parse A2A response: non-JSON body: ${String(body).slice(0, 200)}`)
  }

  // JSON-RPC application-level error over HTTP 200.
  if ('error' in body && body.error && typeof body.error === 'object') {
    const code = String(body.error.code ?? '?')
    const message = String(body.error.message ?? 'Unknown RPC error')
    throw new Error(`A2A RPC error ${code}: ${message}`)
  }

  try {
    return extractArtifact(body, fallback)
  }
  catch (err) {
    throw new Error(`Failed to parse A2A response: ${err.message}`, { cause: err })
  }
}

module.exports = { buildEnvelope, extractArtifact, httpJson, sendEvent }
