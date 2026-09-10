/**
 * Jest for the DWC 3.6 shell.
 *
 * This project is nested under tests/ so it can own a Vue 2.7 node_modules of its own;
 * the repo root carries Vue 3 for the DWC 3.7 build and its vitest suite.
 *
 * The catch is that the files under test live OUTSIDE this directory, in
 * ../../src/ui36/. Node resolves a bare `vue` import by walking up from the importing
 * file, which from src/ui36/ reaches the repo root's Vue 3 first — so every framework
 * package is pinned to this project's own node_modules explicitly. A missing entry
 * shows up as a Vue 3 runtime failing to mount a Vue 2 component, which is a confusing
 * error a long way from its cause.
 */
const path = require('path');

const own = (pkg) => path.join(__dirname, 'node_modules', pkg);

module.exports = {
    rootDir: __dirname,
    testEnvironment: 'jsdom',
    moduleFileExtensions: ['js', 'vue', 'json'],
    transform: {
        '^.+\\.vue$': '@vue/vue2-jest',
        '^.+\\.js$': 'babel-jest'
    },
    testMatch: ['<rootDir>/**/*.test.js'],
    moduleDirectories: [own(''), 'node_modules'],
    moduleNameMapper: {
        // DWC provides these at runtime; the stubs make them resolvable here
        '^@/(.*)$': '<rootDir>/dwc-stubs/$1',
        // chart.js comes from the DWC 3.6 checkout in a real build
        '^chart\\.js$': '<rootDir>/__mocks__/chart.js',
        // Pin the framework to this project, not the Vue 3 root (see above)
        '^vue$': own('vue'),
        '^vue/(.*)$': path.join(own('vue'), '$1'),
        '^vuex$': own('vuex'),
        '^vuetify$': own('vuetify'),
        '^vuetify/(.*)$': path.join(own('vuetify'), '$1'),
        '^@vue/test-utils$': own('@vue/test-utils')
    },
    setupFiles: ['<rootDir>/setup.js'],
    collectCoverageFrom: [
        '<rootDir>/../../src/ui36/**/*.{js,vue}',
        '!<rootDir>/../../src/ui36/index.js'
    ],
    coverageDirectory: '<rootDir>/coverage',
    coverageReporters: ['text', 'text-summary']
};
