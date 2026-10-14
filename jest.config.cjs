/** @type {import('jest').Config} */
module.exports = {
  testEnvironment: 'node',
  testMatch: ['<rootDir>/src/utils/__tests__/**/*.test.ts'],
  transform: {
    '^.+\\.tsx?$': [
      '@swc/jest',
      {
        jsc: {
          parser: { syntax: 'typescript' },
          target: 'es2022',
        },
        module: { type: 'commonjs' },
      },
    ],
  },
  collectCoverageFrom: ['src/utils/*.ts', '!src/utils/__tests__/**'],
  coverageReporters: ['text', 'text-summary'],
  coverageDirectory: '<rootDir>/coverage',
}
