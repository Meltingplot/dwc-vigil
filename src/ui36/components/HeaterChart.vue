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
import { Chart, applyConfig, heaterChartConfig } from '../../core/charts'

export default {
    name: 'HeaterChart',
    props: {
        heaters: { type: Object, default: () => ({}) },
    },
    data() {
        return { chart: null }
    },
    computed: {
        hasData() { return Object.keys(this.heaters).length > 0 },
        config() { return heaterChartConfig(this.heaters) },
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
            if (this.chart) {
                applyConfig(this.chart, this.config)
                return
            }
            this.chart = new Chart(this.$refs.chart, this.config)
        }
    }
}
</script>
