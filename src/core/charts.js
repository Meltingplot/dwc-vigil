'use strict'

/**
 * Chart configuration for both UI shells.
 *
 * The builders return plain objects, so the whole of Vigil's charting is unit-tested
 * without a canvas and the SFCs shrink to "create, apply, destroy".
 *
 * This is also the only module that imports Chart.js. DWC 3.6 ships Chart.js 2.9 and
 * DWC 3.7 does not expose Chart.js to plugins at all, so neither checkout can be relied
 * on: the plugin owns the dependency (`chart.js` in package.json), the 3.7 build bundles
 * it into the IIFE, and scripts/stage-dwc36.mjs vendors it into the 3.6 build's own
 * node_modules — where webpack finds it before the checkout's 2.9, leaving DWC's own
 * temperature and layer charts on the version they were written against.
 *
 * `chart.js/auto` registers every controller, scale and element; the à-la-carte entry
 * point would save a few KB at the cost of a registration list to keep in sync with
 * four charts' worth of chart types.
 */

import Chart from 'chart.js/auto'

export { Chart }

/** Redraw an existing chart from a freshly built config. */
export function applyConfig(chart, config) {
    chart.data = config.data
    chart.options = config.options
    chart.update()
}

/** Chart.js 4 replaced `gridLines.drawBorder` with a separate `border` scale option. */
const SUBTLE_GRID = {
    grid: { color: 'rgba(0,0,0,0.05)' },
    border: { display: false },
}

const NO_GRID = {
    grid: { display: false },
}

/** Charts are redrawn on every poll, so animating them would mean never settling. */
const STATIC = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 0 },
}

const BOTTOM_LEGEND = {
    position: 'bottom',
    labels: { boxWidth: 12, padding: 16 },
}

/**
 * Job outcomes as a doughnut.
 *
 * @param {{successful?: number, cancelled?: number}} jobs
 */
export function jobsChartConfig({ successful = 0, cancelled = 0 } = {}) {
    return {
        type: 'doughnut',
        data: {
            labels: ['Successful', 'Cancelled'],
            datasets: [{
                data: [successful, cancelled],
                backgroundColor: ['#4CAF50', '#EF5350'],
                borderWidth: 0,
            }],
        },
        options: {
            ...STATIC,
            cutout: '65%',
            plugins: { legend: BOTTOM_LEGEND },
        },
    }
}

/**
 * Horizontal bars of hours per series.
 *
 * Chart.js 4 dropped the `horizontalBar` type in favour of `indexAxis: 'y'` on a
 * regular bar chart.
 *
 * @param {Array<string>} labels
 * @param {Array<{label: string, data: Array<number>, color: string}>} datasets
 */
function hoursBarConfig(labels, datasets) {
    return {
        type: 'bar',
        data: {
            labels,
            datasets: datasets.map(({ label, data, color }) => ({
                label,
                data,
                backgroundColor: color,
                borderRadius: 4,
            })),
        },
        options: {
            ...STATIC,
            indexAxis: 'y',
            plugins: { legend: BOTTOM_LEGEND },
            scales: {
                x: { title: { display: true, text: 'Hours' }, ...SUBTLE_GRID },
                y: NO_GRID,
            },
        },
    }
}

/** Seconds as recorded by the daemon, shown as hours. */
function toHours(entries, key) {
    return entries.map((entry) => (entry[key] || 0) / 3600)
}

/**
 * Heater on-time and full-load time per heater.
 *
 * @param {Object<string, {on_seconds?: number, full_load_seconds?: number}>} heaters
 */
export function heaterChartConfig(heaters = {}) {
    const entries = Object.values(heaters)
    return hoursBarConfig(
        Object.keys(heaters).map((key) => `Heater ${key}`),
        [
            { label: 'On Time (h)', data: toHours(entries, 'on_seconds'), color: 'rgba(33, 150, 243, 0.75)' },
            { label: 'Full Load (h)', data: toHours(entries, 'full_load_seconds'), color: 'rgba(255, 152, 0, 0.75)' },
        ],
    )
}

/**
 * Fan on-time per fan.
 *
 * @param {Object<string, {on_seconds?: number}>} fans
 */
export function fanChartConfig(fans = {}) {
    return hoursBarConfig(
        Object.keys(fans).map((key) => `Fan ${key}`),
        [{ label: 'On Time (h)', data: toHours(Object.values(fans), 'on_seconds'), color: 'rgba(0, 150, 136, 0.75)' }],
    )
}

/**
 * One metric per day over the history window.
 *
 * @param {{labels: Array<string>, values: Array<number>, label: string}} series
 */
export function historyChartConfig({ labels = [], values = [], label = '' } = {}) {
    return {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label,
                data: values,
                backgroundColor: 'rgba(25, 118, 210, 0.65)',
                borderRadius: 3,
            }],
        },
        options: {
            ...STATIC,
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { maxRotation: 45, maxTicksLimit: 15 }, ...NO_GRID },
                // beginAtZero moved from scale.ticks onto the scale itself in v3
                y: { beginAtZero: true, title: { display: true, text: label }, ...SUBTLE_GRID },
            },
        },
    }
}
