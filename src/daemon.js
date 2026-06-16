const crypto = require('crypto')
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
  return `daemon-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function _sanitizeForLog(value, maxLen = 512) {
  const str = typeof value === 'string' ? value : String(value ?? '')
  const stripped = str.replace(/[\x00-\x1F\x7F]/g, ' ')
  return stripped.length > maxLen ? `${stripped.slice(0, maxLen)}…` : stripped
}

function _errorToString(err) {
  if (err instanceof Error) return err.message
  if (typeof err === 'string') return err
  try { return JSON.stringify(err) }
  catch (_) { return String(err ?? 'unknown error') }
}

/**
 * Forward a capability task to the Python A2A server via JSON-RPC 2.0 and
 * return the artifact object (whatever the Python handler returned).
 *
 * Throws on network errors or non-200 HTTP responses so processTask can catch
 * and postResult with an error.
 */
function _forwardToA2A(capability, payload) {
  // The inner event must include `capability` so Python dispatch.py can route
  // it, plus all payload fields (task, cwd, operation, sessionId, ...).
  // capability is placed last so a payload.capability field from an untrusted
  // queue task cannot override the validated outer capability (P2 security fix).
  return sendEvent(`${config.a2aServerUrl()}/a2a/octowiz`, {
    method: 'octowiz/event',
    id: _rpcId(),
    payload: { ...payload, capability },
    headers: config.a2aServerAuthHeaders(),
    timeoutMs: config.a2aTimeoutMs(),
  })
}

async function processTask(task) {
  let id
  let leaseToken

  try {
    if (!task || typeof task !== 'object' || Array.isArray(task)) {
      logger.error('[octowiz - processTask] malformed task: expected object')
      return
    }

    const { id: taskId, capability, payload: rawPayload = {} } = task
    id = taskId

    if (typeof id !== 'string' || id.length === 0) {
      logger.error('[octowiz - processTask] malformed task: missing/invalid id')
      return
    }

    if (typeof capability !== 'string' || capability.length === 0) {
      try {
        const malformedClaim = await claimTask(id)
        if (!malformedClaim.ok) return
        await postResult(id, malformedClaim.leaseToken, {
          status: 'error',
          message: 'malformed task: missing/invalid capability',
        })
      }
      catch (err) {
        logger.error(
          `[octowiz - processTask] failed handling malformed capability for ${_sanitizeForLog(id)}: ${_sanitizeForLog(_errorToString(err))}`,
        )
      }
      return
    }

    const claim = await claimTask(id)
    if (!claim.ok) {
      // 409 = another instance claimed it; silently skip
      return
    }
    leaseToken = claim.leaseToken

    // Avoid mutating the inbound task's payload object.
    const payload = (rawPayload && typeof rawPayload === 'object' && !Array.isArray(rawPayload))
      ? { ...rawPayload }
      : {}

    if (!KNOWN_CAPABILITIES.has(capability)) {
      await postResult(id, leaseToken, { status: 'error', message: `unknown capability: ${capability}` })
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
      const { sessionId, advisory = {} } = payload
      if (!ALLOWED_ADVISORY_TYPES.has(advisory.type)) {
        await postResult(id, leaseToken, { status: 'error', failureKind: 'unknown-advisory-type', type: advisory.type })
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
    // AELLI_VALIDATOR_PRINCIPAL must match the OCTOWIZ_INBOUND_SECRET value that
    // this daemon uses when authenticating to AELLI's task queue.
    if (capability === 'router.validation-request') {
      const { workflowTaskId, draft = '' } = payload
      // Validate payload shape before JS syntax check so callers get an explicit
      // error rather than an empty-draft failure for a missing field.
      if (typeof workflowTaskId !== 'string' || typeof draft !== 'string') {
        await postResult(id, leaseToken, { status: 'completed', workflowTaskId, passed: false, failureKind: 'invalid-payload' })
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
    const safeId = _sanitizeForLog(id)
    const safeErr = _sanitizeForLog(_errorToString(err))
    logger.error(`[octowiz - processTask] unhandled error${id ? ` for ${safeId}` : ''}: ${safeErr}`)

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
  const queueUrl = config.queueUrl()
  subscribeToQueue(queueUrl, processTask)
  logger.log(`[octowiz - startup] subscribed to task queue at ${queueUrl}`)
}

module.exports = { start, processTask, _forwardToA2A }
