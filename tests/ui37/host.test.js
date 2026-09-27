import { describe, it, expect, beforeEach } from 'vitest'
import { setModel } from 'dwc-plugin-test-kit'
import { createHost } from '../../src/ui37/host'
import { resetSbcPlugins, startedSbcPlugins, failNextSbcPluginStart, setConnector } from '../dwc-stubs/machine'

describe('DWC 3.7 host adapter', () => {
    beforeEach(() => {
        resetSbcPlugins()
        setConnector(null)
    })

    describe('pluginEntry', () => {
        it('is null while the object model carries no Vigil entry', () => {
            setModel({ plugins: new Map() })
            expect(createHost().pluginEntry()).toBeNull()
        })

        it('reads the entry out of the plugins Map', () => {
            setModel({ plugins: new Map([['Vigil', { pid: 4711 }]]) })
            // The kit's model is reactive(), so the entry comes back as a proxy of
            // the object that went in rather than the object itself.
            expect(createHost().pluginEntry()).toEqual({ pid: 4711 })
        })

        it('reads through the store on every call', () => {
            const plugins = new Map([['Vigil', { pid: -1 }]])
            setModel({ plugins })
            const host = createHost()
            expect(host.pluginEntry().pid).toBe(-1)

            // DSF reports a new PID: a cached entry would keep reporting -1 and the
            // dashboard's recovery banner would never go away.
            plugins.set('Vigil', { pid: 4711 })
            expect(host.pluginEntry().pid).toBe(4711)
        })
    })

    describe('startBackend', () => {
        it('asks the machine store to start this plugin on the SBC', async () => {
            await createHost().startBackend()
            expect(startedSbcPlugins()).toEqual(['Vigil'])
        })

        it('propagates a refusal from DSF', async () => {
            failNextSbcPluginStart(new Error('Incompatible DSF version'))
            await expect(createHost().startBackend()).rejects.toThrow('Incompatible DSF version')
        })
    })

    describe('sessionKey', () => {
        it('is null while not connected', () => {
            expect(createHost().sessionKey()).toBeNull()
        })

        it('reads the key off the machine store\'s connector on every call', () => {
            const connector = { sessionKey: 'first' }
            setConnector(connector)
            const host = createHost()
            expect(host.sessionKey()).toBe('first')

            // RestConnector logs in again on reconnect and replaces the key
            connector.sessionKey = 'second'
            expect(host.sessionKey()).toBe('second')
        })
    })
})
