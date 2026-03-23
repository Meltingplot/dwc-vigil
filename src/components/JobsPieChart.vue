<template>
  <v-card outlined>
    <v-card-title class="text-subtitle-1">Jobs</v-card-title>
    <v-card-text>
      <canvas ref="chart" height="200" />
      <div v-if="!hasData" class="text-center grey--text py-8">
        No job data yet
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
                        backgroundColor: ['#4CAF50', '#F44336'],
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: { duration: 0 },
                    responsiveAnimationDuration: 0,
                    legend: { position: 'bottom' }
                }
            })
        }
    }
}
</script>
