<template>
  <v-card outlined>
    <v-card-title class="text-subtitle-1">Fan Usage</v-card-title>
    <v-card-text>
      <canvas ref="chart" height="200" />
      <div v-if="!hasData" class="text-center grey--text py-8">
        No fan data yet
      </div>
    </v-card-text>
  </v-card>
</template>

<script>
export default {
    name: 'FanChart',
    props: {
        fans: { type: Object, default: () => ({}) },
    },
    data() {
        return { chartInstance: null, lastDataJson: '' }
    },
    computed: {
        hasData() { return Object.keys(this.fans).length > 0 }
    },
    watch: {
        fans: {
            deep: true,
            handler() {
                const json = JSON.stringify(this.fans)
                if (json === this.lastDataJson) return
                this.renderChart()
            }
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

            const labels = Object.keys(this.fans).map(k => `Fan ${k}`)
            const onHours = Object.values(this.fans).map(f => (f.on_seconds || 0) / 3600)

            // Update in-place to avoid animation replay on poll
            if (this.chartInstance) {
                const currentLabels = this.chartInstance.data.labels
                if (currentLabels.length === labels.length && currentLabels.every((l, i) => l === labels[i])) {
                    this.chartInstance.data.datasets[0].data = onHours
                    this.chartInstance.update('none')
                    this.lastDataJson = JSON.stringify(this.fans)
                    return
                }
                this.chartInstance.destroy()
            }

            this.chartInstance = new window.Chart(this.$refs.chart, {
                type: 'bar',
                data: {
                    labels,
                    datasets: [{
                        label: 'On Time (h)',
                        data: onHours,
                        backgroundColor: '#009688',
                    }]
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
            this.lastDataJson = JSON.stringify(this.fans)
        }
    }
}
</script>
