/**
 * The two UI shells are different Vue majors, so they need different rulesets.
 *
 * eslint-plugin-vue's presets cannot simply be layered — an `overrides` entry adds to
 * the root `extends` rather than replacing it, so a Vue 3 preset at the root would keep
 * flagging correct Vue 2 code in src/ui36/ (`beforeDestroy`, the old slot syntax, …).
 * Hence: no Vue preset at the root, one override per shell.
 */
const RULES = {
    'no-console': 'warn',
    'no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
    'vue/html-indent': ['error', 2],
    'vue/max-attributes-per-line': 'off',
    'vue/singleline-html-element-content-newline': 'off',
    'vue/multi-word-component-names': 'off'
};

module.exports = {
    root: true,
    env: {
        browser: true,
        es2020: true
    },
    extends: ['eslint:recommended'],
    parserOptions: {
        ecmaVersion: 2020,
        sourceType: 'module'
    },
    rules: {
        'no-console': 'warn',
        'no-unused-vars': ['error', { argsIgnorePattern: '^_' }]
    },
    overrides: [
        {
            // DWC 3.6 shell: Vue 2.7 + Vuetify 2. `plugin:vue/recommended` is
            // eslint-plugin-vue's Vue 2 ruleset.
            files: ['src/ui36/**/*.{js,vue}'],
            extends: ['plugin:vue/recommended'],
            rules: RULES
        },
        {
            // DWC 3.7 shell and the shared core: Vue 3.
            files: ['src/ui37/**/*.{js,vue}', 'src/core/**/*.js', 'src/index.js'],
            extends: ['plugin:vue/vue3-recommended'],
            rules: RULES
        }
    ],
    globals: {
        fetch: 'readonly'
    }
};
