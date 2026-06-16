// CANONICAL CONFIG OWNER — the single place the Octowiz Bridge reads its
// environment. Every URL, secret, directory, and auth-header decision the
// plugin makes against AELLI, the task queue, or the Python A2A server is
// resolved here. No other module may read these variables directly.
//
// All functions read process.env at call time (not module load) so tests can
// set variables without juggling jest.resetModules().
//
// AELLI exposes two distinct services, both keyed off AELLI_BASE_URL:
//   - apiBase()   → the AELLI Node REST API   (local default :3001/api)
//   - aelliBase() → the AELLI A2A host        (local default :3456)
// When AELLI_BASE_URL is unset they intentionally point at different local
// ports; when it is set, both follow it.

const os = require('node:os')
const path = require('node:path')

// ---------------------------------------------------------------- AELLI ----

function apiBase() {
  return (
    process.env.AELLI_BASE_URL
    || process.env.AELLI_API_BASE
    || 'http://localhost:3001/api'
  )
}

function aelliBase() {
  return (process.env.AELLI_BASE_URL || 'http://localhost:3456').replace(/\/$/, '')
}

function queueUrl() {
  return `${aelliBase()}/a2a/task-queue`
}

function authToken() {
  return process.env.AELLI_AUTH_TOKEN || ''
}

// Secret for AELLI-inbound calls (task queue claim/result, SSE subscribe).
function aelliSecret() {
  return process.env.AELLI_AUTH_TOKEN || process.env.AELLI_INBOUND_SECRET || ''
}

function litellmBase() {
  return (process.env.AELLI_LITELLM_BASE || '').replace(/\/+$/, '')
}

// Dev-advisor delivery route: LiteLLM gateway when configured, direct otherwise.
function devAdvisorUrl() {
  const base = litellmBase()
  if (base)
    return `${base}/a2a/aelli-dev-advisor/message/send`
  return process.env.AELLI_DEV_ADVISOR_URL || 'http://localhost:3456/a2a/dev-advisor'
}

function routerUrl() {
  if (process.env.AELLI_ROUTER_URL)
    return process.env.AELLI_ROUTER_URL
  const base = litellmBase()
  return base ? `${base}/a2a/aelli-router/message/send` : null
}

// -------------------------------------------------------------- storage ----

function cacheDir() {
  return process.env.AELLI_CACHE_DIR || path.join(os.homedir(), '.cache', 'aelli-cc')
}

function logFile() {
  return path.join(cacheDir(), 'aelli-cc.log')
}

// ------------------------------------------------- Python A2A server -------

function a2aPort() {
  return Number.parseInt(process.env.OCTOWIZ_A2A_PORT || '8765', 10)
}

function a2aServerUrl() {
  if (process.env.OCTOWIZ_A2A_URL) {
    return process.env.OCTOWIZ_A2A_URL.replace(/\/$/, '')
  }
  return `http://localhost:${a2aPort()}`
}

function octowizSecret() {
  return process.env.OCTOWIZ_INBOUND_SECRET || ''
}

// OCTOWIZ_DISPATCH_TIMEOUT is in *seconds* (matching Python's dispatch.py).
// The HTTP timeout must exceed the Python ceiling so a POST is never aborted
// before Python finishes; add a 30 s buffer.
function a2aTimeoutMs() {
  const dispatchTimeoutSec = Number.parseInt(process.env.OCTOWIZ_DISPATCH_TIMEOUT || '300', 10)
  return dispatchTimeoutSec * 1000 + 30_000
}

// ------------------------------------------------------- auth headers ------

// Headers for AELLI-bound calls: Bearer through the LiteLLM gateway,
// x-aelli-secret when calling AELLI directly, nothing without a token.
function aelliAuthHeaders() {
  const token = authToken()
  if (!token)
    return {}
  return litellmBase()
    ? { Authorization: `Bearer ${token}` }
    : { 'x-aelli-secret': token }
}

// The task queue (claim/result/subscribe) always authenticates with
// x-aelli-secret, accepting AELLI_INBOUND_SECRET as a fallback.
function queueAuthHeaders() {
  return { 'x-aelli-secret': aelliSecret() }
}

// The Python A2A server authenticates via x-octowiz-secret.
function a2aServerAuthHeaders() {
  return { 'x-octowiz-secret': octowizSecret() }
}

// ---------------------------------------------------------- diagnostics ----

function isLocalhost(urlStr) {
  try {
    const h = new URL(urlStr).hostname
    return h === 'localhost' || h === '127.0.0.1' || h === '::1' || h === '[::1]'
  }
  catch {
    return false
  }
}

// Misconfiguration warnings, computed from the same facts production uses.
// Returns human-readable strings; callers decide where to log them.
function configWarnings() {
  const warnings = []
  const token = authToken()
  const gateway = litellmBase()

  if (gateway && !token) {
    warnings.push(
      '[AELLI A2A] AELLI_LITELLM_BASE is set but AELLI_AUTH_TOKEN is missing. '
      + 'All A2A calls through the LiteLLM gateway will get 401 Unauthorized. '
      + 'Set AELLI_AUTH_TOKEN to a valid LiteLLM API key.',
    )
  }

  if (token) {
    const urlsToCheck = [
      ['AELLI_API_BASE', apiBase()],
      ...(gateway ? [['AELLI_LITELLM_BASE', gateway]] : []),
      ['AELLI_DEV_ADVISOR_URL', devAdvisorUrl()],
    ]
    for (const [name, url] of urlsToCheck) {
      if (!url.startsWith('https://') && !isLocalhost(url)) {
        warnings.push(
          `[AELLI A2A] AELLI_AUTH_TOKEN is set but ${name} uses plain HTTP on a non-localhost address. Use HTTPS to protect your token.`,
        )
      }
    }
  }

  return warnings
}

module.exports = {
  apiBase,
  aelliBase,
  queueUrl,
  authToken,
  aelliSecret,
  litellmBase,
  devAdvisorUrl,
  routerUrl,
  cacheDir,
  logFile,
  a2aPort,
  a2aServerUrl,
  octowizSecret,
  a2aTimeoutMs,
  aelliAuthHeaders,
  queueAuthHeaders,
  a2aServerAuthHeaders,
  configWarnings,
}
