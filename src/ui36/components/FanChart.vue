<template>
  <v-card style="border-radius: 8px; height: 100%">
    <v-card-title class="text-subtitle-2 pb-0">
      <v-icon small color="teal" class="mr-2">mdi-fan</v-icon>
      Fan Usage
    </v-card-title>
    <v-card-text>
      <div v-if="hasData" style="position: relative; height: 200px">
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
import { Chart, applyConfig, fanChartConfig } from '../../core/charts'

export default {
    name: 'FanChart',
    props: {
        fans: { type: Object, default: () => ({}) },
    },
    data() {
        return { chart: null }
    },
    computed: {
        hasData() { return Object.keys(this.fans).length > 0 },
        config() { return fanChartConfig(this.fans) },
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
            if (this.chart) {
                applyConfig(this.chart, this.config)
                return
            }
            this.chart = new Chart(this.$refs.chart, this.config)
        }
    }
}
</script>
