const { httpJson } = require('./a2a-transport')
const config = require('./config')
const logger = require('./logger')

function _post(path, body) {
  return httpJson('POST', config.aelliBase() + path, body, {
    headers: config.queueAuthHeaders(),
    timeoutMs: 15_000,
  })
}

async function claimTask(taskId) {
  const { status, body } = await _post(`/a2a/task-queue/${taskId}/claim`, {})
  if (status === 200)
    return { ok: true, leaseToken: body.leaseToken }
  return { ok: false, reason: body.error || `HTTP ${status}` }
}

async function postResult(taskId, leaseToken, result) {
  let retries = 3
  while (retries-- > 0) {
    try {
      const { status } = await _post(`/a2a/task-queue/${taskId}/result`, { leaseToken, ...result })
      if (status === 200 || status === 409)
        return // 409 = late (lease expired or already done), discard
      if (status >= 500 && retries > 0)
        continue // retry on server error
      if (status >= 500)
        logger.error(`[daemon] postResult failed after retries: HTTP ${status}`)
      else
        logger.error(`[daemon] postResult unexpected ${status} — discarding`)
      return
    }
    catch (err) {
      if (retries === 0)
        logger.error(`[daemon] postResult failed after retries: ${err.message}`)
    }
  }
}

module.exports = { claimTask, postResult }
