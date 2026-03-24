<template>
  <v-card style="border-radius: 8px; height: 100%">
    <v-card-title class="text-subtitle-2 pb-0">
      <v-icon small color="teal" class="mr-2">mdi-fan</v-icon>
      Fan Usage
    </v-card-title>
    <v-card-text style="max-height: 280px">
      <div v-if="hasData" style="position: relative; max-height: 240px">
        <canvas ref="chart" />
      </div>
      <div v-else class="d-flex flex-column align-center justify-center" style="height: 200px">
        <v-icon size="40" color="grey lighten-1">mdi-fan</v-icon>
        <div class="text-caption grey--text mt-2">No fan data yet</div>
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
            if (!this.hasData) return
            if (!this.$refs.chart) {
                this.$nextTick(() => this.renderChart())
                return
            }

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
                        backgroundColor: 'rgba(0, 150, 136, 0.75)',
                        borderRadius: 4,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: { duration: 0 },
                    responsiveAnimationDuration: 0,
                    legend: {
                        position: 'bottom',
                        labels: { boxWidth: 12, padding: 16 }
                    },
                    scales: {
                        xAxes: [{
                            scaleLabel: { display: true, labelString: 'Hours' },
                            gridLines: { drawBorder: false, color: 'rgba(0,0,0,0.05)' }
                        }],
                        yAxes: [{
                            gridLines: { display: false }
                        }]
                    }
                }
            })
        }
    }
}
</script>
