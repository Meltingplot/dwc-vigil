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
import Chart from 'chart.js'

export default {
    name: 'FanChart',
    props: {
        fans: { type: Object, default: () => ({}) },
    },
    data() {
        return { chart: null }
    },
    computed: {
        hasData() { return Object.keys(this.fans).length > 0 }
    },
    watch: {
        fans: {
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

            const labels = Object.keys(this.fans).map(k => `Fan ${k}`)
            const onHours = Object.values(this.fans).map(f => (f.on_seconds || 0) / 3600)

            if (this.chart) {
                this.chart.config.data.labels = labels
                this.chart.config.data.datasets[0].data = onHours
                this.chart.update()
                return
            }

            this.chart = new Chart(this.$refs.chart, {
                type: 'horizontalBar',
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
