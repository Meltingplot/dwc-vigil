<template>
  <v-card outlined>
    <v-card-title class="text-subtitle-1">Fan Usage</v-card-title>
    <v-card-text>
      <Bar v-if="hasData" :data="chartData" :options="chartOptions" />
      <div v-else class="text-center grey--text py-8">
        No fan data yet
      </div>
    </v-card-text>
  </v-card>
</template>

<script>
import { Bar } from 'vue-chartjs'
import { Chart as ChartJS, BarElement, CategoryScale, LinearScale, Tooltip, Legend } from 'chart.js'

ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip, Legend)

export default {
    name: 'FanChart',
    components: { Bar },
    props: {
        fans: { type: Object, default: () => ({}) },
    },
    computed: {
        hasData() { return Object.keys(this.fans).length > 0 },
        chartData() {
            const labels = Object.keys(this.fans).map(k => `Fan ${k}`)
            return {
                labels,
                datasets: [{
                    label: 'On Time (h)',
                    data: Object.values(this.fans).map(f => (f.on_seconds || 0) / 3600),
                    backgroundColor: '#009688',
                }]
            }
        },
        chartOptions() {
            return {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                animation: false,
                plugins: {
                    legend: { position: 'bottom' }
                },
                scales: {
                    x: { title: { display: true, text: 'Hours' } }
                }
            }
        }
    }
}
</script>
