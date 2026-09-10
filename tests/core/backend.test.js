import { describe, it, expect, vi } from 'vitest'
import {
    PLUGIN_ID,
    getPluginEntry,
    isBackendRunning,
    startBackend,
    ensureBackendRunning
} from '../../src/core/backend'

function modelWithMap(plugin) {
    const plugins = new Map()
    if (plugin) {
        plugins.set(PLUGIN_ID, plugin)
    }
    return { plugins }
}

/** Minimal HostAdapter reading a mutable model, as the real adapters do. */
function fakeHost(model, startBackendImpl) {
    return {
        pluginEntry: () => getPluginEntry(model),
        startBackend: startBackendImpl || vi.fn().mockResolvedValue(undefined),
    }
}

describe('backend helpers', () => {
    describe('getPluginEntry', () => {
        it('reads the plugin from a Map (both DWC generations)', () => {
            const plugin = { id: PLUGIN_ID, pid: 1234 }
            expect(getPluginEntry(modelWithMap(plugin))).toBe(plugin)
        })

        it('reads the plugin from a plain object (test models)', () => {
            const plugin = { id: PLUGIN_ID, pid: 1234 }
            expect(getPluginEntry({ plugins: { [PLUGIN_ID]: plugin } })).toBe(plugin)
        })

        it('returns null when the model carries no entry for this plugin', () => {
            expect(getPluginEntry(modelWithMap(null))).toBeNull()
            expect(getPluginEntry({})).toBeNull()
        })

        it('returns undefined when there is no object model at all', () => {
            expect(getPluginEntry(undefined)).toBeUndefined()
            expect(getPluginEntry(null)).toBeUndefined()
        })
    })

    describe('isBackendRunning', () => {
        it('is true for a positive PID', () => {
            expect(isBackendRunning({ pid: 4711 })).toBe(true)
        })

        it('is false for pid -1 (stopped, e.g. right after an update)', () => {
            expect(isBackendRunning({ pid: -1 })).toBe(false)
        })

        it('is false for pid 0 (shutting down)', () => {
            expect(isBackendRunning({ pid: 0 })).toBe(false)
        })

        it('is null when the plugin entry is missing', () => {
            expect(isBackendRunning(null)).toBeNull()
            expect(isBackendRunning(undefined)).toBeNull()
        })

        it('is null when the PID is not a number yet', () => {
            expect(isBackendRunning({})).toBeNull()
        })
    })

    describe('startBackend', () => {
        it('delegates to the host adapter', async () => {
            const host = fakeHost(modelWithMap({ pid: -1 }))
            await startBackend(host)
            expect(host.startBackend).toHaveBeenCalled()
        })

        it('resolves even when the host returns a non-promise', async () => {
            const host = fakeHost(modelWithMap({ pid: -1 }), vi.fn().mockReturnValue(undefined))
            await expect(startBackend(host)).resolves.toBeUndefined()
        })
    })

    describe('ensureBackendRunning', () => {
        it('starts the backend when the model reports it as stopped', async () => {
            const host = fakeHost(modelWithMap({ pid: -1 }))
            await expect(ensureBackendRunning(host)).resolves.toBe(true)
            expect(host.startBackend).toHaveBeenCalled()
        })

        it('does nothing when the backend is already running', async () => {
            const host = fakeHost(modelWithMap({ pid: 4711 }))
            await expect(ensureBackendRunning(host)).resolves.toBe(false)
            expect(host.startBackend).not.toHaveBeenCalled()
        })

        it('bails out immediately when the host reports no object model', async () => {
            const host = fakeHost(undefined)
            await expect(ensureBackendRunning(host)).resolves.toBe(false)
            expect(host.startBackend).not.toHaveBeenCalled()
        })

        it('bails out immediately without a host', async () => {
            await expect(ensureBackendRunning(undefined)).resolves.toBe(false)
            await expect(ensureBackendRunning({})).resolves.toBe(false)
        })

        it('treats a throwing host read as "no object model"', async () => {
            const startBackendImpl = vi.fn()
            await expect(ensureBackendRunning({
                pluginEntry: () => { throw new Error('not connected') },
                startBackend: startBackendImpl,
            })).resolves.toBe(false)
            expect(startBackendImpl).not.toHaveBeenCalled()
        })

        it('waits for the object model to report a PID', async () => {
            const model = modelWithMap(null)
            const host = fakeHost(model)

            const promise = ensureBackendRunning(host, { interval: 1, maxAttempts: 20 })
            // Plugin entry shows up a little later, as it does on a fresh connection
            setTimeout(() => model.plugins.set(PLUGIN_ID, { pid: -1 }), 5)

            await expect(promise).resolves.toBe(true)
            expect(host.startBackend).toHaveBeenCalled()
        })

        it('gives up after maxAttempts when the PID never appears', async () => {
            const host = fakeHost(modelWithMap(null))
            await expect(
                ensureBackendRunning(host, { interval: 1, maxAttempts: 3 })
            ).resolves.toBe(false)
            expect(host.startBackend).not.toHaveBeenCalled()
        })

        it('resolves false when starting the backend fails', async () => {
            const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
            const host = fakeHost(modelWithMap({ pid: -1 }), vi.fn().mockRejectedValue(new Error('denied')))
            await expect(ensureBackendRunning(host)).resolves.toBe(false)
            expect(warn).toHaveBeenCalled()
            warn.mockRestore()
        })
    })
})
