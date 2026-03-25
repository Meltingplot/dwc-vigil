<template>
  <v-card style="border-radius: 8px; height: 100%">
    <v-card-title class="text-subtitle-2 pb-0">
      <v-icon small color="indigo" class="mr-2">mdi-chart-donut</v-icon>
      Job Outcomes
    </v-card-title>
    <v-card-text>
      <div v-if="hasData" style="position: relative; height: 200px">
        <canvas ref="chart" />
      </div>
      <div v-else class="d-flex flex-column align-center justify-center" style="height: 200px">
        <v-icon size="40" color="grey lighten-1">mdi-chart-donut</v-icon>
        <div class="text-caption grey--text mt-2">No job data yet</div>
      </div>
    </v-card-text>
  </v-card>
</template>

<script>
import Chart from 'chart.js'

export default {
    name: 'JobsPieChart',
    props: {
        successful: { type: Number, default: 0 },
        cancelled: { type: Number, default: 0 },
    },
    data() {
        return { chart: null }
    },
    computed: {
        hasData() { return this.successful > 0 || this.cancelled > 0 }
    },
    watch: {
        successful() { this.renderChart() },
        cancelled() { this.renderChart() },
        hasData(val) {
            if (val) {
                this.$nextTick(() => this.renderChart())
            }
        },
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

            if (this.chart) {
                this.chart.config.data.datasets[0].data = [this.successful, this.cancelled]
                this.chart.update()
                return
            }

            this.chart = new Chart(this.$refs.chart, {
                type: 'doughnut',
                data: {
                    labels: ['Successful', 'Cancelled'],
                    datasets: [{
                        data: [this.successful, this.cancelled],
                        backgroundColor: ['#4CAF50', '#EF5350'],
                        borderWidth: 0,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutoutPercentage: 65,
                    animation: { duration: 0 },
                    responsiveAnimationDuration: 0,
                    legend: {
                        position: 'bottom',
                        labels: { boxWidth: 12, padding: 16 }
                    }
                }
            })
        }
    }
}
</script>
