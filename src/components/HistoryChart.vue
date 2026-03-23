<template>
  <v-card outlined>
    <v-card-title class="text-subtitle-1 d-flex align-center">
      History
      <v-spacer />
      <v-select
        v-model="metric"
        :items="metrics"
        dense
        outlined
        hide-details
        style="max-width: 200px"
        class="ml-2"
      />
      <v-select
        v-if="subKeys.length > 0"
        v-model="subKey"
        :items="subKeys"
        dense
        outlined
        hide-details
        style="max-width: 120px"
        class="ml-2"
      />
    </v-card-title>
    <v-card-text>
      <canvas ref="chart" height="200" />
      <div v-if="loading" class="text-center py-8">
        <v-progress-circular indeterminate size="32" />
      </div>
      <div v-else-if="!hasData" class="text-center grey--text py-8">
        No history data yet
      </div>
    </v-card-text>
  </v-card>
</template>

<script>
import Chart from 'chart.js'

const DICT_METRICS = new Set([
    'heater_on_hours', 'fan_on_hours', 'axis_travel_mm', 'filament_mm',
])

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
            metrics: [
                { header: 'Time' },
                { text: 'Print Hours', value: 'print_hours' },
                { text: 'Machine Hours', value: 'machine_hours' },
                { text: 'Pause Hours', value: 'pause_hours' },
                { text: 'Warmup Hours', value: 'warmup_hours' },
                { header: 'Jobs' },
                { text: 'Jobs Total', value: 'jobs_total' },
                { text: 'Jobs Successful', value: 'jobs_successful' },
                { text: 'Jobs Cancelled', value: 'jobs_cancelled' },
                { header: 'Heaters & Fans' },
                { text: 'Heater On Hours', value: 'heater_on_hours' },
                { text: 'Fan On Hours', value: 'fan_on_hours' },
                { header: 'Travel' },
                { text: 'Axis Travel (mm)', value: 'axis_travel_mm' },
                { text: 'Filament (mm)', value: 'filament_mm' },
                { header: 'Vitals' },
                { text: 'MCU Temp Max (°C)', value: 'mcu_temp_max' },
                { text: 'MCU Temp Min (°C)', value: 'mcu_temp_min' },
                { text: 'Vin Max (V)', value: 'vin_max' },
                { text: 'Vin Min (V)', value: 'vin_min' },
                { text: 'V12 Max (V)', value: 'v12_max' },
                { text: 'V12 Min (V)', value: 'v12_min' },
                { text: 'SBC CPU Temp Max', value: 'sbc_cpu_temp_max' },
                { text: 'SBC CPU Load Avg', value: 'sbc_cpu_load_avg' },
                { text: 'SBC Memory Min (MB)', value: 'sbc_memory_min_mb' },
                { header: 'System' },
                { text: 'Firmware Reboots', value: 'firmware_reboots' },
                { text: 'SBC Reboots', value: 'sbc_reboots' },
                { text: 'Disk Free (MB)', value: 'volume_free_mb' },
            ],
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
            let label = item ? item.text : this.metric
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
    beforeDestroy() {
        if (this.chart) this.chart.destroy()
    },
    methods: {
        renderChart() {
            if (!this.$refs.chart || !this.hasData) return

            const labels = this.days.map(d => d.date)
            const data = this.chartValues
            const label = this.metricLabel

            if (this.chart) {
                this.chart.config.data.labels = labels
                this.chart.config.data.datasets[0].data = data
                this.chart.config.data.datasets[0].label = label
                this.chart.config.options.scales.yAxes[0].scaleLabel.labelString = label
                this.chart.update()
                return
            }

            this.chart = new Chart(this.$refs.chart, {
                type: 'bar',
                data: {
                    labels,
                    datasets: [{
                        label,
                        data,
                        backgroundColor: '#1976D2',
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: { duration: 0 },
                    responsiveAnimationDuration: 0,
                    legend: { display: false },
                    scales: {
                        xAxes: [{
                            ticks: {
                                maxRotation: 45,
                                maxTicksLimit: 15,
                            }
                        }],
                        yAxes: [{
                            ticks: { beginAtZero: true },
                            scaleLabel: { display: true, labelString: label }
                        }]
                    }
                }
            })
        }
    }
}
</script>
