<template>
  <v-card style="border-radius: 8px">
    <v-card-title class="text-subtitle-2 d-flex align-center pb-0">
      <v-icon size="small" color="blue" class="mr-2">mdi-chart-timeline-variant</v-icon>
      30-Day History
      <v-spacer />
      <v-select
        v-model="metric"
        :items="metrics"
        density="compact"
        variant="outlined"
        hide-details
        style="max-width: 200px"
        class="ml-2 text-caption"
      />
      <v-select
        v-if="subKeys.length > 0"
        v-model="subKey"
        :items="subKeys"
        density="compact"
        variant="outlined"
        hide-details
        style="max-width: 120px"
        class="ml-2 text-caption"
      />
    </v-card-title>
    <v-card-text>
      <canvas ref="chart" height="200" />
      <div v-if="loading" class="d-flex flex-column align-center justify-center" style="min-height: 160px">
        <v-progress-circular indeterminate size="32" color="primary" />
      </div>
      <div v-else-if="!hasData" class="d-flex flex-column align-center justify-center" style="min-height: 160px">
        <v-icon size="40" color="grey-lighten-1">mdi-chart-timeline-variant</v-icon>
        <div class="text-caption text-medium-emphasis mt-2">No history data yet</div>
      </div>
    </v-card-text>
  </v-card>
</template>

<script>
import { Chart, applyConfig, historyChartConfig } from '../../core/charts'

const DICT_METRICS = new Set([
    'heater_on_hours', 'fan_on_hours', 'axis_travel_mm', 'filament_mm',
])

// Vuetify 4 reads `title`/`value` off item objects (Vuetify 2 read `text`/`value`), and
// group captions are items of their own with `type: 'subheader'` rather than `header`.
const METRICS = [
    { type: 'subheader', title: 'Time' },
    { title: 'Print Hours', value: 'print_hours' },
    { title: 'Machine Hours', value: 'machine_hours' },
    { title: 'Pause Hours', value: 'pause_hours' },
    { title: 'Warmup Hours', value: 'warmup_hours' },
    { type: 'subheader', title: 'Jobs' },
    { title: 'Jobs Total', value: 'jobs_total' },
    { title: 'Jobs Successful', value: 'jobs_successful' },
    { title: 'Jobs Cancelled', value: 'jobs_cancelled' },
    { type: 'subheader', title: 'Heaters & Fans' },
    { title: 'Heater On Hours', value: 'heater_on_hours' },
    { title: 'Fan On Hours', value: 'fan_on_hours' },
    { type: 'subheader', title: 'Travel' },
    { title: 'Axis Travel (mm)', value: 'axis_travel_mm' },
    { title: 'Filament (mm)', value: 'filament_mm' },
    { type: 'subheader', title: 'Vitals' },
    { title: 'MCU Temp Max', value: 'mcu_temp_max' },
    { title: 'MCU Temp Min', value: 'mcu_temp_min' },
    { title: 'Vin Max', value: 'vin_max' },
    { title: 'Vin Min', value: 'vin_min' },
    { title: 'V12 Max', value: 'v12_max' },
    { title: 'V12 Min', value: 'v12_min' },
    { title: 'SBC CPU Temp Max', value: 'sbc_cpu_temp_max' },
    { title: 'SBC CPU Load Avg', value: 'sbc_cpu_load_avg' },
    { title: 'SBC Memory Min (MB)', value: 'sbc_memory_min_mb' },
    { type: 'subheader', title: 'System' },
    { title: 'Firmware Reboots', value: 'firmware_reboots' },
    { title: 'SBC Reboots', value: 'sbc_reboots' },
    { title: 'Disk Free (MB)', value: 'volume_free_mb' },
]

export default {
    name: 'HistoryChart',
    props: {
        days: { type: Array, default: () => [] },
        loading: { type: Boolean, default: false },
    },
    data() {
        return {
            metric: 'print_hours',
            subKey: '',
            metrics: METRICS,
            chart: null,
        }
    },
    computed: {
        hasData() { return this.days.length > 0 },
        isDictMetric() { return DICT_METRICS.has(this.metric) },
        subKeys() {
            if (!this.isDictMetric) return []
            const keys = new Set()
            for (const day of this.days) {
                const dict = day[this.metric]
                if (dict && typeof dict === 'object') {
                    Object.keys(dict).forEach(k => keys.add(k))
                }
            }
            return Array.from(keys).sort()
        },
        metricLabel() {
            const item = this.metrics.find(m => m.value === this.metric)
            let label = item ? item.title : this.metric
            if (this.isDictMetric && this.subKey) {
                label += ` [${this.subKey}]`
            }
            return label
        },
        chartValues() {
            return this.days.map(d => {
                if (this.isDictMetric) {
                    const dict = d[this.metric]
                    if (dict && typeof dict === 'object') {
                        return dict[this.subKey] || 0
                    }
                    return 0
                }
                return d[this.metric] || 0
            })
        },
        config() {
            return historyChartConfig({
                labels: this.days.map(d => d.date),
                values: this.chartValues,
                label: this.metricLabel,
            })
        },
    },
    watch: {
        days() { this.renderChart() },
        metric() {
            if (this.isDictMetric && this.subKeys.length > 0 && !this.subKeys.includes(this.subKey)) {
                this.subKey = this.subKeys[0]
            }
            this.renderChart()
        },
        subKey() { this.renderChart() },
    },
    mounted() {
        this.renderChart()
    },
    beforeUnmount() {
        if (this.chart) this.chart.destroy()
    },
    methods: {
        renderChart() {
            if (!this.$refs.chart || !this.hasData) return
            if (this.chart) {
                applyConfig(this.chart, this.config)
                return
            }
            this.chart = new Chart(this.$refs.chart, this.config)
        }
    }
}
</script>
