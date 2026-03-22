<template>
  <v-card outlined class="stat-card">
    <v-card-text class="text-center pa-3">
      <div class="text-caption grey--text">{{ label }}</div>
      <div class="text-h5 font-weight-bold mt-1">{{ formattedValue }}</div>
      <div v-if="subtitle" class="text-caption grey--text mt-1">{{ subtitle }}</div>
    </v-card-text>
  </v-card>
</template>

<script>
export default {
    name: 'StatCard',
    props: {
        label: { type: String, required: true },
        value: { type: Number, default: 0 },
        type: { type: String, default: 'number' }, // 'time', 'number'
        subtitle: { type: String, default: '' },
    },
    computed: {
        formattedValue() {
            if (this.type === 'time') {
                return this.formatDuration(this.value)
            }
            return this.value.toLocaleString()
        }
    },
    methods: {
        formatDuration(seconds) {
            const days = Math.floor(seconds / 86400)
            const hours = Math.floor((seconds % 86400) / 3600)
            const minutes = Math.floor((seconds % 3600) / 60)

            const parts = []
            if (days > 0) parts.push(`${days}d`)
            if (hours > 0 || days > 0) parts.push(`${hours}h`)
            parts.push(`${minutes}m`)
            return parts.join(' ')
        }
    }
}
</script>
