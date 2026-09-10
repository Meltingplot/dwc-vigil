import { describe, it, expect, beforeEach, vi } from 'vitest'
import { API_BASE, apiBlob, apiGet, apiPost, downloadBlob, waitForBackend } from '../../src/core/api'

function respond(overrides) {
    return { ok: true, json: () => Promise.resolve({}), blob: () => Promise.resolve('blob'), ...overrides }
}

describe('daemon API', () => {
    beforeEach(() => {
        global.fetch = vi.fn().mockResolvedValue(respond())
    })

    it('addresses the endpoints DSF serves for this plugin', async () => {
        expect(API_BASE).toBe('/machine/Vigil')
        await apiGet('history?days=30')
        expect(global.fetch).toHaveBeenCalledWith('/machine/Vigil/history?days=30')
    })

    it('posts JSON bodies', async () => {
        await apiPost('service/event', { component: 'nozzle' })
        const [url, init] = global.fetch.mock.calls[0]
        expect(url).toBe('/machine/Vigil/service/event')
        expect(init.method).toBe('POST')
        expect(init.headers['Content-Type']).toBe('application/json')
        expect(JSON.parse(init.body)).toEqual({ component: 'nozzle' })
    })

    it('reports the daemon error message from the body', async () => {
        global.fetch.mockResolvedValue(respond({
            ok: false, statusText: 'Bad Request', json: () => Promise.resolve({ error: 'scope required' })
        }))
        await expect(apiGet('status')).rejects.toThrow('scope required')
    })

    it('falls back to the status text when there is no body', async () => {
        // DSF answers 404 without a body while the daemon is not running
        global.fetch.mockResolvedValue(respond({
            ok: false, statusText: 'Not Found', json: () => Promise.reject(new Error('no body'))
        }))
        await expect(apiPost('service/reset')).rejects.toThrow('Not Found')
        await expect(apiBlob('export?format=csv')).rejects.toThrow('Not Found')
    })

    it('returns the raw blob for file endpoints', async () => {
        await expect(apiBlob('export?format=csv')).resolves.toBe('blob')
    })

    describe('waitForBackend', () => {
        it('returns true as soon as /status answers', async () => {
            await expect(waitForBackend(3, 1)).resolves.toBe(true)
            expect(global.fetch).toHaveBeenCalledTimes(1)
        })

        it('retries and gives up when the endpoints stay down', async () => {
            global.fetch.mockResolvedValue(respond({ ok: false, statusText: 'Not Found' }))
            await expect(waitForBackend(3, 1)).resolves.toBe(false)
            expect(global.fetch).toHaveBeenCalledTimes(3)
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
