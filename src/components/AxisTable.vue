<template>
  <v-card outlined>
    <v-card-title class="text-subtitle-1">Axis Travel</v-card-title>
    <v-card-text>
      <v-simple-table v-if="hasData" dense>
        <thead>
          <tr>
            <th>Axis</th>
            <th class="text-right">Distance</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.axis">
            <td>{{ row.axis }}</td>
            <td class="text-right font-weight-medium">{{ row.formatted }}</td>
          </tr>
        </tbody>
      </v-simple-table>
      <div v-else class="text-center grey--text py-8">
        No axis data yet
      </div>
    </v-card-text>
  </v-card>
</template>

<script>
export default {
    name: 'AxisTable',
    props: {
        axes: { type: Object, default: () => ({}) },
        filament: { type: Object, default: () => ({}) },
    },
    computed: {
        hasData() {
            return Object.keys(this.axes).length > 0 || Object.keys(this.filament).length > 0
        },
        rows() {
            const rows = []

            // Regular axes (X, Y, Z) — skip extruder axes (E*)
            for (const [axis, mm] of Object.entries(this.axes)) {
                if (axis.startsWith('E')) continue
                rows.push({ axis, formatted: this.formatDistance(mm) })
            }

            // Extruder axes (total travel including retracts)
            for (const [axis, mm] of Object.entries(this.axes)) {
                if (!axis.startsWith('E')) continue
                rows.push({ axis: `${axis} (total)`, formatted: this.formatDistance(mm) })
            }

            // Net filament
            for (const [ext, mm] of Object.entries(this.filament)) {
                rows.push({ axis: `${ext} (filament)`, formatted: this.formatDistance(mm) })
            }

            return rows
        }
    },
    methods: {
        formatDistance(mm) {
            if (mm >= 1000000) {
                return `${(mm / 1000000).toFixed(2)} km`
            }
            if (mm >= 1000) {
                return `${(mm / 1000).toFixed(2)} m`
            }
            return `${mm.toFixed(0)} mm`
        }
    }
}
</script>
