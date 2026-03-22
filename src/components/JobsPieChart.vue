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
export default {
    name: 'JobsPieChart',
    props: {
        successful: { type: Number, default: 0 },
        cancelled: { type: Number, default: 0 },
    },
    data() {
        return { chartInstance: null }
    },
    computed: {
        hasData() { return this.successful > 0 || this.cancelled > 0 }
    },
    watch: {
        successful() { this.renderChart() },
        cancelled() { this.renderChart() },
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
                // Chart.js is bundled with the plugin
                try {
                    await import('chart.js/auto')
                } catch {
                    // Chart.js not available
                    return
                }
            }
            this.renderChart()
        },
        renderChart() {
            if (!this.$refs.chart || !this.hasData || typeof window.Chart === 'undefined') return

            if (this.chartInstance) this.chartInstance.destroy()

            this.chartInstance = new window.Chart(this.$refs.chart, {
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
                    plugins: {
                        legend: { position: 'bottom' }
                    }
                }
            })
        }
    }
}
</script>
