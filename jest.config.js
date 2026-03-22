module.exports = {
    testEnvironment: 'jsdom',
    moduleFileExtensions: ['js', 'vue', 'json'],
    transform: {
        '^.+\\.vue$': '@vue/vue2-jest',
        '^.+\\.js$': 'babel-jest'
    },
    testMatch: ['**/tests/frontend/**/*.test.js'],
    moduleNameMapper: {
        '^@/(.*)$': '<rootDir>/src/$1'
    },
    setupFiles: ['./tests/frontend/setup.js'],
    collectCoverageFrom: [
        'src/**/*.{js,vue}',
        '!src/**/index.js'
    ],
    coverageDirectory: 'coverage',
    coverageReporters: ['text', 'text-summary']
};
