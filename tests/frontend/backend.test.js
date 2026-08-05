import { describe, it, expect, jest } from '@jest/globals'
import {
    PLUGIN_ID,
    getPluginEntry,
    isBackendRunning,
    startBackend,
    ensureBackendRunning
} from '../../src/backend'

function modelWithMap(plugin) {
    const plugins = new Map()
    if (plugin) {
        plugins.set(PLUGIN_ID, plugin)
    }
    return { plugins }
}

describe('backend helpers', () => {
    describe('getPluginEntry', () => {
        it('reads the plugin from a Map (DWC 3.6)', () => {
            const plugin = { id: PLUGIN_ID, pid: 1234 }
            expect(getPluginEntry(modelWithMap(plugin))).toBe(plugin)
        })

        it('reads the plugin from a plain object (test stores)', () => {
            const plugin = { id: PLUGIN_ID, pid: 1234 }
            expect(getPluginEntry({ plugins: { [PLUGIN_ID]: plugin } })).toBe(plugin)
        })

        it('returns null when the plugin is absent', () => {
            expect(getPluginEntry(modelWithMap(null))).toBeNull()
        })

        it('returns null when there is no model state at all', () => {
            expect(getPluginEntry(undefined)).toBeNull()
            expect(getPluginEntry({})).toBeNull()
        })
    })

    describe('isBackendRunning', () => {
        it('is true for a positive PID', () => {
            expect(isBackendRunning(modelWithMap({ pid: 4711 }))).toBe(true)
        })

        it('is false for pid -1 (stopped, e.g. right after an update)', () => {
            expect(isBackendRunning(modelWithMap({ pid: -1 }))).toBe(false)
        })

        it('is false for pid 0 (shutting down)', () => {
            expect(isBackendRunning(modelWithMap({ pid: 0 }))).toBe(false)
        })

        it('is null when the plugin entry is missing', () => {
            expect(isBackendRunning(modelWithMap(null))).toBeNull()
        })

        it('is null when the PID is not a number yet', () => {
            expect(isBackendRunning(modelWithMap({}))).toBeNull()
        })
    })

    describe('startBackend', () => {
        it('dispatches machine/startSbcPlugin with the plugin id', async () => {
            const store = { dispatch: jest.fn().mockResolvedValue(undefined) }
            await startBackend(store)
            expect(store.dispatch).toHaveBeenCalledWith('machine/startSbcPlugin', PLUGIN_ID)
        })

        it('resolves even when dispatch returns a non-promise', async () => {
            const store = { dispatch: jest.fn().mockReturnValue(undefined) }
            await expect(startBackend(store)).resolves.toBeUndefined()
        })
    })

    describe('ensureBackendRunning', () => {
        function makeStore(model, dispatch) {
            return {
                state: { machine: { model } },
                dispatch: dispatch || jest.fn().mockResolvedValue(undefined)
            }
        }

        it('starts the backend when the model reports it as stopped', async () => {
            const dispatch = jest.fn().mockResolvedValue(undefined)
            const store = makeStore(modelWithMap({ pid: -1 }), dispatch)
            await expect(ensureBackendRunning(store)).resolves.toBe(true)
            expect(dispatch).toHaveBeenCalledWith('machine/startSbcPlugin', PLUGIN_ID)
        })

        it('does nothing when the backend is already running', async () => {
            const dispatch = jest.fn()
            const store = makeStore(modelWithMap({ pid: 4711 }), dispatch)
            await expect(ensureBackendRunning(store)).resolves.toBe(false)
            expect(dispatch).not.toHaveBeenCalled()
        })

        it('bails out immediately without a machine module', async () => {
            const dispatch = jest.fn()
            await expect(
                ensureBackendRunning({ state: {}, dispatch })
            ).resolves.toBe(false)
            expect(dispatch).not.toHaveBeenCalled()
        })

        it('bails out immediately without a store', async () => {
            await expect(ensureBackendRunning(undefined)).resolves.toBe(false)
        })

        it('waits for the object model to report a PID', async () => {
            const model = modelWithMap(null)
            const dispatch = jest.fn().mockResolvedValue(undefined)
            const store = makeStore(model, dispatch)

            const promise = ensureBackendRunning(store, { interval: 1, maxAttempts: 20 })
            // Plugin entry shows up a little later, as it does on a fresh connection
            setTimeout(() => model.plugins.set(PLUGIN_ID, { pid: -1 }), 5)

            await expect(promise).resolves.toBe(true)
            expect(dispatch).toHaveBeenCalledWith('machine/startSbcPlugin', PLUGIN_ID)
        })

        it('gives up after maxAttempts when the PID never appears', async () => {
            const dispatch = jest.fn()
            const store = makeStore(modelWithMap(null), dispatch)
            await expect(
                ensureBackendRunning(store, { interval: 1, maxAttempts: 3 })
            ).resolves.toBe(false)
            expect(dispatch).not.toHaveBeenCalled()
        })

        it('resolves false when starting the backend fails', async () => {
            const warn = jest.spyOn(console, 'warn').mockImplementation(() => {})
            const dispatch = jest.fn().mockRejectedValue(new Error('denied'))
            const store = makeStore(modelWithMap({ pid: -1 }), dispatch)
            await expect(ensureBackendRunning(store)).resolves.toBe(false)
            expect(warn).toHaveBeenCalled()
            warn.mockRestore()
        })
    })
})
