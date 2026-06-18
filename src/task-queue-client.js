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
  isRetryableStatus: (status) => status >= 500,
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

async function claimTask(taskId) {
  const { status, body } = await _post(`/a2a/task-queue/${taskId}/claim`, {})

  if (status === 200) {
    if (!body || !body.leaseToken)
      return { ok: false, reason: 'Malformed response: missing leaseToken' }

    return { ok: true, leaseToken: body.leaseToken }
  }

  return { ok: false, reason: (body && body.error) || `HTTP ${status}` }
}

async function postResult(taskId, leaseToken, result) {
  for (let attempt = 1; attempt <= RETRY_POLICY.maxAttempts; attempt++) {
    try {
      const { status, body } = await _post(`/a2a/task-queue/${taskId}/result`, {
        leaseToken,
        ...result,
      })

      if (status === 200 || status === 409)
        return true // 409 = late (lease expired or already done), discard

      if (RETRY_POLICY.isRetryableStatus(status) && attempt < RETRY_POLICY.maxAttempts) {
        await _sleep(RETRY_POLICY.calculateBackoffMs(attempt))
        continue
      }

      logger.error(
        `[daemon] postResult failed: HTTP ${status}${body && body.error ? ` - ${body.error}` : ''}`
      )
      return false
    }
    catch (err) {
      if (attempt < RETRY_POLICY.maxAttempts) {
        await _sleep(RETRY_POLICY.calculateBackoffMs(attempt))
        continue
      }

      logger.error(`[daemon] postResult failed after retries: ${err.message}`)
      return false
    }
  }

  return false
}

module.exports = { claimTask, postResult }
