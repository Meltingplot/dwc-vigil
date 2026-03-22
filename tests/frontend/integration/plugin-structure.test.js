import { describe, it, expect } from '@jest/globals'
import fs from 'fs'
import path from 'path'

const ROOT = path.resolve(__dirname, '../../..')

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

    it('src/ contains frontend entry point', () => {
        expect(fs.existsSync(path.join(ROOT, 'src/index.js'))).toBe(true)
        expect(fs.existsSync(path.join(ROOT, 'src/VigilDashboard.vue'))).toBe(true)
    })

    it('vigil-daemon.py has shebang line', () => {
        const content = fs.readFileSync(path.join(ROOT, 'dsf/vigil-daemon.py'), 'utf8')
        expect(content.startsWith('#!/usr/bin/env python3')).toBe(true)
    })
})
