import { describe, it, expect, vi } from 'vitest'
import {
    applyConfig,
    fanChartConfig,
    heaterChartConfig,
    historyChartConfig,
    jobsChartConfig,
} from '../../src/core/charts'

/**
 * These configs were translated from Chart.js 2.9 (what DWC 3.6 ships) to Chart.js 4
 * (what the plugin now brings itself). The 2.9 spellings — `scales.xAxes[]`,
 * `scaleLabel`, top-level `legend`, `ticks.beginAtZero`, `type: 'horizontalBar'` — are
 * silently ignored by v4 rather than rejected, so the assertions below name the v4
 * option explicitly and the absence of its v2 predecessor.
 */
describe('chart configs', () => {
    describe('job outcomes', () => {
        it('plots successful against cancelled', () => {
            const config = jobsChartConfig({ successful: 7, cancelled: 2 })
            expect(config.type).toBe('doughnut')
            expect(config.data.labels).toEqual(['Successful', 'Cancelled'])
            expect(config.data.datasets[0].data).toEqual([7, 2])
        })

        it('uses the v4 spelling for the hole and the legend', () => {
            const config = jobsChartConfig({ successful: 1, cancelled: 0 })
            expect(config.options.cutout).toBe('65%')
            expect(config.options.cutoutPercentage).toBeUndefined()
            expect(config.options.plugins.legend.position).toBe('bottom')
            expect(config.options.legend).toBeUndefined()
        })

        it('defaults both counters to zero', () => {
            expect(jobsChartConfig().data.datasets[0].data).toEqual([0, 0])
        })
    })

    describe('heaters', () => {
        it('shows on-time and full-load time in hours', () => {
            const config = heaterChartConfig({
                0: { on_seconds: 3600, full_load_seconds: 1800 },
                1: { on_seconds: 7200 },
            })
            expect(config.data.labels).toEqual(['Heater 0', 'Heater 1'])
            expect(config.data.datasets[0].data).toEqual([1, 2])
            // Missing full_load_seconds counts as zero, not NaN
            expect(config.data.datasets[1].data).toEqual([0.5, 0])
        })

        it('is a bar chart on the y index axis, not the removed horizontalBar type', () => {
            const config = heaterChartConfig({ 0: { on_seconds: 0 } })
            expect(config.type).toBe('bar')
            expect(config.options.indexAxis).toBe('y')
        })

        it('names the hours axis with the v4 scale options', () => {
            const { scales } = heaterChartConfig({ 0: { on_seconds: 0 } }).options
            expect(scales.x.title).toEqual({ display: true, text: 'Hours' })
            expect(scales.x.scaleLabel).toBeUndefined()
            expect(scales.xAxes).toBeUndefined()
            // drawBorder moved off gridLines onto its own `border` option in v4
            expect(scales.x.border.display).toBe(false)
        })
    })

    describe('fans', () => {
        it('shows one on-time series', () => {
            const config = fanChartConfig({ 2: { on_seconds: 1800 } })
            expect(config.data.labels).toEqual(['Fan 2'])
            expect(config.data.datasets).toHaveLength(1)
            expect(config.data.datasets[0].data).toEqual([0.5])
        })

        it('copes with no fans at all', () => {
            expect(fanChartConfig().data.labels).toEqual([])
            expect(fanChartConfig().data.datasets[0].data).toEqual([])
        })
    })

    describe('history', () => {
        it('labels the dataset and the y axis with the selected metric', () => {
            const config = historyChartConfig({
                labels: ['2026-09-09', '2026-09-10'],
                values: [1, 4],
                label: 'Print Hours',
            })
            expect(config.data.datasets[0].label).toBe('Print Hours')
            expect(config.options.scales.y.title).toEqual({ display: true, text: 'Print Hours' })
        })

        it('puts beginAtZero on the scale, where v3 moved it', () => {
            const { scales } = historyChartConfig().options
            expect(scales.y.beginAtZero).toBe(true)
            expect(scales.y.ticks).toBeUndefined()
        })

        it('hides the legend of its single series', () => {
            expect(historyChartConfig().options.plugins.legend.display).toBe(false)
        })
    })

    it('never animates — every chart is redrawn on each poll', () => {
        for (const config of [jobsChartConfig(), heaterChartConfig(), fanChartConfig(), historyChartConfig()]) {
            expect(config.options.animation.duration).toBe(0)
            expect(config.options.responsive).toBe(true)
            expect(config.options.maintainAspectRatio).toBe(false)
        }
    })

    describe('applyConfig', () => {
        it('swaps data and options into a live chart and redraws it', () => {
            const chart = { data: null, options: null, update: vi.fn() }
            const config = fanChartConfig({ 0: { on_seconds: 3600 } })

            applyConfig(chart, config)

            expect(chart.data).toBe(config.data)
            // The y-axis title changes with the selected history metric, so the
            // options have to travel with the data.
            expect(chart.options).toBe(config.options)
            expect(chart.update).toHaveBeenCalled()
        })
    })
})
