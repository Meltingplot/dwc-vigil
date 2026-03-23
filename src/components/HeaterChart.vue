<template>
  <v-card outlined>
    <v-card-title class="text-subtitle-1">Heater Usage</v-card-title>
    <v-card-text>
      <Bar v-if="hasData" :data="chartData" :options="chartOptions" />
      <div v-else class="text-center grey--text py-8">
        No heater data yet
      </div>
    </v-card-text>
  </v-card>
</template>

<script>
import { Bar } from 'vue-chartjs'
import { Chart as ChartJS, BarElement, CategoryScale, LinearScale, Tooltip, Legend } from 'chart.js'

ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip, Legend)

export default {
    name: 'HeaterChart',
    components: { Bar },
    props: {
        heaters: { type: Object, default: () => ({}) },
    },
    computed: {
        hasData() { return Object.keys(this.heaters).length > 0 },
        chartData() {
            const labels = Object.keys(this.heaters).map(k => `Heater ${k}`)
            return {
                labels,
                datasets: [
                    {
                        label: 'On Time (h)',
                        data: Object.values(this.heaters).map(h => (h.on_seconds || 0) / 3600),
                        backgroundColor: '#2196F3',
                    },
                    {
                        label: 'Full Load (h)',
                        data: Object.values(this.heaters).map(h => (h.full_load_seconds || 0) / 3600),
                        backgroundColor: '#FF9800',
                    }
                ]
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
