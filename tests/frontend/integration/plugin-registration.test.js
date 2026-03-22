import { describe, it, expect, beforeEach } from '@jest/globals'

jest.mock('@/routes')

describe('Plugin registration (index.js)', () => {
    let registerRoute

    beforeEach(() => {
        jest.resetModules()
        jest.mock('@/routes')
        registerRoute = require('@/routes').registerRoute
        registerRoute.mockClear()
        require('../../../src/index.js')
    })

    it('calls registerRoute exactly once', () => {
        expect(registerRoute).toHaveBeenCalledTimes(1)
    })

    it('passes a Vue component as first argument', () => {
        const component = registerRoute.mock.calls[0][0]
        expect(component).toBeDefined()
        expect(component.name).toBe('VigilDashboard')
    })

    it('registers under Plugins namespace', () => {
        const routeConfig = registerRoute.mock.calls[0][1]
        expect(routeConfig).toHaveProperty('Plugins')
        expect(routeConfig.Plugins).toHaveProperty('Vigil')
    })

    it('specifies correct route path', () => {
        const entry = registerRoute.mock.calls[0][1].Plugins.Vigil
        expect(entry.path).toBe('/Vigil')
    })

    it('specifies an mdi icon', () => {
        const entry = registerRoute.mock.calls[0][1].Plugins.Vigil
        expect(entry.icon).toMatch(/^mdi-/)
    })

    it('specifies a non-empty caption', () => {
        const entry = registerRoute.mock.calls[0][1].Plugins.Vigil
        expect(entry.caption).toBeTruthy()
        expect(typeof entry.caption).toBe('string')
    })

    it('marks caption as translated', () => {
        const entry = registerRoute.mock.calls[0][1].Plugins.Vigil
        expect(entry.translated).toBe(true)
    })

    it('component has all child components registered', () => {
        const component = registerRoute.mock.calls[0][0]
        expect(component.components).toHaveProperty('CounterTabs')
        expect(component.components).toHaveProperty('StatCard')
        expect(component.components).toHaveProperty('JobsPieChart')
        expect(component.components).toHaveProperty('HeaterChart')
        expect(component.components).toHaveProperty('AxisTable')
        expect(component.components).toHaveProperty('HistoryChart')
        expect(component.components).toHaveProperty('ExportButton')
    })
})
