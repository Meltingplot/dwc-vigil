<template>
  <v-card class="stat-card" style="border-radius: 8px; overflow: hidden">
    <div class="stat-card__accent" :style="{ backgroundColor: accentColor }" />
    <v-card-text class="text-center pa-3 pt-4">
      <v-icon :color="color" class="mb-1" size="28">{{ icon }}</v-icon>
      <div class="text-h5 font-weight-bold mt-1">{{ formattedValue }}</div>
      <div class="text-caption grey--text mt-1">{{ label }}</div>
    </v-card-text>
  </v-card>
</template>

<script>
const COLOR_MAP = {
    blue: '#1976D2',
    green: '#4CAF50',
    orange: '#FB8C00',
    'deep-orange': '#F4511E',
    indigo: '#3F51B5',
    red: '#F44336',
}

export default {
    name: 'StatCard',
    props: {
        label: { type: String, required: true },
        value: { type: Number, default: 0 },
        type: { type: String, default: 'number' },
        icon: { type: String, default: 'mdi-chart-bar' },
        color: { type: String, default: 'blue' },
    },
    computed: {
        formattedValue() {
            if (this.type === 'time') {
                return this.formatDuration(this.value)
            }
            return this.value.toLocaleString()
        },
        accentColor() {
            return COLOR_MAP[this.color] || COLOR_MAP.blue
        },
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

<style scoped>
.stat-card {
    position: relative;
    transition: box-shadow 0.2s ease;
}
.stat-card:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1) !important;
}
.stat-card__accent {
    height: 3px;
    width: 100%;
}
</style>
