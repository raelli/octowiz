const crypto = require('node:crypto')
const { subscribeToQueue } = require('./a2a-client')
const { normalizeA2AResponse } = require('./a2a-response')
const { sendEvent } = require('./a2a-transport')
const config = require('./config')
const logger = require('./logger')
const { checkStartup, validateCwd } = require('./policy')
const { claimTask, postResult } = require('./task-queue-client')
const { validateJavaScriptSyntax } = require('./validation')

const ALLOWED_ADVISORY_TYPES = new Set(['file-conflict', 'branch-drift', 'spec-deviation'])

const KNOWN_CAPABILITIES = new Set([
  'octowiz.dispatch',
  'octowiz.manage_agents',
  'octowiz.observe',
  'octowiz.load_memory',
  'octowiz.escalate_to_aelli',
  'octowiz.plan',
  'octowiz.review',
  'octowiz.write_diary',
  'octowiz.run_sandboxed',
  'octowiz.marketplace_info',
  'router.validation-request',
])

function _rpcId() {
  if (typeof crypto.randomUUID === 'function') {
    return `daemon-${crypto.randomUUID()}`
  }
  return `daemon-${Date.now()}-${crypto.randomBytes(8).toString('hex')}`
}

function _sanitizeForLog(value, maxLen = 512) {
  const str = typeof value === 'string' ? value : String(value ?? '')
  // Strip C0 and C1 control characters before logging — intentional control-char range.
  // eslint-disable-next-line no-control-regex
  const stripped = str.replace(/[\x00-\x1F\x7F-\x9F]/g, ' ')
  // Code-unit length >= code-point count, so this is a safe early exit for small inputs.
  if (stripped.length <= maxLen) return stripped
  const glyphs = Array.from(stripped)
  return glyphs.length > maxLen ? `${glyphs.slice(0, maxLen).join('')}…` : stripped
}

function _errorToString(err) {
  if (err instanceof Error)
    return err.message
  if (typeof err === 'string')
    return err
  try { return JSON.stringify(err) }
  catch { return String(err ?? 'unknown error') }
}

function _clonePayload(rawPayload) {
  if (!rawPayload || typeof rawPayload !== 'object' || Array.isArray(rawPayload)) {
    return {}
  }

  if (typeof globalThis.structuredClone === 'function') {
    try {
      return globalThis.structuredClone(rawPayload)
    }
    catch {
      // Fall through to JSON-safe clone for non-cloneable values.
    }
  }

  try {
    return JSON.parse(JSON.stringify(rawPayload))
  }
  catch {
    return {}
  }
}

function _getA2AServerUrl() {
  const url = config.a2aServerUrl()
  let parsed
  try {
    parsed = new URL(url)
  }
  catch {
    throw new Error(`invalid A2A server URL: ${url}`)
  }
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    throw new Error(`A2A server URL must use http or https (got ${parsed.protocol.slice(0, -1)})`)
  }
  return url
}

/**
 * Forward a capability task to the Python A2A server via JSON-RPC 2.0 and
 * return the artifact object (whatever the Python handler returned).
 *
 * Throws on network errors or non-200 HTTP responses.
 * Callers MUST handle rejections (e.g. with try/catch) when using this API.
 */
async function _forwardToA2A(capability, payload) {
  try {
    const a2aUrl = _getA2AServerUrl()
    // capability is placed last so untrusted payload.capability cannot override it.
    return await sendEvent(`${a2aUrl}/a2a/octowiz`, {
      method: 'octowiz/event',
      id: _rpcId(),
      payload: { ...payload, capability },
      headers: config.a2aServerAuthHeaders(),
      timeoutMs: config.a2aTimeoutMs(),
    })
  }
  catch (err) {
    const wrapped = new Error(`A2A forward failed: ${_errorToString(err)}`)
    wrapped.name = 'A2AForwardError'
    wrapped.cause = err
    throw wrapped
  }
}

