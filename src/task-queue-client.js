const { httpJson } = require('./a2a-transport')
const config = require('./config')
const logger = require('./logger')

const RETRY_POLICY = {
  maxAttempts: 3,
  calculateBackoffMs(attempt) {
    const exponential = Math.min(15_000, (2 ** attempt) * 50)
    const jitter = Math.random() * 50
    return exponential + jitter
  },
  isRetryableStatus: status => status === 429 || status >= 500,
}

function _post(path, body) {
  return httpJson('POST', config.aelliBase() + path, body, {
    headers: config.queueAuthHeaders(),
    timeoutMs: 15_000,
  })
}

function _sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

/**
 * Claims a task lease.
 * Returns:
 *   { ok: true, leaseToken }
 *   { ok: false, reason }
 */
async function claimTask(taskId) {
  if (!taskId) {
    logger.error('[task-queue-client] claimTask validation failed: taskId is required')
    return { ok: false, reason: 'taskId is required' }
  }

  for (let attempt = 1; attempt <= RETRY_POLICY.maxAttempts; attempt++) {
    try {
      const { status, body } = await _post(`/a2a/task-queue/${encodeURIComponent(taskId)}/claim`, {})

      if (status === 200) {
        if (!body || typeof body.leaseToken !== 'string' || body.leaseToken.length === 0) {
          logger.error('[task-queue-client] claimTask malformed 200 response: missing/invalid leaseToken')
          return { ok: false, reason: 'Malformed response: missing leaseToken' }
        }
        return { ok: true, leaseToken: body.leaseToken }
      }

      // Safe to retry: a retryable status means the server responded and told
      // us the claim did not succeed (aelli's claim() only ever mutates state
      // and returns 200 together — see src/task-queue.js in raelli/aelli).
      if (RETRY_POLICY.isRetryableStatus(status) && attempt < RETRY_POLICY.maxAttempts) {
        await _sleep(RETRY_POLICY.calculateBackoffMs(attempt))
        continue
      }

      return { ok: false, reason: body?.error || `HTTP ${status}` }
    }
    catch (err) {
      // Do NOT retry here, unlike postResult. A network/timeout error means we
      // don't know whether the server already committed the claim before the
      // response was lost. aelli's claim() is a one-shot pending->claimed
      // transition with no idempotency key: retrying would only ever hit our
      // own already-claimed lease as a 409 (wasted round trip, never a fix),
      // while this daemon actually holds a lease it would otherwise abandon.
      // Fail fast instead; the caller treats any claim failure as "someone
      // else has it" and moves on, so a spurious retry buys nothing here.
      logger.error(`[task-queue-client] claimTask failed: ${err?.message || String(err)}`)
      return { ok: false, reason: err?.message || 'Unknown error' }
    }
  }
}

/**
 * Posts task result with retry for transient failures.
 * Returns true if accepted or considered terminal-success (409 late result),
 * otherwise false.
 */
async function postResult(taskId, leaseToken, result) {
  if (!taskId) {
    logger.error('[task-queue-client] postResult validation failed: taskId is required')
    return false
  }
  if (!leaseToken) {
    logger.error('[task-queue-client] postResult validation failed: leaseToken is required')
    return false
  }
  if (!result || typeof result !== 'object' || Array.isArray(result)) {
    logger.error('[task-queue-client] postResult validation failed: result must be an object')
    return false
  }

  const path = `/a2a/task-queue/${encodeURIComponent(taskId)}/result`
  const payload = { ...result, leaseToken }

  for (let attempt = 1; attempt <= RETRY_POLICY.maxAttempts; attempt++) {
    try {
      const { status, body } = await _post(path, payload)

      if (status === 200 || status === 409)
        return true // 409 = lease expired or already completed; safe to treat as terminal

      if (RETRY_POLICY.isRetryableStatus(status) && attempt < RETRY_POLICY.maxAttempts) {
        await _sleep(RETRY_POLICY.calculateBackoffMs(attempt))
        continue
      }

      const afterRetries = attempt > 1 ? ' after retries' : ''
      logger.error(
        `[task-queue-client] postResult failed${afterRetries}: HTTP ${status}${body?.error ? ` - ${body.error}` : ''}`,
      )
      return false
    }
    catch (err) {
      if (attempt < RETRY_POLICY.maxAttempts) {
        await _sleep(RETRY_POLICY.calculateBackoffMs(attempt))
        continue
      }

      logger.error(`[task-queue-client] postResult failed${attempt > 1 ? ' after retries' : ''}: ${err?.message || String(err)}`)
      return false
    }
  }
}

module.exports = { claimTask, postResult }
