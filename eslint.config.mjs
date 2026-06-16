import antfu from '@antfu/eslint-config'

const jestGlobals = {
  describe: 'readonly',
  it: 'readonly',
  test: 'readonly',
  expect: 'readonly',
  beforeEach: 'readonly',
  afterEach: 'readonly',
  beforeAll: 'readonly',
  afterAll: 'readonly',
  jest: 'readonly',
}

export default antfu({
  ignores: ['node_modules', 'dist', 'docs', 'skills', 'assets', '**/*.toml', '**/*.yml', '**/*.yaml'],
  rules: {
    // Node.js CJS project — process/Buffer/etc. are always globals
    'node/prefer-global/process': 'off',
    'node/prefer-global/buffer': 'off',
    // Single-line guard clauses are idiomatic in this codebase
    'style/max-statements-per-line': 'off',
  },
}).append({
  files: ['tests/**/*.js', '**/*.test.js'],
  languageOptions: {
    globals: jestGlobals,
  },
})
