// @vitest-environment node
// Filesystem-only assertions about the repo layout — happy-dom would serve
// import.meta.url as an http: URL, which fileURLToPath cannot resolve.
import { describe, it, expect } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = fileURLToPath(new URL('../..', import.meta.url))

describe('Plugin structure', () => {
    it('plugin.json is valid JSON', () => {
        const raw = fs.readFileSync(path.join(ROOT, 'plugin.json'), 'utf8')
        const json = JSON.parse(raw)
        expect(json).toBeDefined()
    })

    it('plugin.json has required fields', () => {
        const json = JSON.parse(fs.readFileSync(path.join(ROOT, 'plugin.json'), 'utf8'))
        expect(json.id).toBe('Vigil')
        expect(json.name).toBe('Vigil')
        expect(json.sbcRequired).toBe(true)
        expect(json.sbcExecutable).toBe('vigil-daemon.py')
        expect(json.sbcPermissions).toContain('registerHttpEndpoints')
        expect(json.sbcPermissions).toContain('objectModelReadWrite')
    })

    it('plugin.json has initial data', () => {
        const json = JSON.parse(fs.readFileSync(path.join(ROOT, 'plugin.json'), 'utf8'))
        expect(json.data).toBeDefined()
        expect(json.data.status).toBe('idle')
    })

    it('dsf/ contains all Python backend files', () => {
        const dsfDir = path.join(ROOT, 'dsf')
        const expected = [
            'vigil-daemon.py',
            'vigil_tracker.py',
            'vigil_persistence.py',
            'vigil_time.py',
            'vigil_api.py',
        ]
        for (const file of expected) {
            expect(fs.existsSync(path.join(dsfDir, file))).toBe(true)
        }
    })

    it('src/ carries the builder entry point and the shared core', () => {
        // Both DWC builders always compile src/index.js
        expect(fs.existsSync(path.join(ROOT, 'src/index.js'))).toBe(true)
        for (const file of ['host.js', 'backend.js', 'api.js', 'format.js']) {
            expect(fs.existsSync(path.join(ROOT, 'src/core', file))).toBe(true)
        }
    })

    it('src/ui36/ carries the complete DWC 3.6 shell', () => {
        for (const file of ['index.js', 'host.js', 'VigilDashboard.vue']) {
            expect(fs.existsSync(path.join(ROOT, 'src/ui36', file))).toBe(true)
        }
        expect(fs.readdirSync(path.join(ROOT, 'src/ui36/components')).length).toBeGreaterThan(0)
    })

    it('keeps the Jest-only DWC stubs out of src/', () => {
        // The DWC 3.7 builder is pointed straight at the repo and compiles all of
        // src/; a stray @/routes or @/store stub there would shadow DWC's own.
        for (const stub of ['routes.js', 'store.js', '__mocks__']) {
            expect(fs.existsSync(path.join(ROOT, 'src', stub))).toBe(false)
        }
        for (const stub of ['routes.js', 'store.js']) {
            expect(fs.existsSync(path.join(ROOT, 'tests/ui36/dwc-stubs', stub))).toBe(true)
        }
    })

    it('has no framework-specific import in src/core/', () => {
        // core/ is shipped to both generations verbatim, so it must not reach for
        // a store, a Vue runtime or a DWC module — that is the host adapter's job.
        const dir = path.join(ROOT, 'src/core')
        for (const file of fs.readdirSync(dir)) {
            const source = fs.readFileSync(path.join(dir, file), 'utf8')
            expect(source).not.toMatch(/from ['"](@\/|vue|vuex|vuetify|pinia)/)
        }
    })

    it('vigil-daemon.py has shebang line', () => {
        const content = fs.readFileSync(path.join(ROOT, 'dsf/vigil-daemon.py'), 'utf8')
        expect(content.startsWith('#!/usr/bin/env python3')).toBe(true)
    })
})
