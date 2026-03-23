<template>
  <v-card outlined>
    <v-card-title class="text-subtitle-1">Jobs</v-card-title>
    <v-card-text>
      <Doughnut v-if="hasData" :data="chartData" :options="chartOptions" />
      <div v-else class="text-center grey--text py-8">
        No job data yet
      </div>
    </v-card-text>
  </v-card>
</template>

<script>
import { Doughnut } from 'vue-chartjs'
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js'

ChartJS.register(ArcElement, Tooltip, Legend)

export default {
    name: 'JobsPieChart',
    components: { Doughnut },
    props: {
        successful: { type: Number, default: 0 },
        cancelled: { type: Number, default: 0 },
    },
    computed: {
        hasData() { return this.successful > 0 || this.cancelled > 0 },
        chartData() {
            return {
                labels: ['Successful', 'Cancelled'],
                datasets: [{
                    data: [this.successful, this.cancelled],
                    backgroundColor: ['#4CAF50', '#F44336'],
                }]
            }
        },
        chartOptions() {
            return {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                plugins: {
                    legend: { position: 'bottom' }
                }
            }
        }
    }
}
</script>
