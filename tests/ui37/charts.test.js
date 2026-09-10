import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mountInDwc } from 'dwc-plugin-test-kit'

/**
 * happy-dom has no 2D canvas context, so the real Chart.js cannot draw here. The
 * configs themselves are covered without a DOM in tests/core/charts.test.js; what is
 * left for the wrappers is the lifecycle — create once, then update in place rather
 * than leaking a second chart per poll, and destroy on unmount.
 */
const instances = []

vi.mock('../../src/core/charts', async (importOriginal) => {
    const actual = await importOriginal()
    return {
        ...actual,
        Chart: class {
            constructor(canvas, config) {
                this.canvas = canvas
                this.data = config.data
                this.options = config.options
                this.destroyed = false
                instances.push(this)
            }
            update() { this.updates = (this.updates || 0) + 1 }
            destroy() { this.destroyed = true }
        },
    }
})

const FanChart = (await import('../../src/ui37/components/FanChart.vue')).default
const HeaterChart = (await import('../../src/ui37/components/HeaterChart.vue')).default
const HistoryChart = (await import('../../src/ui37/components/HistoryChart.vue')).default
const JobsPieChart = (await import('../../src/ui37/components/JobsPieChart.vue')).default

beforeEach(() => {
    instances.length = 0
})

describe('chart components', () => {
    it('draws nothing until there is data to draw', () => {
        const wrapper = mountInDwc(FanChart, { props: { fans: {} } })
        expect(instances).toHaveLength(0)
        expect(wrapper.text()).toContain('No fan data yet')
    })

    it('creates one chart per series and updates it in place', async () => {
        const wrapper = mountInDwc(FanChart, { props: { fans: { 0: { on_seconds: 3600 } } } })
        expect(instances).toHaveLength(1)
        expect(instances[0].data.datasets[0].data).toEqual([1])

        await wrapper.setProps({ fans: { 0: { on_seconds: 7200 } } })
        expect(instances).toHaveLength(1)
        expect(instances[0].data.datasets[0].data).toEqual([2])
        expect(instances[0].updates).toBe(1)
    })

    it('destroys its chart on unmount', () => {
        const wrapper = mountInDwc(HeaterChart, { props: { heaters: { 0: { on_seconds: 3600 } } } })
        expect(instances).toHaveLength(1)
        wrapper.unmount()
        expect(instances[0].destroyed).toBe(true)
    })

    it('starts drawing once the first job finishes', async () => {
        const wrapper = mountInDwc(JobsPieChart, { props: { successful: 0, cancelled: 0 } })
        expect(instances).toHaveLength(0)

        await wrapper.setProps({ successful: 1 })
        await wrapper.vm.$nextTick()
        expect(instances).toHaveLength(1)
        expect(instances[0].data.datasets[0].data).toEqual([1, 0])
    })

    it('relabels the history axis when the metric changes', async () => {
        const wrapper = mountInDwc(HistoryChart, {
            props: { days: [{ date: '2026-09-10', print_hours: 4, machine_hours: 9 }] }
        })
        expect(instances[0].data.datasets[0].label).toBe('Print Hours')

        wrapper.vm.metric = 'machine_hours'
        await wrapper.vm.$nextTick()
        expect(instances).toHaveLength(1)
        expect(instances[0].data.datasets[0].label).toBe('Machine Hours')
        expect(instances[0].options.scales.y.title.text).toBe('Machine Hours')
    })

    it('drills into a per-heater history metric', async () => {
        const wrapper = mountInDwc(HistoryChart, {
            props: { days: [{ date: '2026-09-10', heater_on_hours: { 0: 3, 1: 5 } }] }
        })

        wrapper.vm.metric = 'heater_on_hours'
        await wrapper.vm.$nextTick()
        // The first sub-key is selected automatically when the metric has any
        expect(wrapper.vm.subKeys).toEqual(['0', '1'])
        expect(wrapper.vm.subKey).toBe('0')
        expect(instances[0].data.datasets[0].data).toEqual([3])

        wrapper.vm.subKey = '1'
        await wrapper.vm.$nextTick()
        expect(instances[0].data.datasets[0].data).toEqual([5])
        expect(instances[0].data.datasets[0].label).toBe('Heater On Hours [1]')
    })
})
