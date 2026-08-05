import { describe, it, expect, beforeEach, afterEach, jest } from '@jest/globals'
import { shallowMount, createLocalVue } from '@vue/test-utils'
import Vuex from 'vuex'
import VigilDashboard from '../../src/VigilDashboard.vue'

const localVue = createLocalVue()
localVue.use(Vuex)

function createStore(options = {}) {
    const plugin = { data: options.pluginData || {} }
    if (options.pid !== undefined) {
        plugin.pid = options.pid
    }
    return new Vuex.Store({
        modules: {
            'machine/model': {
                namespaced: true,
                state: {
                    plugins: new Map([['Vigil', plugin]])
                }
            },
            machine: {
                namespaced: true,
                actions: {
                    startSbcPlugin: options.startSbcPlugin || jest.fn()
                }
            }
        }
    })
}

function mountDashboard(options = {}) {
    return shallowMount(VigilDashboard, {
        localVue,
        store: createStore(options),
        vuetify: createVuetify()
    })
}

function mockFetchSuccess(data) {
    global.fetch = jest.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(data)
    })
}

// Let the fetch chain started by mounted() finish before re-mocking fetch
function flushPromises() {
    return new Promise(resolve => setTimeout(resolve, 0))
}

function mockFetchError(status = 404, statusText = 'Not Found') {
    global.fetch = jest.fn().mockResolvedValue({
        ok: false,
        status,
        statusText,
        json: () => Promise.resolve({})
    })
}

describe('VigilDashboard backend recovery', () => {
    let wrapper

    beforeEach(() => {
        mockFetchSuccess({})
    })

    afterEach(() => {
        if (wrapper) {
            wrapper.destroy()
            wrapper = null
        }
        jest.restoreAllMocks()
    })

    describe('backendRunning', () => {
        it('is null while the object model reports no PID', () => {
            wrapper = mountDashboard()
            expect(wrapper.vm.backendRunning).toBeNull()
        })

        it('is true when the SBC process is running', () => {
            wrapper = mountDashboard({ pid: 4711 })
            expect(wrapper.vm.backendRunning).toBe(true)
        })

        it('is false after an update left the process stopped', () => {
            wrapper = mountDashboard({ pid: -1 })
            expect(wrapper.vm.backendRunning).toBe(false)
        })
    })

    describe('warning banner', () => {
        it('is shown when the backend is stopped', async () => {
            wrapper = mountDashboard({ pid: -1 })
            await wrapper.vm.$nextTick()
            expect(wrapper.text()).toContain('Backend is not running')
        })

        it('is hidden when the backend runs', async () => {
            wrapper = mountDashboard({ pid: 4711 })
            await wrapper.vm.$nextTick()
            expect(wrapper.text()).not.toContain('Backend is not running')
        })

        it('is hidden while the PID is unknown', async () => {
            wrapper = mountDashboard()
            await wrapper.vm.$nextTick()
            expect(wrapper.text()).not.toContain('Backend is not running')
        })

        it('replaces the loading spinner while the backend is down', async () => {
            wrapper = mountDashboard({ pid: -1 })
            await wrapper.vm.$nextTick()
            expect(wrapper.text()).not.toContain('Loading Vigil data')
        })
    })

    describe('startBackend', () => {
        it('dispatches machine/startSbcPlugin and reports success', async () => {
            const startSbcPlugin = jest.fn()
            wrapper = mountDashboard({ pid: -1, startSbcPlugin })

            await wrapper.vm.startBackend()

            expect(startSbcPlugin).toHaveBeenCalled()
            expect(startSbcPlugin.mock.calls[0][1]).toBe('Vigil')
            expect(wrapper.vm.snackbar.color).toBe('success')
            expect(wrapper.vm.startingBackend).toBe(false)
        })

        it('sets startingBackend during the operation', async () => {
            wrapper = mountDashboard({ pid: -1 })

            const promise = wrapper.vm.startBackend()
            expect(wrapper.vm.startingBackend).toBe(true)
            await promise
            expect(wrapper.vm.startingBackend).toBe(false)
        })

        it('reports an error when DSF refuses to start the plugin', async () => {
            const startSbcPlugin = jest.fn(() => {
                throw new Error('Incompatible DSF version')
            })
            wrapper = mountDashboard({ pid: -1, startSbcPlugin })

            await wrapper.vm.startBackend()

            expect(wrapper.vm.snackbar.color).toBe('error')
            expect(wrapper.vm.snackbar.text).toContain('Incompatible DSF version')
            expect(wrapper.vm.startingBackend).toBe(false)
        })

        it('reports an error when the endpoints never come up', async () => {
            wrapper = mountDashboard({ pid: -1 })
            jest.spyOn(wrapper.vm, 'waitForBackend').mockResolvedValue(false)

            await wrapper.vm.startBackend()

            expect(wrapper.vm.snackbar.color).toBe('error')
            expect(wrapper.vm.snackbar.text).toContain('did not come up')
        })
    })

    describe('waitForBackend', () => {
        it('returns true as soon as /status answers', async () => {
            wrapper = mountDashboard()
            await flushPromises()

            mockFetchSuccess({})
            await expect(wrapper.vm.waitForBackend(3, 1)).resolves.toBe(true)
            expect(global.fetch).toHaveBeenCalledTimes(1)
        })

        it('retries and returns false when /status keeps failing', async () => {
            wrapper = mountDashboard()
            await flushPromises()

            mockFetchError(404, 'Not Found')
            await expect(wrapper.vm.waitForBackend(3, 1)).resolves.toBe(false)
            expect(global.fetch).toHaveBeenCalledTimes(3)
        })
    })
})
