<template>
  <v-card outlined>
    <v-card-title class="text-subtitle-1">System Vitals</v-card-title>
    <v-card-text v-if="hasData">
      <v-simple-table dense>
        <tbody>
          <!-- Board vitals -->
          <tr v-if="hasMcuTemp">
            <td class="text-caption grey--text" style="width: 140px">MCU Temp</td>
            <td class="font-weight-medium">{{ formatTemp(vitals.mcu_temp_min) }} – {{ formatTemp(vitals.mcu_temp_max) }}</td>
          </tr>
          <tr v-if="hasVin">
            <td class="text-caption grey--text">Input Voltage</td>
            <td class="font-weight-medium">{{ formatVoltage(vitals.vin_min) }} – {{ formatVoltage(vitals.vin_max) }}</td>
          </tr>
          <tr v-if="hasV12">
            <td class="text-caption grey--text">12V Rail</td>
            <td class="font-weight-medium">{{ formatVoltage(vitals.v12_min) }} – {{ formatVoltage(vitals.v12_max) }}</td>
          </tr>

          <!-- SBC vitals -->
          <tr v-if="vitals.sbc_cpu_temp_max != null">
            <td class="text-caption grey--text">SBC CPU Temp</td>
            <td class="font-weight-medium">{{ formatTemp(vitals.sbc_cpu_temp_max) }} (max)</td>
          </tr>
          <tr v-if="sbcCpuLoadAvg != null">
            <td class="text-caption grey--text">SBC CPU Load</td>
            <td class="font-weight-medium">{{ sbcCpuLoadAvg }}%</td>
          </tr>
          <tr v-if="vitals.sbc_memory_min_bytes != null">
            <td class="text-caption grey--text">SBC Memory (min free)</td>
            <td class="font-weight-medium">{{ formatBytes(vitals.sbc_memory_min_bytes) }}</td>
          </tr>

          <!-- Uptime & reboots -->
          <tr v-if="uptime.firmware_uptime_secs != null">
            <td class="text-caption grey--text">Firmware Uptime</td>
            <td class="font-weight-medium">{{ formatDuration(uptime.firmware_uptime_secs) }}</td>
          </tr>
          <tr v-if="uptime.sbc_uptime_secs != null">
            <td class="text-caption grey--text">SBC Uptime</td>
            <td class="font-weight-medium">{{ formatDuration(uptime.sbc_uptime_secs) }}</td>
          </tr>
          <tr v-if="uptime.firmware_reboots > 0">
            <td class="text-caption grey--text">Firmware Reboots</td>
            <td class="font-weight-medium">{{ uptime.firmware_reboots }}</td>
          </tr>
          <tr v-if="uptime.sbc_reboots > 0">
            <td class="text-caption grey--text">SBC Reboots</td>
            <td class="font-weight-medium">{{ uptime.sbc_reboots }}</td>
          </tr>

          <!-- Volume -->
          <tr v-if="volumeFreeBytes != null">
            <td class="text-caption grey--text">Disk Free</td>
            <td class="font-weight-medium">{{ formatBytes(volumeFreeBytes) }}</td>
          </tr>
        </tbody>
      </v-simple-table>
    </v-card-text>
    <v-card-text v-else class="text-center grey--text py-8">
      No vitals data yet
    </v-card-text>
  </v-card>
</template>

<script>
export default {
    name: 'VitalsCard',
    props: {
        vitals: { type: Object, default: () => ({}) },
        uptime: { type: Object, default: () => ({}) },
        volumeFreeBytes: { type: Number, default: null },
    },
    computed: {
        hasMcuTemp() {
            return this.vitals.mcu_temp_min != null || this.vitals.mcu_temp_max != null
        },
        hasVin() {
            return this.vitals.vin_min != null || this.vitals.vin_max != null
        },
        hasV12() {
            return this.vitals.v12_min != null || this.vitals.v12_max != null
        },
        sbcCpuLoadAvg() {
            const count = this.vitals.sbc_cpu_load_avg_count
            if (!count || count === 0) return null
            return (this.vitals.sbc_cpu_load_avg_sum / count * 100).toFixed(1)
        },
        hasData() {
            return this.hasMcuTemp || this.hasVin || this.hasV12
                || this.vitals.sbc_cpu_temp_max != null
                || this.sbcCpuLoadAvg != null
                || this.vitals.sbc_memory_min_bytes != null
                || this.uptime.firmware_uptime_secs != null
                || this.uptime.sbc_uptime_secs != null
                || this.volumeFreeBytes != null
        },
    },
    methods: {
        formatTemp(val) {
            if (val == null) return '—'
            return `${val.toFixed(1)} °C`
        },
        formatVoltage(val) {
            if (val == null) return '—'
            return `${val.toFixed(2)} V`
        },
        formatBytes(bytes) {
            if (bytes == null) return '—'
            if (bytes >= 1073741824) return `${(bytes / 1073741824).toFixed(1)} GB`
            if (bytes >= 1048576) return `${(bytes / 1048576).toFixed(0)} MB`
            return `${(bytes / 1024).toFixed(0)} KB`
        },
        formatDuration(seconds) {
            if (seconds == null) return '—'
            const days = Math.floor(seconds / 86400)
            const hours = Math.floor((seconds % 86400) / 3600)
            const minutes = Math.floor((seconds % 3600) / 60)
            const parts = []
            if (days > 0) parts.push(`${days}d`)
            if (hours > 0 || days > 0) parts.push(`${hours}h`)
            parts.push(`${minutes}m`)
            return parts.join(' ')
        },
    }
}
</script>
