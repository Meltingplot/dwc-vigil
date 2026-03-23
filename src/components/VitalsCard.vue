<template>
  <v-card style="border-radius: 8px">
    <v-card-title class="text-subtitle-2 pb-0">
      <v-icon small color="red darken-1" class="mr-2">mdi-heart-pulse</v-icon>
      System Vitals
    </v-card-title>
    <v-card-text v-if="hasData">
      <v-row>
        <!-- Board vitals column -->
        <v-col cols="12" sm="6" md="4">
          <div class="text-overline grey--text mb-2">Board</div>
          <div v-if="hasMcuTemp" class="vitals-row">
            <v-icon x-small color="grey" class="mr-2">mdi-thermometer</v-icon>
            <span class="text-caption grey--text">MCU Temp</span>
            <v-spacer />
            <span class="text-body-2 font-weight-medium">{{ formatTemp(vitals.mcu_temp_min) }} – {{ formatTemp(vitals.mcu_temp_max) }}</span>
          </div>
          <div v-if="hasVin" class="vitals-row">
            <v-icon x-small color="grey" class="mr-2">mdi-flash</v-icon>
            <span class="text-caption grey--text">Input Voltage</span>
            <v-spacer />
            <span class="text-body-2 font-weight-medium">{{ formatVoltage(vitals.vin_min) }} – {{ formatVoltage(vitals.vin_max) }}</span>
          </div>
          <div v-if="hasV12" class="vitals-row">
            <v-icon x-small color="grey" class="mr-2">mdi-flash-outline</v-icon>
            <span class="text-caption grey--text">12V Rail</span>
            <v-spacer />
            <span class="text-body-2 font-weight-medium">{{ formatVoltage(vitals.v12_min) }} – {{ formatVoltage(vitals.v12_max) }}</span>
          </div>
        </v-col>

        <!-- SBC vitals column -->
        <v-col cols="12" sm="6" md="4">
          <div class="text-overline grey--text mb-2">SBC</div>
          <div v-if="vitals.sbc_cpu_temp_max != null" class="vitals-row">
            <v-icon x-small color="grey" class="mr-2">mdi-thermometer</v-icon>
            <span class="text-caption grey--text">CPU Temp</span>
            <v-spacer />
            <span class="text-body-2 font-weight-medium">{{ formatTemp(vitals.sbc_cpu_temp_max) }} <span class="text-caption grey--text">(max)</span></span>
          </div>
          <div v-if="sbcCpuLoadAvg != null" class="vitals-row">
            <v-icon x-small color="grey" class="mr-2">mdi-cpu-64-bit</v-icon>
            <span class="text-caption grey--text">CPU Load</span>
            <v-spacer />
            <span class="text-body-2 font-weight-medium">{{ sbcCpuLoadAvg }}%</span>
          </div>
          <div v-if="vitals.sbc_memory_min_bytes != null" class="vitals-row">
            <v-icon x-small color="grey" class="mr-2">mdi-memory</v-icon>
            <span class="text-caption grey--text">Memory (min free)</span>
            <v-spacer />
            <span class="text-body-2 font-weight-medium">{{ formatBytes(vitals.sbc_memory_min_bytes) }}</span>
          </div>
        </v-col>

        <!-- Uptime & system column -->
        <v-col cols="12" sm="6" md="4">
          <div class="text-overline grey--text mb-2">Uptime</div>
          <div v-if="uptime.firmware_uptime_secs != null" class="vitals-row">
            <v-icon x-small color="grey" class="mr-2">mdi-chip</v-icon>
            <span class="text-caption grey--text">Firmware</span>
            <v-spacer />
            <span class="text-body-2 font-weight-medium">{{ formatDuration(uptime.firmware_uptime_secs) }}</span>
          </div>
          <div v-if="uptime.sbc_uptime_secs != null" class="vitals-row">
            <v-icon x-small color="grey" class="mr-2">mdi-desktop-classic</v-icon>
            <span class="text-caption grey--text">SBC</span>
            <v-spacer />
            <span class="text-body-2 font-weight-medium">{{ formatDuration(uptime.sbc_uptime_secs) }}</span>
          </div>
          <div v-if="uptime.firmware_reboots > 0" class="vitals-row">
            <v-icon x-small color="amber darken-1" class="mr-2">mdi-restart</v-icon>
            <span class="text-caption grey--text">FW Reboots</span>
            <v-spacer />
            <span class="text-body-2 font-weight-medium">{{ uptime.firmware_reboots }}</span>
          </div>
          <div v-if="uptime.sbc_reboots > 0" class="vitals-row">
            <v-icon x-small color="amber darken-1" class="mr-2">mdi-restart</v-icon>
            <span class="text-caption grey--text">SBC Reboots</span>
            <v-spacer />
            <span class="text-body-2 font-weight-medium">{{ uptime.sbc_reboots }}</span>
          </div>
          <div v-if="volumeFreeBytes != null" class="vitals-row">
            <v-icon x-small color="grey" class="mr-2">mdi-harddisk</v-icon>
            <span class="text-caption grey--text">Disk Free</span>
            <v-spacer />
            <span class="text-body-2 font-weight-medium">{{ formatBytes(volumeFreeBytes) }}</span>
          </div>
        </v-col>
      </v-row>
    </v-card-text>
    <v-card-text v-else class="d-flex flex-column align-center justify-center" style="min-height: 120px">
      <v-icon size="40" color="grey lighten-1">mdi-heart-pulse</v-icon>
      <div class="text-caption grey--text mt-2">No vitals data yet</div>
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
            return Math.min(100, Math.max(0, this.vitals.sbc_cpu_load_avg_sum / count * 100)).toFixed(1)
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
            if (val == null) return '\u2014'
            return `${val.toFixed(1)} \u00B0C`
        },
        formatVoltage(val) {
            if (val == null) return '\u2014'
            return `${val.toFixed(2)} V`
        },
        formatBytes(bytes) {
            if (bytes == null) return '\u2014'
            if (bytes >= 1073741824) return `${(bytes / 1073741824).toFixed(1)} GB`
            if (bytes >= 1048576) return `${(bytes / 1048576).toFixed(0)} MB`
            return `${(bytes / 1024).toFixed(0)} KB`
        },
        formatDuration(seconds) {
            if (seconds == null) return '\u2014'
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

<style scoped>
.vitals-row {
    display: flex;
    align-items: center;
    padding: 4px 0;
    border-bottom: 1px solid rgba(0, 0, 0, 0.04);
}
.vitals-row:last-child {
    border-bottom: none;
}
</style>
