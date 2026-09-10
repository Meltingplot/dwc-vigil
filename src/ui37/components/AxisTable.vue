<template>
  <v-card style="border-radius: 8px; height: 100%">
    <v-card-title class="text-subtitle-2 pb-0">
      <v-icon size="small" color="purple" class="mr-2">mdi-axis-arrow</v-icon>
      Axis Travel
    </v-card-title>
    <v-card-text>
      <v-table v-if="hasData" density="compact" class="vigil-table">
        <thead>
          <tr>
            <th>Axis</th>
            <th class="text-right">Distance</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.axis">
            <td>
              <v-icon size="x-small" class="mr-1" :color="row.isExtruder ? 'amber-darken-1' : 'grey'">
                {{ row.isExtruder ? 'mdi-printer-3d-nozzle-outline' : 'mdi-arrow-all' }}
              </v-icon>
              {{ row.axis }}
            </td>
            <td class="text-right font-weight-medium">{{ row.formatted }}</td>
          </tr>
        </tbody>
      </v-table>
      <div v-else class="d-flex flex-column align-center justify-center" style="min-height: 160px">
        <v-icon size="40" color="grey-lighten-1">mdi-axis-arrow</v-icon>
        <div class="text-caption text-medium-emphasis mt-2">No axis data yet</div>
      </div>
    </v-card-text>
  </v-card>
</template>

<script>
import { formatDistance } from '../../core/format'

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

            for (const [axis, mm] of Object.entries(this.axes)) {
                if (axis.startsWith('E')) continue
                rows.push({ axis, formatted: formatDistance(mm), isExtruder: false })
            }

            for (const [axis, mm] of Object.entries(this.axes)) {
                if (!axis.startsWith('E')) continue
                rows.push({ axis: `${axis} (total)`, formatted: formatDistance(mm), isExtruder: true })
            }

            for (const [ext, mm] of Object.entries(this.filament)) {
                rows.push({ axis: `${ext} (filament)`, formatted: formatDistance(mm), isExtruder: true })
            }

            return rows
        }
    },
}
</script>
