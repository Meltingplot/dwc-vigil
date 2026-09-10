import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mountInDwc } from 'dwc-plugin-test-kit'
import AxisTable from '../../src/ui37/components/AxisTable.vue'
import CounterTabs from '../../src/ui37/components/CounterTabs.vue'
import ExportButton from '../../src/ui37/components/ExportButton.vue'
import ServiceEventDialog from '../../src/ui37/components/ServiceEventDialog.vue'
import ServiceLogDialog from '../../src/ui37/components/ServiceLogDialog.vue'
import ServiceResetDialog from '../../src/ui37/components/ServiceResetDialog.vue'
import StatCard from '../../src/ui37/components/StatCard.vue'
import VitalsCard from '../../src/ui37/components/VitalsCard.vue'

/**
 * These mount against real Vuetify 4 rather than stubs, because the DWC 3.6 → 3.7 port
 * is mostly template: a Vuetify 2 prop or component name that survived the translation
 * is valid markup and only the running component knows it is wrong (plan §7.4).
 * `expectNoVueWarnings` is what turns "resolved to nothing" into a failure.
 */
let warn

beforeEach(() => {
    warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
})

afterEach(() => {
    vi.restoreAllMocks()
})

function expectNoVueWarnings() {
    const messages = warn.mock.calls.map(args => String(args[0]))
    expect(messages.filter(m => /Failed to resolve|\[Vue warn\]/.test(m))).toEqual([])
}

describe('StatCard', () => {
    it('renders a formatted count', () => {
        const wrapper = mountInDwc(StatCard, { props: { label: 'Jobs Total', value: 42 } })
        expect(wrapper.text()).toContain('Jobs Total')
        expect(wrapper.text()).toContain('42')
        expectNoVueWarnings()
    })

    it('renders a formatted duration', () => {
        const wrapper = mountInDwc(StatCard, { props: { label: 'Machine Time', value: 90061, type: 'time' } })
        expect(wrapper.text()).toContain('1d 1h 1m')
    })
})

describe('CounterTabs', () => {
    it('renders the three counter tiers', () => {
        const wrapper = mountInDwc(CounterTabs, { props: { modelValue: 0 } })
        expect(wrapper.text()).toContain('Lifetime')
        expect(wrapper.text()).toContain('Since Service')
        expect(wrapper.text()).toContain('Session')
        expectNoVueWarnings()
    })

    it('reports the selected tier through v-model', async () => {
        const wrapper = mountInDwc(CounterTabs, { props: { modelValue: 0 } })
        await wrapper.findAll('.v-tab')[1].trigger('click')
        expect(wrapper.emitted('update:modelValue')).toEqual([[1]])
    })
})

describe('AxisTable', () => {
    it('lists axes, extruder totals and filament separately', () => {
        const wrapper = mountInDwc(AxisTable, {
            props: { axes: { X: 1500, E0: 2000 }, filament: { E0: 950 } }
        })
        const text = wrapper.text()
        expect(text).toContain('1.50 m')
        expect(text).toContain('E0 (total)')
        expect(text).toContain('E0 (filament)')
        expect(text).toContain('950 mm')
        expectNoVueWarnings()
    })

    it('shows a placeholder without data', () => {
        const wrapper = mountInDwc(AxisTable)
        expect(wrapper.text()).toContain('No axis data yet')
    })
})

describe('VitalsCard', () => {
    it('renders board, SBC and uptime figures', () => {
        const wrapper = mountInDwc(VitalsCard, {
            props: {
                vitals: { mcu_temp_min: 30, mcu_temp_max: 41.25, vin_min: 23.9, vin_max: 24.1 },
                uptime: { firmware_uptime_secs: 90061, firmware_reboots: 3 },
                volumeFreeBytes: 3 * 1073741824,
            }
        })
        const text = wrapper.text()
        expect(text).toContain('41.3 °C')
        expect(text).toContain('24.10 V')
        expect(text).toContain('1d 1h 1m')
        expect(text).toContain('3.0 GB')
        expectNoVueWarnings()
    })

    it('shows a placeholder without data', () => {
        const wrapper = mountInDwc(VitalsCard)
        expect(wrapper.text()).toContain('No vitals data yet')
    })
})

