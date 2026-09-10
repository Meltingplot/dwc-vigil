<template>
  <v-card style="border-radius: 8px; height: 100%">
    <v-card-title class="text-subtitle-2 pb-0">
      <v-icon small color="deep-orange" class="mr-2">mdi-thermometer</v-icon>
      Heater Usage
    </v-card-title>
    <v-card-text>
      <div v-if="hasData" style="position: relative; height: 200px">
        <canvas ref="chart" />
      </div>
      <div v-else class="d-flex flex-column align-center justify-center" style="height: 200px">
        <v-icon size="40" color="grey lighten-1">mdi-thermometer</v-icon>
        <div class="text-caption grey--text mt-2">No heater data yet</div>
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
            if (!this.hasData) return
            if (!this.$refs.chart) {
                this.$nextTick(() => this.renderChart())
                return
            }

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
                            backgroundColor: 'rgba(33, 150, 243, 0.75)',
                            borderRadius: 4,
                        },
                        {
                            label: 'Full Load (h)',
                            data: fullLoadHours,
                            backgroundColor: 'rgba(255, 152, 0, 0.75)',
                            borderRadius: 4,
                        }
                    ]
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
