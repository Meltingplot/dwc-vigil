<template>
  <v-dialog v-model="visible" max-width="500" persistent>
    <v-card>
      <v-card-title>Reset Service Counter</v-card-title>
      <v-card-text>
        <v-select
          v-model="scope"
          :items="scopes"
          label="Scope"
          outlined
          dense
        />

        <div v-if="availableKeys.length > 0" class="mb-4">
          <div class="text-caption mb-1">Select counters to reset:</div>
          <v-checkbox
            v-for="key in availableKeys"
            :key="key"
            v-model="selectedKeys"
            :label="key"
            :value="key"
            dense
            hide-details
            class="mt-0"
          />
        </div>

        <v-select
          v-model="component"
          :items="components"
          label="Component (optional)"
          outlined
          dense
          clearable
        />

        <v-textarea
          v-model="description"
          label="Reason (required)"
          outlined
          dense
          rows="2"
          :rules="[v => (v && v.length >= 3) || 'Min. 3 characters']"
        />

        <v-alert v-if="scope && currentValues" type="warning" dense text class="mt-2">
          Current values will be reset to 0
        </v-alert>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn text @click="close">Cancel</v-btn>
        <v-btn
          color="warning"
          :disabled="!isValid"
          :loading="loading"
          @click="submit"
        >
          Reset
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
export default {
    name: 'ServiceResetDialog',
    props: {
        value: { type: Boolean, default: false },
        serviceData: { type: Object, default: () => ({}) },
        loading: { type: Boolean, default: false },
    },
    data() {
        return {
            scope: '',
            selectedKeys: [],
            component: '',
            description: '',
            scopes: [
                { text: 'Machine Time', value: 'machine_time' },
                { text: 'Print Time', value: 'print_time' },
                { text: 'Pause Time', value: 'pause_time' },
                { text: 'Warmup Time', value: 'warmup_time' },
                { text: 'Jobs', value: 'jobs' },
                { text: 'Axes', value: 'axes' },
                { text: 'Extruders', value: 'extruders' },
                { text: 'Filament', value: 'filament' },
                { text: 'Heaters', value: 'heaters' },
                { text: 'Fans', value: 'fans' },
            ],
            components: [
                { text: 'Nozzle', value: 'nozzle' },
                { text: 'Extruder', value: 'extruder' },
                { text: 'Hotend Fan', value: 'fan_hotend' },
                { text: 'Heater (Bed)', value: 'heater_bed' },
                { text: 'Belt X', value: 'belt_x' },
                { text: 'Belt Y', value: 'belt_y' },
                { text: 'Mainboard', value: 'mainboard' },
                { text: 'Other', value: 'other' },
            ],
        }
    },
    computed: {
        visible: {
            get() { return this.value },
            set(val) { this.$emit('input', val) }
        },
        availableKeys() {
            if (!this.scope || !this.serviceData) return []
            if (this.scope === 'axes') {
                return Object.keys(this.serviceData.axes || {}).filter(k => !k.startsWith('E'))
            }
            if (this.scope === 'extruders') {
                return Object.keys(this.serviceData.axes || {}).filter(k => k.startsWith('E'))
            }
            if (this.scope === 'filament') {
                return Object.keys(this.serviceData.filament_mm || {})
            }
            if (this.scope === 'heaters') {
                return Object.keys(this.serviceData.heaters || {})
            }
            if (this.scope === 'fans') {
                return Object.keys(this.serviceData.fans || {})
            }
            return []
        },
        currentValues() {
            return this.scope && this.serviceData
        },
        isValid() {
            return this.scope && this.description && this.description.length >= 3
        }
    },
    watch: {
        scope() {
            this.selectedKeys = []
        }
    },
    methods: {
        submit() {
            this.$emit('reset', {
                scope: this.scope,
                keys: this.selectedKeys.length > 0 ? this.selectedKeys : null,
                description: this.description,
                component: this.component || null,
            })
        },
        close() {
            this.scope = ''
            this.selectedKeys = []
            this.component = ''
            this.description = ''
            this.visible = false
        }
    }
}
</script>
