import { describe, it, expect, beforeEach, vi } from 'vitest'
import {
    API_BASE, apiBlob, apiGet, apiPost, connectorSessionKey, downloadBlob, waitForBackend
} from '../../src/core/api'

function respond(overrides) {
    return { ok: true, json: () => Promise.resolve({}), blob: () => Promise.resolve('blob'), ...overrides }
}

// Only sessionKey() matters to this module
function hostWithKey(key) {
    return { sessionKey: () => key }
}

describe('daemon API', () => {
    const host = hostWithKey('0123abcd')

    beforeEach(() => {
        global.fetch = vi.fn().mockResolvedValue(respond())
    })

    it('addresses the endpoints DSF serves for this plugin', async () => {
        expect(API_BASE).toBe('/machine/Vigil')
        await apiGet(host, 'history?days=30')
        expect(global.fetch.mock.calls[0][0]).toBe('/machine/Vigil/history?days=30')
    })

    it('posts JSON bodies', async () => {
        await apiPost(host, 'service/event', { component: 'nozzle' })
        const [url, init] = global.fetch.mock.calls[0]
        expect(url).toBe('/machine/Vigil/service/event')
        expect(init.method).toBe('POST')
        expect(init.headers['Content-Type']).toBe('application/json')
        expect(JSON.parse(init.body)).toEqual({ component: 'nozzle' })
    })

    describe('session key', () => {
        // DSF forwards anonymous requests to plugin endpoints too; the daemon answers
        // 401 unless X-Session-Key names a live session, so every call must carry it.
        it('is sent with every kind of request', async () => {
            await apiGet(host, 'status')
            await apiPost(host, 'service/reset', {})
            await apiBlob(host, 'export?format=csv')
            await waitForBackend(host, 1, 1)
            expect(global.fetch).toHaveBeenCalledTimes(4)
            for (const [, init] of global.fetch.mock.calls) {
                expect(init.headers['X-Session-Key']).toBe('0123abcd')
            }
        })

        it('is read from the host on every call, so a reconnect is picked up', async () => {
            let key = 'first'
            const rotating = { sessionKey: () => key }
            await apiGet(rotating, 'status')
            key = 'second'
            await apiGet(rotating, 'status')
            expect(global.fetch.mock.calls.map(([, init]) => init.headers['X-Session-Key']))
                .toEqual(['first', 'second'])
        })

        it('is left out when the host has none', async () => {
            await apiGet(hostWithKey(null), 'status')
            await apiPost(hostWithKey(null), 'service/event', {})
            expect(global.fetch.mock.calls[0][1].headers).toEqual({})
            expect(global.fetch.mock.calls[1][1].headers).toEqual({ 'Content-Type': 'application/json' })
        })

        it('reports the daemon refusing a request without one', async () => {
            global.fetch.mockResolvedValue(respond({
                ok: false, status: 401, statusText: 'Unauthorized',
                json: () => Promise.resolve({ error: 'Not logged in: X-Session-Key missing or expired' })
            }))
            await expect(apiGet(hostWithKey(null), 'status')).rejects.toThrow('X-Session-Key')
        })
    })

    it('reports the daemon error message from the body', async () => {
        global.fetch.mockResolvedValue(respond({
            ok: false, statusText: 'Bad Request', json: () => Promise.resolve({ error: 'scope required' })
        }))
        await expect(apiGet(host, 'status')).rejects.toThrow('scope required')
    })

    it('falls back to the status text when there is no body', async () => {
        // DSF answers 404 without a body while the daemon is not running
        global.fetch.mockResolvedValue(respond({
            ok: false, statusText: 'Not Found', json: () => Promise.reject(new Error('no body'))
        }))
        await expect(apiPost(host, 'service/reset')).rejects.toThrow('Not Found')
        await expect(apiBlob(host, 'export?format=csv')).rejects.toThrow('Not Found')
    })

    it('returns the raw blob for file endpoints', async () => {
        await expect(apiBlob(host, 'export?format=csv')).resolves.toBe('blob')
    })

    describe('waitForBackend', () => {
        it('returns true as soon as /status answers', async () => {
            await expect(waitForBackend(host, 3, 1)).resolves.toBe(true)
            expect(global.fetch).toHaveBeenCalledTimes(1)
        })

        it('retries and gives up when the endpoints stay down', async () => {
            global.fetch.mockResolvedValue(respond({ ok: false, statusText: 'Not Found' }))
            await expect(waitForBackend(host, 3, 1)).resolves.toBe(false)
            expect(global.fetch).toHaveBeenCalledTimes(3)
        })
    })

    describe('connectorSessionKey', () => {
        it('reads the key a RestConnector logged in with', () => {
            expect(connectorSessionKey({ sessionKey: '0123abcd' })).toBe('0123abcd')
        })

        it('is null without a connector, for a PollConnector and before login', () => {
            expect(connectorSessionKey(null)).toBeNull()
            expect(connectorSessionKey(undefined)).toBeNull()
            expect(connectorSessionKey({ hostname: 'duet' })).toBeNull()
            expect(connectorSessionKey({ sessionKey: null })).toBeNull()
            expect(connectorSessionKey({ sessionKey: '' })).toBeNull()
        })
    })

    it('hands a blob to the browser as a download', () => {
        const click = vi.fn()
        global.URL.createObjectURL = vi.fn(() => 'blob:vigil')
        global.URL.revokeObjectURL = vi.fn()
        vi.spyOn(document, 'createElement').mockReturnValue({ click, set href(v) { this._h = v } })

        downloadBlob(new Blob(['x']), 'vigil_export.csv')

        expect(global.URL.createObjectURL).toHaveBeenCalled()
        expect(click).toHaveBeenCalled()
        expect(global.URL.revokeObjectURL).toHaveBeenCalledWith('blob:vigil')
        document.createElement.mockRestore()
    })
})
