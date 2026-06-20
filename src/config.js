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

const DEFAULTS = {
  AELLI_API_BASE: 'http://localhost:3001/api',
  AELLI_A2A_BASE: 'http://localhost:3456',
  AELLI_DEV_ADVISOR_URL: 'http://localhost:3456/a2a/dev-advisor',
  CACHE_SUBDIR: '.cache',
  CACHE_DIRNAME: 'aelli-cc',
  LOG_FILENAME: 'aelli-cc.log',
  A2A_PORT: 8765,
  DISPATCH_TIMEOUT_SEC: 600,
  HTTP_TIMEOUT_BUFFER_MS: 30_000,
  MIN_DISPATCH_TIMEOUT_SEC: 1,
}

function env(name) {
  const v = process.env[name]
  return typeof v === 'string' ? v.trim() : ''
}

// Expects clean base inputs (no query/hash fragments).
function trimTrailingSlash(url) {
  return url.replace(/\/+$/, '')
}

function joinUrlPath(base, segment) {
  return `${trimTrailingSlash(base)}/${String(segment).replace(/^\/+/, '')}`
}

function isValidHttpUrl(value) {
  try {
    const u = new URL(value)
    return u.protocol === 'http:' || u.protocol === 'https:'
  }
  catch {
    return false
  }
}

// ---------------------------------------------------------------- AELLI ----

function apiBase() {
  return trimTrailingSlash(
    env('AELLI_BASE_URL')
    || env('AELLI_API_BASE')
    || DEFAULTS.AELLI_API_BASE,
  )
}

function aelliBase() {
  return trimTrailingSlash(env('AELLI_BASE_URL') || DEFAULTS.AELLI_A2A_BASE)
}

function queueUrl() {
  return joinUrlPath(aelliBase(), '/a2a/task-queue')
}

function authToken() {
  return env('AELLI_AUTH_TOKEN')
}

// Secret for AELLI-inbound calls (task queue claim/result, SSE subscribe).
// Precedence is intentional: AUTH_TOKEN is canonical and used first;
// INBOUND_SECRET is a compatibility fallback for direct-secret setups.
function aelliSecret() {
  return authToken() || env('AELLI_INBOUND_SECRET')
}

function litellmBase() {
  return trimTrailingSlash(env('AELLI_LITELLM_BASE'))
}

// Dev-advisor delivery route: LiteLLM gateway when configured, direct otherwise.
function devAdvisorUrl() {
  const base = litellmBase()
  if (base)
    return joinUrlPath(base, '/a2a/aelli-dev-advisor/message/send')
  return trimTrailingSlash(env('AELLI_DEV_ADVISOR_URL') || DEFAULTS.AELLI_DEV_ADVISOR_URL)
}

// Returns optional string: explicit URL, gateway-derived URL, or undefined when disabled.
function routerUrl() {
  const explicit = env('AELLI_ROUTER_URL')
  if (explicit)
    return trimTrailingSlash(explicit)
  const base = litellmBase()
  return base ? joinUrlPath(base, '/a2a/aelli-router/message/send') : undefined
}

// -------------------------------------------------------------- storage ----

function cacheDir() {
  const explicit = env('AELLI_CACHE_DIR')
  if (explicit)
    return explicit

  const home = os.homedir() || os.tmpdir()
  return path.join(home, DEFAULTS.CACHE_SUBDIR, DEFAULTS.CACHE_DIRNAME)
}

function logFile() {
  return path.join(cacheDir(), DEFAULTS.LOG_FILENAME)
}

// ------------------------------------------------- Python A2A server -------

function a2aPort() {
  const parsed = Number.parseInt(env('OCTOWIZ_A2A_PORT') || String(DEFAULTS.A2A_PORT), 10)
  // valid user-space TCP range; fallback on invalid or out-of-range input
  return Number.isInteger(parsed) && parsed > 0 && parsed <= 65535 ? parsed : DEFAULTS.A2A_PORT
}

function a2aServerUrl() {
  const explicit = env('OCTOWIZ_A2A_URL')
  if (explicit)
    return trimTrailingSlash(explicit)
  return `http://localhost:${a2aPort()}`
}

function octowizSecret() {
  return env('OCTOWIZ_INBOUND_SECRET')
}

