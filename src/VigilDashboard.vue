<template>
  <v-container fluid class="vigil-dashboard pa-4">
    <!-- Page Header -->
    <div class="d-flex align-center mb-1">
      <v-icon large color="primary" class="mr-3">mdi-chart-box-outline</v-icon>
      <div>
        <div class="text-h5 font-weight-bold">Vigil</div>
        <div class="text-caption grey--text">Machine usage monitoring &amp; service tracking</div>
      </div>
      <v-spacer />
      <div class="d-flex align-center" style="gap: 8px">
        <export-button :loading="exporting" @export="handleExport" />
        <v-btn outlined small @click="openServiceLog">
          <v-icon left small>mdi-history</v-icon>
          Service Log
        </v-btn>
      </div>
    </div>

    <v-divider class="mb-4" />

    <!-- Counter tier tabs -->
    <counter-tabs v-model="activeTab" />

    <v-row v-if="statusData" class="mt-3">
      <!-- Key metrics -->
      <v-col cols="12">
        <v-row>
          <v-col v-for="card in statCards" :key="card.label" cols="6" sm="4" md>
            <stat-card
              :label="card.label"
              :value="card.value"
              :type="card.type"
              :icon="card.icon"
              :color="card.color"
            />
          </v-col>
        </v-row>
      </v-col>

      <!-- Jobs & Heaters section -->
      <v-col cols="12" md="5">
        <jobs-pie-chart
          :successful="currentTier.jobs_successful || 0"
          :cancelled="currentTier.jobs_cancelled || 0"
        />
      </v-col>
      <v-col cols="12" md="7">
        <heater-chart :heaters="currentTier.heaters || {}" />
      </v-col>

      <!-- Travel & Fans section -->
      <v-col cols="12" md="5">
        <axis-table
          :axes="currentTier.axes || {}"
          :filament="currentTier.filament_mm || {}"
        />
      </v-col>
      <v-col cols="12" md="7">
        <fan-chart :fans="currentTier.fans || {}" />
      </v-col>

      <!-- System vitals -->
      <v-col cols="12">
        <vitals-card
          :vitals="statusData.vitals || {}"
          :uptime="statusData.uptime || {}"
          :volume-free-bytes="statusData.volume_free_bytes"
        />
      </v-col>

      <!-- History -->
      <v-col cols="12">
        <history-chart
          :days="historyDays"
          :loading="loadingHistory"
        />
      </v-col>

      <!-- Service actions (only shown for service tier) -->
      <v-col v-if="activeTab === 1" cols="12">
        <v-card class="vigil-card">
          <v-card-text class="d-flex align-center" style="gap: 12px">
            <v-icon color="amber darken-1" class="mr-1">mdi-wrench-outline</v-icon>
            <span class="text-subtitle-2 font-weight-medium">Service Actions</span>
            <v-spacer />
            <v-btn color="warning" small @click="showResetDialog = true">
              <v-icon left small>mdi-restart</v-icon>
              Reset Counter
            </v-btn>
            <v-btn color="primary" small @click="showEventDialog = true">
              <v-icon left small>mdi-wrench</v-icon>
              Log Service Event
            </v-btn>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Loading state -->
    <div v-else class="text-center py-12">
      <v-progress-circular indeterminate size="48" color="primary" />
      <div class="mt-4 text-subtitle-2 grey--text">Loading Vigil data&hellip;</div>
    </div>

    <!-- Dialogs -->
    <service-reset-dialog
      v-model="showResetDialog"
      :service-data="statusData ? statusData.service : {}"
      :loading="resetting"
      @reset="handleReset"
    />

    <service-event-dialog
      v-model="showEventDialog"
      :loading="savingEvent"
      @submit="handleServiceEvent"
    />

    <service-log-dialog
      v-model="showLogDialog"
      :entries="serviceLogEntries"
      :loading="loadingLog"
    />

    <!-- Snackbar -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="4000">
      {{ snackbar.text }}
      <template #action="{ attrs }">
        <v-btn text v-bind="attrs" @click="snackbar.show = false">Close</v-btn>
      </template>
    </v-snackbar>
  </v-container>
</template>

<script>
import { mapState } from 'vuex'
import CounterTabs from './components/CounterTabs.vue'
import StatCard from './components/StatCard.vue'
import JobsPieChart from './components/JobsPieChart.vue'
import HeaterChart from './components/HeaterChart.vue'
import FanChart from './components/FanChart.vue'
import AxisTable from './components/AxisTable.vue'
import VitalsCard from './components/VitalsCard.vue'
import HistoryChart from './components/HistoryChart.vue'
import ExportButton from './components/ExportButton.vue'
import ServiceResetDialog from './components/ServiceResetDialog.vue'
import ServiceEventDialog from './components/ServiceEventDialog.vue'
import ServiceLogDialog from './components/ServiceLogDialog.vue'

const TIER_KEYS = ['lifetime', 'service', 'session']
const POLL_INTERVAL = 5000
const API_BASE = '/machine/Vigil'

