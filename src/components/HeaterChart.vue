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
import Chart from 'chart.js'

export default {
    name: 'HeaterChart',
    props: {
        heaters: { type: Object, default: () => ({}) },
    },
    data() {
        return { chart: null }
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
        this.renderChart()
    },
    beforeDestroy() {
        if (this.chart) this.chart.destroy()
    },
    methods: {
        renderChart() {
            if (!this.$refs.chart || !this.hasData) return

            const labels = Object.keys(this.heaters).map(k => `Heater ${k}`)
            const onHours = Object.values(this.heaters).map(h => (h.on_seconds || 0) / 3600)
            const fullLoadHours = Object.values(this.heaters).map(h => (h.full_load_seconds || 0) / 3600)

            if (this.chart) {
                this.chart.config.data.labels = labels
                this.chart.config.data.datasets[0].data = onHours
                this.chart.config.data.datasets[1].data = fullLoadHours
                this.chart.update()
                return
            }

            this.chart = new Chart(this.$refs.chart, {
                type: 'horizontalBar',
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
                    animation: { duration: 0 },
                    responsiveAnimationDuration: 0,
                    legend: { position: 'bottom' },
                    scales: {
                        xAxes: [{
                            scaleLabel: { display: true, labelString: 'Hours' }
                        }]
                    }
                }
            })
        }
    }
}
</script>
