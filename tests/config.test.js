const os = require('node:os')
const path = require('node:path')

const ENV_KEYS = [
  'AELLI_BASE_URL',
  'AELLI_API_BASE',
  'AELLI_AUTH_TOKEN',
  'AELLI_INBOUND_SECRET',
  'AELLI_LITELLM_BASE',
  'AELLI_DEV_ADVISOR_URL',
  'AELLI_ROUTER_URL',
  'AELLI_CACHE_DIR',
  'OCTOWIZ_A2A_URL',
  'OCTOWIZ_A2A_PORT',
  'OCTOWIZ_INBOUND_SECRET',
  'OCTOWIZ_DISPATCH_TIMEOUT',
]

describe('config', () => {
  let saved
  let config

  beforeEach(() => {
    saved = {}
    for (const k of ENV_KEYS) {
      saved[k] = process.env[k]
      delete process.env[k]
    }
    config = require('../src/config')
  })

  afterEach(() => {
    for (const k of ENV_KEYS) {
      if (saved[k] === undefined)
        delete process.env[k]
      else process.env[k] = saved[k]
    }
  })

  describe('apiBase', () => {
    it('defaults to the AELLI Node REST API', () => {
      expect(config.apiBase()).toBe('http://localhost:3001/api')
    })
    it('prefers AELLI_BASE_URL over AELLI_API_BASE', () => {
      process.env.AELLI_BASE_URL = 'https://aelli.example.com'
      process.env.AELLI_API_BASE = 'https://other.example.com'
      expect(config.apiBase()).toBe('https://aelli.example.com')
    })
    it('falls back to AELLI_API_BASE', () => {
      process.env.AELLI_API_BASE = 'https://other.example.com'
      expect(config.apiBase()).toBe('https://other.example.com')
    })
  })

  describe('aelliBase / queueUrl', () => {
    it('defaults to the local AELLI A2A host', () => {
      expect(config.aelliBase()).toBe('http://localhost:3456')
      expect(config.queueUrl()).toBe('http://localhost:3456/a2a/task-queue')
    })
    it('strips a trailing slash from AELLI_BASE_URL', () => {
      process.env.AELLI_BASE_URL = 'https://aelli.example.com/'
      expect(config.queueUrl()).toBe('https://aelli.example.com/a2a/task-queue')
    })
  })

  describe('secrets', () => {
    it('aelliSecret prefers AELLI_AUTH_TOKEN, falls back to AELLI_INBOUND_SECRET', () => {
      expect(config.aelliSecret()).toBe('')
      process.env.AELLI_INBOUND_SECRET = 'inbound'
      expect(config.aelliSecret()).toBe('inbound')
      process.env.AELLI_AUTH_TOKEN = 'token'
      expect(config.aelliSecret()).toBe('token')
    })
    it('octowizSecret reads OCTOWIZ_INBOUND_SECRET', () => {
      expect(config.octowizSecret()).toBe('')
      process.env.OCTOWIZ_INBOUND_SECRET = 's3cret'
      expect(config.octowizSecret()).toBe('s3cret')
    })
  })

  describe('dev-advisor / router resolution', () => {
    it('routes through the LiteLLM gateway when AELLI_LITELLM_BASE is set', () => {
      process.env.AELLI_LITELLM_BASE = 'https://llm.example.com/'
      expect(config.devAdvisorUrl()).toBe(
        'https://llm.example.com/a2a/aelli-dev-advisor/message/send',
      )
      expect(config.routerUrl()).toBe(
        'https://llm.example.com/a2a/aelli-router/message/send',
      )
    })
    it('falls back to the direct dev-advisor URL', () => {
      expect(config.devAdvisorUrl()).toBe('http://localhost:3456/a2a/dev-advisor')
      expect(config.routerUrl()).toBeNull()
    })
    it('honors explicit AELLI_DEV_ADVISOR_URL and AELLI_ROUTER_URL', () => {
      process.env.AELLI_DEV_ADVISOR_URL = 'http://localhost:9999/a2a/dev-advisor'
      process.env.AELLI_ROUTER_URL = 'http://localhost:9999/a2a/router'
      expect(config.devAdvisorUrl()).toBe('http://localhost:9999/a2a/dev-advisor')
      expect(config.routerUrl()).toBe('http://localhost:9999/a2a/router')
    })
  })

  describe('cacheDir / logFile', () => {
    it('defaults under the home directory', () => {
      expect(config.cacheDir()).toBe(path.join(os.homedir(), '.cache', 'aelli-cc'))
      expect(config.logFile()).toBe(
        path.join(os.homedir(), '.cache', 'aelli-cc', 'aelli-cc.log'),
      )
    })
    it('honors AELLI_CACHE_DIR', () => {
      process.env.AELLI_CACHE_DIR = '/tmp/custom-cache'
      expect(config.cacheDir()).toBe('/tmp/custom-cache')
    })
  })

  describe('python A2A server', () => {
    it('defaults to localhost on port 8765', () => {
      expect(config.a2aPort()).toBe(8765)
      expect(config.a2aServerUrl()).toBe('http://localhost:8765')
    })
    it('oCTOWIZ_A2A_URL wins over the port', () => {
      process.env.OCTOWIZ_A2A_URL = 'http://10.0.0.5:9000/'
      process.env.OCTOWIZ_A2A_PORT = '1234'
      expect(config.a2aServerUrl()).toBe('http://10.0.0.5:9000')
    })
    it('oCTOWIZ_A2A_PORT changes the local fallback', () => {
      process.env.OCTOWIZ_A2A_PORT = '1234'
      expect(config.a2aServerUrl()).toBe('http://localhost:1234')
    })
    it('a2aTimeoutMs derives from OCTOWIZ_DISPATCH_TIMEOUT seconds plus buffer', () => {
      expect(config.a2aTimeoutMs()).toBe(300 * 1000 + 30000)
      process.env.OCTOWIZ_DISPATCH_TIMEOUT = '60'
      expect(config.a2aTimeoutMs()).toBe(60 * 1000 + 30000)
    })
  })

  describe('auth headers', () => {
    it('aelliAuthHeaders is empty without a token', () => {
      expect(config.aelliAuthHeaders()).toEqual({})
    })
    it('uses Bearer when routing through the gateway', () => {
      process.env.AELLI_AUTH_TOKEN = 'tok'
      process.env.AELLI_LITELLM_BASE = 'https://llm.example.com'
      expect(config.aelliAuthHeaders()).toEqual({ Authorization: 'Bearer tok' })
    })
    it('uses x-aelli-secret for direct AELLI calls', () => {
      process.env.AELLI_AUTH_TOKEN = 'tok'
      expect(config.aelliAuthHeaders()).toEqual({ 'x-aelli-secret': 'tok' })
    })
    it('queueAuthHeaders always uses x-aelli-secret with the fallback chain', () => {
      process.env.AELLI_INBOUND_SECRET = 'inbound'
      expect(config.queueAuthHeaders()).toEqual({ 'x-aelli-secret': 'inbound' })
    })
    it('a2aServerAuthHeaders uses x-octowiz-secret', () => {
      process.env.OCTOWIZ_INBOUND_SECRET = 's'
      expect(config.a2aServerAuthHeaders()).toEqual({ 'x-octowiz-secret': 's' })
    })
  })

  describe('configWarnings', () => {
    it('is silent for a default local setup', () => {
      expect(config.configWarnings()).toEqual([])
    })
    it('warns when the gateway is set without a token', () => {
      process.env.AELLI_LITELLM_BASE = 'https://llm.example.com'
      const warnings = config.configWarnings()
      expect(warnings).toHaveLength(1)
      expect(warnings[0]).toMatch(/AELLI_AUTH_TOKEN is missing/)
    })
    it('warns when a token would travel over non-localhost plain HTTP', () => {
      process.env.AELLI_AUTH_TOKEN = 'tok'
      process.env.AELLI_BASE_URL = 'http://aelli.example.com'
      const warnings = config.configWarnings()
      expect(warnings.some(w => w.includes('plain HTTP'))).toBe(true)
    })
    it('does not warn for localhost plain HTTP', () => {
      process.env.AELLI_AUTH_TOKEN = 'tok'
      expect(config.configWarnings()).toEqual([])
    })
  })
})