describe('ExportButton', () => {
    it('emits the chosen format', async () => {
        const wrapper = mountInDwc(ExportButton, { attachTo: document.body })
        await wrapper.find('button').trigger('click')
        await new Promise(resolve => setTimeout(resolve, 0))

        // The menu renders into an overlay outside the component's own subtree
        const items = [...document.querySelectorAll('.v-list-item')]
        expect(items.map(i => i.textContent.trim())).toEqual(['Export JSON', 'Export CSV'])
        items[1].click()
        expect(wrapper.emitted('export')).toEqual([['csv']])
    })
})

describe('ServiceEventDialog', () => {
    it('submits the component and description', () => {
        const wrapper = mountInDwc(ServiceEventDialog, { props: { modelValue: true } })
        wrapper.vm.component = 'nozzle'
        wrapper.vm.description = 'Replaced the nozzle'
        expect(wrapper.vm.isValid).toBe(true)

        wrapper.vm.submit()
        expect(wrapper.emitted('submit')).toEqual([[
            { component: 'nozzle', description: 'Replaced the nozzle' }
        ]])
        expectNoVueWarnings()
    })

    it('rejects a description shorter than three characters', () => {
        const wrapper = mountInDwc(ServiceEventDialog, { props: { modelValue: true } })
        wrapper.vm.description = 'ab'
        expect(wrapper.vm.isValid).toBe(false)
    })

    it('closes through v-model and resets its fields', () => {
        const wrapper = mountInDwc(ServiceEventDialog, { props: { modelValue: true } })
        wrapper.vm.description = 'Replaced the nozzle'
        wrapper.vm.close()
        expect(wrapper.vm.description).toBe('')
        expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
    })
})

describe('ServiceResetDialog', () => {
    it('offers the counters of the selected scope', async () => {
        const wrapper = mountInDwc(ServiceResetDialog, {
            props: {
                modelValue: true,
                serviceData: { axes: { X: 1, E0: 2 }, heaters: { 0: {}, 1: {} } },
            }
        })

        wrapper.vm.scope = 'axes'
        await wrapper.vm.$nextTick()
        expect(wrapper.vm.availableKeys).toEqual(['X'])

        wrapper.vm.scope = 'extruders'
        await wrapper.vm.$nextTick()
        expect(wrapper.vm.availableKeys).toEqual(['E0'])

        wrapper.vm.scope = 'heaters'
        await wrapper.vm.$nextTick()
        expect(wrapper.vm.availableKeys).toEqual(['0', '1'])
        expectNoVueWarnings()
    })

    it('clears the selection when the scope changes', async () => {
        const wrapper = mountInDwc(ServiceResetDialog, {
            props: { modelValue: true, serviceData: { heaters: { 0: {} } } }
        })
        wrapper.vm.scope = 'heaters'
        await wrapper.vm.$nextTick()
        wrapper.vm.selectedKeys = ['0']

        wrapper.vm.scope = 'fans'
        await wrapper.vm.$nextTick()
        expect(wrapper.vm.selectedKeys).toEqual([])
    })

    it('submits null keys when nothing was ticked, meaning "the whole scope"', () => {
        const wrapper = mountInDwc(ServiceResetDialog, { props: { modelValue: true } })
        wrapper.vm.scope = 'jobs'
        wrapper.vm.description = 'Annual service'

        wrapper.vm.submit()
        expect(wrapper.emitted('reset')).toEqual([[
            { scope: 'jobs', keys: null, description: 'Annual service', component: null }
        ]])
    })
})

describe('ServiceLogDialog', () => {
    // v-dialog teleports its content out of the component's own subtree, so the
    // rendered markup is read off the document rather than off the wrapper.
    async function openLog(entries) {
        const wrapper = mountInDwc(ServiceLogDialog, {
            props: { modelValue: true, entries },
            attachTo: document.body,
        })
        await wrapper.vm.$nextTick()
        await new Promise(resolve => setTimeout(resolve, 0))
        return document.body.textContent
    }

    it('renders one timeline entry per log record', async () => {
        const text = await openLog([
            { type: 'service', description: 'Replaced the nozzle', component: 'nozzle', timestamp: '2026-09-10T08:00:00Z' },
            { type: 'counter_reset', description: 'Annual service', reset_scope: 'heaters', reset_keys: ['0'], timestamp: '2026-09-10T09:00:00Z' },
        ])
        expect(text).toContain('Replaced the nozzle')
        expect(text).toContain('nozzle')
        expect(text).toContain('Reset: heaters')
        expect(text).toContain('(0)')
        expectNoVueWarnings()
    })

    it('shows a placeholder for an empty log', async () => {
        expect(await openLog([])).toContain('No service events logged yet')
    })
})
