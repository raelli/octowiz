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
    logger.error('[daemon] claimTask validation failed: taskId is required')
    return { ok: false, reason: 'taskId is required' }
  }

  try {
    const { status, body } = await _post(`/a2a/task-queue/${encodeURIComponent(taskId)}/claim`, {})

    if (status === 200) {
      if (!body || typeof body.leaseToken !== 'string' || body.leaseToken.length === 0) {
        logger.error('[daemon] claimTask malformed 200 response: missing/invalid leaseToken')
        return { ok: false, reason: 'Malformed response: missing leaseToken' }
      }

      return { ok: true, leaseToken: body.leaseToken }
    }

    return { ok: false, reason: body?.error || `HTTP ${status}` }
  }
  catch (err) {
    logger.error(`[daemon] claimTask failed: ${err?.message || String(err)}`)
    return { ok: false, reason: err?.message || 'Unknown error' }
  }
}

/**
 * Posts task result with retry for transient failures.
 * Returns true if accepted or considered terminal-success (409 late result),
 * otherwise false.
 */
async function postResult(taskId, leaseToken, result) {
  if (!taskId) {
    logger.error('[daemon] postResult validation failed: taskId is required')
    return false
  }
  if (!leaseToken) {
    logger.error('[daemon] postResult validation failed: leaseToken is required')
    return false
  }
  if (!result || typeof result !== 'object' || Array.isArray(result)) {
    logger.error('[daemon] postResult validation failed: result must be an object')
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

      const afterRetries = RETRY_POLICY.isRetryableStatus(status) ? ' after retries' : ''
      logger.error(
        `[daemon] postResult failed${afterRetries}: HTTP ${status}${body?.error ? ` - ${body.error}` : ''}`,
      )
      return false
    }
    catch (err) {
      if (attempt < RETRY_POLICY.maxAttempts) {
        await _sleep(RETRY_POLICY.calculateBackoffMs(attempt))
        continue
      }

      logger.error(`[daemon] postResult failed after retries: ${err?.message || String(err)}`)
      return false
    }
  }

  return false
}

module.exports = { claimTask, postResult }
