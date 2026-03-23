<template>
  <v-card outlined>
    <v-card-title class="text-subtitle-1">Heater Usage</v-card-title>
    <v-card-text>
      <canvas ref="chart" height="200" />
      <div v-if="!hasData" class="text-center grey--text py-8">
        No heater data yet
      </div>
    </v-card-text>
  </v-card>
</template>

<script>
export default {
    name: 'HeaterChart',
    props: {
        heaters: { type: Object, default: () => ({}) },
    },
    data() {
        return { chartInstance: null }
    },
    computed: {
        hasData() { return Object.keys(this.heaters).length > 0 }
    },
    watch: {
        heaters: {
            deep: true,
            handler() { this.renderChart() }
        }
    },
    mounted() {
        this.loadChartJs()
    },
    beforeDestroy() {
        if (this.chartInstance) this.chartInstance.destroy()
    },
    methods: {
        async loadChartJs() {
            if (typeof window.Chart === 'undefined') {
                try {
                    await import('chart.js/auto')
                } catch {
                    return
                }
            }
            this.renderChart()
        },
        renderChart() {
            if (!this.$refs.chart || !this.hasData || typeof window.Chart === 'undefined') return

            const labels = Object.keys(this.heaters).map(k => `Heater ${k}`)
            const onHours = Object.values(this.heaters).map(h => (h.on_seconds || 0) / 3600)
            const fullLoadHours = Object.values(this.heaters).map(h => (h.full_load_seconds || 0) / 3600)

            // Update in-place if labels haven't changed to avoid animation replay
            if (this.chartInstance) {
                const currentLabels = this.chartInstance.data.labels
                if (currentLabels.length === labels.length && currentLabels.every((l, i) => l === labels[i])) {
                    this.chartInstance.data.datasets[0].data = onHours
                    this.chartInstance.data.datasets[1].data = fullLoadHours
                    this.chartInstance.update('none')
                    return
                }
                this.chartInstance.destroy()
            }

            this.chartInstance = new window.Chart(this.$refs.chart, {
                type: 'bar',
                data: {
                    labels,
                    datasets: [
                        {
                            label: 'On Time (h)',
                            data: onHours,
                            backgroundColor: '#2196F3',
                        },
                        {
                            label: 'Full Load (h)',
                            data: fullLoadHours,
                            backgroundColor: '#FF9800',
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    indexAxis: 'y',
                    plugins: {
                        legend: { position: 'bottom' }
                    },
                    scales: {
                        x: { title: { display: true, text: 'Hours' } }
                    }
                }
            })
        }
    }
}
</script>
