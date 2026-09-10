import { describe, it, expect, jest, beforeEach } from '@jest/globals'

// The 3.6 adapter reads DWC's Vuex store as a module singleton, so the store has
// to be replaced at module level rather than injected.
const mockStore = {
    state: {},
    dispatch: jest.fn().mockResolvedValue(undefined),
}
jest.mock('@/store', () => ({ __esModule: true, default: mockStore }))

const { createHost } = require('../../src/ui36/host')

describe('DWC 3.6 host adapter', () => {
    beforeEach(() => {
        mockStore.state = {}
        mockStore.dispatch.mockClear()
    })

    describe('pluginEntry', () => {
        it('is undefined while there is no machine module', () => {
            expect(createHost().pluginEntry()).toBeUndefined()
        })

        it('is undefined while the machine module has no object model', () => {
            mockStore.state = { machine: {} }
            expect(createHost().pluginEntry()).toBeUndefined()
        })

        it('is null while the object model carries no Vigil entry', () => {
            mockStore.state = { machine: { model: { plugins: new Map() } } }
            expect(createHost().pluginEntry()).toBeNull()
        })

        it('reads the entry out of the plugins Map', () => {
            const entry = { pid: 4711 }
            mockStore.state = { machine: { model: { plugins: new Map([['Vigil', entry]]) } } }
            expect(createHost().pluginEntry()).toBe(entry)
        })

        it('reads through the store on every call', () => {
            mockStore.state = { machine: { model: { plugins: new Map([['Vigil', { pid: -1 }]]) } } }
            const host = createHost()
            expect(host.pluginEntry().pid).toBe(-1)

            // DSF reports a new PID: a cached entry would keep reporting -1 and the
            // dashboard's recovery banner would never go away.
            mockStore.state.machine.model.plugins.set('Vigil', { pid: 4711 })
            expect(host.pluginEntry().pid).toBe(4711)
        })
    })

    describe('startBackend', () => {
        it('dispatches machine/startSbcPlugin with the plugin id', async () => {
            await createHost().startBackend()
            expect(mockStore.dispatch).toHaveBeenCalledWith('machine/startSbcPlugin', 'Vigil')
        })

        it('resolves even when dispatch returns a non-promise', async () => {
            mockStore.dispatch.mockReturnValueOnce(undefined)
            await expect(createHost().startBackend()).resolves.toBeUndefined()
        })
    })
})