// OCTOWIZ_DISPATCH_TIMEOUT is in *seconds* (matching Python's dispatch.py).
// The HTTP timeout must exceed the Python ceiling so a POST is never aborted
// before Python finishes; add a 30 s buffer.
function a2aTimeoutMs() {
  const parsed = Number.parseInt(
    env('OCTOWIZ_DISPATCH_TIMEOUT') || String(DEFAULTS.DISPATCH_TIMEOUT_SEC),
    10,
  )
  const dispatchTimeoutSec = Number.isNaN(parsed)
    ? DEFAULTS.DISPATCH_TIMEOUT_SEC
    : Math.max(DEFAULTS.MIN_DISPATCH_TIMEOUT_SEC, parsed)

  return dispatchTimeoutSec * 1000 + DEFAULTS.HTTP_TIMEOUT_BUFFER_MS
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

// The task queue (claim/result/subscribe) uses Bearer when the queue host
// is the LiteLLM gateway (AELLI_BASE_URL === AELLI_LITELLM_BASE), and
// x-aelli-secret when targeting direct AELLI.
function queueAuthHeaders() {
  const secret = aelliSecret()
  if (!secret)
    return {}
  const gateway = litellmBase()
  return gateway && aelliBase() === gateway
    ? { Authorization: `Bearer ${secret}` }
    : { 'x-aelli-secret': secret }
}

// The Python A2A server authenticates via x-octowiz-secret when set.
function a2aServerAuthHeaders() {
  const secret = octowizSecret()
  return secret ? { 'x-octowiz-secret': secret } : {}
}

// ---------------------------------------------------------- diagnostics ----

function isLocalhost(urlStr) {
  try {
    const h = new URL(urlStr).hostname
    return h === 'localhost' || h === '127.0.0.1' || h === '::1'
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

  const inboundSecret = env('AELLI_INBOUND_SECRET')
  if (token && inboundSecret && token !== inboundSecret) {
    warnings.push(
      '[AELLI A2A] Both AELLI_AUTH_TOKEN and AELLI_INBOUND_SECRET are set and differ. '
      + 'aelliSecret() prefers AELLI_AUTH_TOKEN; verify this is intentional.',
    )
  }

  const explicitUrls = [
    ['AELLI_API_BASE', env('AELLI_API_BASE')],
    ['AELLI_BASE_URL', env('AELLI_BASE_URL')],
    ['AELLI_LITELLM_BASE', env('AELLI_LITELLM_BASE')],
    ['AELLI_DEV_ADVISOR_URL', env('AELLI_DEV_ADVISOR_URL')],
    ['AELLI_ROUTER_URL', env('AELLI_ROUTER_URL')],
    ['OCTOWIZ_A2A_URL', env('OCTOWIZ_A2A_URL')],
  ]

  for (const [name, value] of explicitUrls) {
    if (value && !isValidHttpUrl(value)) {
      warnings.push(
        `[AELLI A2A] ${name} is set but is not a valid absolute http(s) URL: "${value}".`,
      )
    }
  }

  if (token) {
    const router = routerUrl()
    const urlsToCheck = [
      ['AELLI_API_BASE', apiBase()],
      ...(gateway ? [['AELLI_LITELLM_BASE', gateway]] : []),
      ['AELLI_DEV_ADVISOR_URL', devAdvisorUrl()],
      ...(router ? [['AELLI_ROUTER_URL', router]] : []),
    ]
    for (const [name, url] of urlsToCheck) {
      if (!url.startsWith('https://') && !isLocalhost(url)) {
        warnings.push(
          `[AELLI A2A] AELLI_AUTH_TOKEN is set but ${name} uses plain HTTP on a non-localhost address. Use HTTPS to protect your token.`,
        )
      }
    }
  }

  const a2aSecret = octowizSecret()
  if (a2aSecret) {
    const a2aUrl = a2aServerUrl()
    if (!a2aUrl.startsWith('https://') && !isLocalhost(a2aUrl)) {
      warnings.push(
        '[AELLI A2A] OCTOWIZ_INBOUND_SECRET is set but OCTOWIZ_A2A_URL uses plain HTTP on a non-localhost address. Use HTTPS to protect your secret.',
      )
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