export default {
    name: 'VigilDashboard',
    components: {
        CounterTabs, StatCard, JobsPieChart, HeaterChart, FanChart,
        AxisTable, VitalsCard, HistoryChart, ExportButton,
        ServiceResetDialog, ServiceEventDialog, ServiceLogDialog,
    },
    data() {
        return {
            activeTab: 0,
            statusData: null,
            historyDays: [],
            serviceLogEntries: [],

            // Loading states
            loadingHistory: false,
            loadingLog: false,
            exporting: false,
            resetting: false,
            savingEvent: false,

            // Dialogs
            showResetDialog: false,
            showEventDialog: false,
            showLogDialog: false,

            // Snackbar
            snackbar: { show: false, text: '', color: 'success' },

            // Polling
            pollTimer: null,
            historyLoaded: false,
        }
    },
    computed: {
        ...mapState('machine/model', {
            pluginData: state => {
                const plugins = state.plugins
                if (plugins instanceof Map) return plugins.get('Vigil')?.data ?? {}
                return plugins?.Vigil?.data ?? {}
            }
        }),
        currentTier() {
            if (!this.statusData) return {}
            return this.statusData[TIER_KEYS[this.activeTab]] || {}
        },
        statCards() {
            const t = this.currentTier
            return [
                { label: 'Machine Time', value: t.machine_seconds || 0, type: 'time', icon: 'mdi-power', color: 'blue' },
                { label: 'Print Time', value: t.print_seconds || 0, type: 'time', icon: 'mdi-printer-3d', color: 'green' },
                { label: 'Pause Time', value: t.pause_seconds || 0, type: 'time', icon: 'mdi-pause-circle-outline', color: 'orange' },
                { label: 'Warmup', value: t.warmup_seconds || 0, type: 'time', icon: 'mdi-thermometer-chevron-up', color: 'deep-orange' },
                { label: 'Jobs', value: t.jobs_total || 0, type: 'number', icon: 'mdi-format-list-numbered', color: 'indigo' },
                { label: 'Successful', value: t.jobs_successful || 0, type: 'number', icon: 'mdi-check-circle-outline', color: 'green' },
                { label: 'Cancelled', value: t.jobs_cancelled || 0, type: 'number', icon: 'mdi-close-circle-outline', color: 'red' },
            ]
        },
    },
    watch: {
        activeTab() {
            if (!this.historyLoaded) {
                this.loadHistory()
            }
        }
    },
    mounted() {
        this.loadStatus()
        this.pollTimer = setInterval(() => this.loadStatus(), POLL_INTERVAL)
    },
    beforeDestroy() {
        if (this.pollTimer) clearInterval(this.pollTimer)
    },
    methods: {
        // --- API helpers ---
        async apiGet(endpoint) {
            const resp = await fetch(`${API_BASE}/${endpoint}`)
            if (!resp.ok) {
                const body = await resp.json().catch(() => ({}))
                throw new Error(body.error || resp.statusText || 'Request failed')
            }
            return resp.json()
        },
        async apiPost(endpoint, data = {}) {
            const resp = await fetch(`${API_BASE}/${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            })
            if (!resp.ok) {
                const body = await resp.json().catch(() => ({}))
                throw new Error(body.error || resp.statusText || 'Request failed')
            }
            return resp.json()
        },

        // --- Data loading ---
        async loadStatus() {
            try {
                this.statusData = await this.apiGet('status')
                if (!this.historyLoaded) {
                    this.loadHistory()
                }
            } catch {
                // Non-critical: silent fail, keep previous data
            }
        },
        async loadHistory() {
            this.loadingHistory = true
            try {
                const result = await this.apiGet('history?days=30')
                this.historyDays = result.days || []
                this.historyLoaded = true
            } catch {
                // Non-critical
            } finally {
                this.loadingHistory = false
            }
        },

        // --- Actions ---
        async handleExport(format) {
            this.exporting = true
            try {
                if (format === 'csv') {
                    const resp = await fetch(`${API_BASE}/export?format=csv`)
                    const blob = await resp.blob()
                    this.downloadBlob(blob, 'vigil_export.csv')
                } else {
                    const data = await this.apiGet('export?format=json')
                    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
                    this.downloadBlob(blob, 'vigil_export.json')
                }
                this.notify('Export complete', 'success')
            } catch (e) {
                this.notify(`Export failed: ${e.message}`, 'error')
            } finally {
                this.exporting = false
            }
        },

        async handleReset(resetData) {
            this.resetting = true
            try {
                await this.apiPost('service/reset', resetData)
                this.showResetDialog = false
                this.notify('Counter reset successful', 'success')
                await this.loadStatus()
            } catch (e) {
                this.notify(`Reset failed: ${e.message}`, 'error')
            } finally {
                this.resetting = false
            }
        },

        async handleServiceEvent(eventData) {
            this.savingEvent = true
            try {
                await this.apiPost('service/event', eventData)
                this.showEventDialog = false
                this.notify('Service event logged', 'success')
            } catch (e) {
                this.notify(`Failed to log event: ${e.message}`, 'error')
            } finally {
                this.savingEvent = false
            }
        },

        async openServiceLog() {
            this.showLogDialog = true
            this.loadingLog = true
            try {
                const result = await this.apiGet('service/log')
                this.serviceLogEntries = result.log || []
            } catch (e) {
                this.notify(`Failed to load service log: ${e.message}`, 'error')
            } finally {
                this.loadingLog = false
            }
        },

        // --- Helpers ---
        downloadBlob(blob, filename) {
            const url = URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            a.download = filename
            a.click()
            URL.revokeObjectURL(url)
        },
        notify(text, color = 'success') {
            this.snackbar = { show: true, text, color }
        },
    },
}
</script>

<style scoped>
.vigil-dashboard .vigil-card {
    border-radius: 8px;
}
</style>
