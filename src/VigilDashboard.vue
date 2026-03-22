<template>
  <v-container fluid>
    <!-- Counter tier tabs -->
    <counter-tabs v-model="activeTab" />

    <v-row v-if="statusData" class="mt-2">
      <!-- Row 1: Key metrics -->
      <v-col cols="12">
        <v-row>
          <v-col v-for="card in statCards" :key="card.label" cols="12" sm="6" md>
            <stat-card
              :label="card.label"
              :value="card.value"
              :type="card.type"
            />
          </v-col>
        </v-row>
      </v-col>

      <!-- Row 2: Charts -->
      <v-col cols="12" md="5">
        <jobs-pie-chart
          :successful="currentTier.jobs_successful || 0"
          :cancelled="currentTier.jobs_cancelled || 0"
        />
      </v-col>
      <v-col cols="12" md="7">
        <heater-chart :heaters="currentTier.heaters || {}" />
      </v-col>

      <!-- Row 3: Details -->
      <v-col cols="12" md="5">
        <axis-table
          :axes="currentTier.axes || {}"
          :filament="currentTier.filament_mm || {}"
        />
      </v-col>
      <v-col cols="12" md="7">
        <history-chart
          :days="historyDays"
          :loading="loadingHistory"
        />
      </v-col>

      <!-- Row 4: Actions -->
      <v-col cols="12">
        <div class="d-flex flex-wrap align-center" style="gap: 8px">
          <export-button :loading="exporting" @export="handleExport" />

          <template v-if="activeTab === 1">
            <v-btn outlined color="warning" @click="showResetDialog = true">
              <v-icon left>mdi-restart</v-icon>
              Reset Counter
            </v-btn>
            <v-btn outlined color="primary" @click="showEventDialog = true">
              <v-icon left>mdi-wrench</v-icon>
              Log Service Event
            </v-btn>
          </template>

          <v-btn outlined @click="openServiceLog">
            <v-icon left>mdi-history</v-icon>
            Service Log
          </v-btn>
        </div>
      </v-col>
    </v-row>

    <!-- Loading state -->
    <div v-else class="text-center py-12">
      <v-progress-circular indeterminate size="48" />
      <div class="mt-4 grey--text">Loading Vigil data...</div>
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
import AxisTable from './components/AxisTable.vue'
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
        CounterTabs, StatCard, JobsPieChart, HeaterChart,
        AxisTable, HistoryChart, ExportButton,
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
                { label: 'Machine Hours', value: t.machine_seconds || 0, type: 'time' },
                { label: 'Print Hours', value: t.print_seconds || 0, type: 'time' },
                { label: 'Jobs Total', value: t.jobs_total || 0, type: 'number' },
                { label: 'Successful', value: t.jobs_successful || 0, type: 'number' },
                { label: 'Cancelled', value: t.jobs_cancelled || 0, type: 'number' },
            ]
        },
    },
    mounted() {
        this.loadStatus()
        this.pollTimer = setInterval(() => this.loadStatus(), POLL_INTERVAL)
    },
    beforeDestroy() {
        if (this.pollTimer) clearInterval(this.pollTimer)
    },
    watch: {
        activeTab(newTab) {
            // Lazy-load history when first switching away from lifetime tab
            if (!this.historyLoaded) {
                this.loadHistory()
            }
        }
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
                // Load history on first successful status
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