async function processTask(task) {
  let id
  let leaseToken

  try {
    if (!task || typeof task !== 'object' || Array.isArray(task)) {
      logger.error('[octowiz - processTask] malformed task: expected object')
      // NOTE: cannot ack/post result without a valid task id; queue adapter must drop/DLQ malformed envelopes.
      return
    }

    const { id: taskId, capability, payload: rawPayload = {} } = task
    id = taskId

    if (typeof id !== 'string' || id.length === 0) {
      logger.error('[octowiz - processTask] malformed task: missing/invalid id')
      // NOTE: cannot claim/post without an id; queue adapter must handle malformed messages.
      return
    }

    const claim = await claimTask(id)
    if (!claim.ok) {
      // 409 = another instance claimed it; silently skip.
      return
    }
    leaseToken = claim.leaseToken

    if (typeof capability !== 'string' || capability.length === 0) {
      await postResult(id, leaseToken, {
        status: 'error',
        failureKind: 'malformed-task',
        message: 'malformed task: missing/invalid capability',
      })
      return
    }

    const payload = _clonePayload(rawPayload)

    if (!KNOWN_CAPABILITIES.has(capability)) {
      await postResult(id, leaseToken, { status: 'error', failureKind: 'unknown-capability', message: `unknown capability: ${_sanitizeForLog(capability, 128)}` })
      return
    }

    // CWD validation is a security boundary that stays in the daemon even though
    // Python also validates cwd. This ensures bad paths are rejected before they
    // ever leave the trusted JS process.
    if (payload.cwd) {
      try { payload.cwd = validateCwd(payload.cwd) }
      catch (err) {
        await postResult(id, leaseToken, { status: 'error', message: _errorToString(err) })
        return
      }
    }

    // octowiz.observe is handled locally — no A2A forwarding needed.
    // Log the advisory and echo it back as the artifact.
    if (capability === 'octowiz.observe') {
      const { sessionId } = payload
      const advisory = payload.advisory ?? {}
      if (!ALLOWED_ADVISORY_TYPES.has(advisory.type)) {
        await postResult(id, leaseToken, { status: 'error', failureKind: 'unknown-advisory-type', message: `unknown advisory type: ${_sanitizeForLog(advisory.type, 64)}`, type: advisory.type })
        return
      }
      logger.log(
        `[octowiz - observe] advisory for session ${_sanitizeForLog(sessionId)}: ${_sanitizeForLog(advisory.type)} — ${_sanitizeForLog(advisory.message)}`,
      )
      await postResult(id, leaseToken, { status: 'completed', advisory })
      return
    }

    // router.validation-request is handled locally: validate the draft and post
    // the result back so AELLI's onTaskComplete callback resolves the gate.
    if (capability === 'router.validation-request') {
      const { workflowTaskId, draft = '' } = payload
      // Validate payload shape before JS syntax check so callers get an explicit
      // error rather than an empty-draft failure for a missing field.
      if (typeof workflowTaskId !== 'string' || typeof draft !== 'string') {
        await postResult(id, leaseToken, {
          status: 'completed',
          ...(typeof workflowTaskId === 'string' ? { workflowTaskId } : {}),
          passed: false,
          failureKind: 'invalid-payload',
        })
        return
      }
      const validation = validateJavaScriptSyntax(draft)
      await postResult(id, leaseToken, {
        status: 'completed',
        workflowTaskId,
        passed: validation.passed,
        ...(validation.failureKind ? { failureKind: validation.failureKind } : {}),
        ...(validation.output ? { output: validation.output } : {}),
      })
      return
    }

    const artifact = await _forwardToA2A(capability, payload)
    // normalizeA2AResponse handles null/undefined (returns {}) and adds camelCase
    // aliases for any recognized snake_case fields (session_id → sessionId, etc.).
    const normalized = normalizeA2AResponse(artifact)
    // Normalize: Python capabilities use "error" for failures; queue needs
    // "completed" vs "error".
    const queueStatus = normalized.status === 'error' ? 'error' : 'completed'
    await postResult(id, leaseToken, { ...normalized, status: queueStatus })
  }
  catch (err) {
    const safeId = id ? _sanitizeForLog(id) : ''
    const safeErr = _sanitizeForLog(_errorToString(err))
    logger.error(`[octowiz - processTask] unhandled error${safeId ? ` for ${safeId}` : ''}: ${safeErr}`)

    if (id && leaseToken) {
      try {
        await postResult(id, leaseToken, { status: 'error', message: _errorToString(err) })
      }
      catch (postErr) {
        logger.error(`[octowiz - processTask] failed to post error result for ${safeId}: ${_sanitizeForLog(_errorToString(postErr))}`)
      }
    }
  }
}

function start() {
  checkStartup()
  // Validate early so boot fails fast on misconfiguration.
  _getA2AServerUrl()

  const queueUrl = config.queueUrl()
  subscribeToQueue(queueUrl, processTask)
  logger.log(`[octowiz - startup] subscribed to task queue at ${queueUrl}`)
}

module.exports = { start, processTask, _forwardToA2A }
