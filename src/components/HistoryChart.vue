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
        style="max-width: 180px"
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
export default {
    name: 'HistoryChart',
    props: {
        days: { type: Array, default: () => [] },
        loading: { type: Boolean, default: false },
    },
    data() {
        return {
            metric: 'print_hours',
            metrics: [
                { text: 'Print Hours', value: 'print_hours' },
                { text: 'Machine Hours', value: 'machine_hours' },
                { text: 'Jobs', value: 'jobs_total' },
            ],
            chartInstance: null,
        }
    },
    computed: {
        hasData() { return this.days.length > 0 }
    },
    watch: {
        days() { this.renderChart() },
        metric() { this.renderChart() },
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

            if (this.chartInstance) this.chartInstance.destroy()

            const labels = this.days.map(d => d.date)
            const data = this.days.map(d => d[this.metric] || 0)
            const selected = this.metrics.find(m => m.value === this.metric)
            const label = selected ? selected.text : this.metric

            this.chartInstance = new window.Chart(this.$refs.chart, {
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
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        x: {
                            ticks: {
                                maxRotation: 45,
                                maxTicksLimit: 15,
                            }
                        },
                        y: {
                            beginAtZero: true,
                            title: { display: true, text: label }
                        }
                    }
                }
            })
        }
    }
}
</script>
