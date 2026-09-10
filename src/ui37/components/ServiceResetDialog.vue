<template>
  <v-dialog v-model="visible" max-width="500" persistent>
    <v-card style="border-radius: 8px">
      <v-card-title class="d-flex align-center">
        <v-icon color="warning" class="mr-2">mdi-restart</v-icon>
        Reset Service Counter
      </v-card-title>
      <v-divider />
      <v-card-text class="pt-4">
        <v-select
          v-model="scope"
          :items="scopes"
          label="Scope"
          variant="outlined"
          density="compact"
          prepend-inner-icon="mdi-target"
        />

        <div v-if="availableKeys.length > 0" class="mb-4">
          <div class="text-caption font-weight-medium mb-2">Select counters to reset:</div>
          <v-checkbox
            v-for="key in availableKeys"
            :key="key"
            v-model="selectedKeys"
            :label="key"
            :value="key"
            density="compact"
            hide-details
            class="mt-0"
          />
        </div>

        <v-select
          v-model="component"
          :items="components"
          label="Component (optional)"
          variant="outlined"
          density="compact"
          clearable
          prepend-inner-icon="mdi-cog-outline"
        />

        <v-textarea
          v-model="description"
          label="Reason"
          placeholder="Why are you resetting this counter?"
          variant="outlined"
          density="compact"
          rows="2"
          prepend-inner-icon="mdi-text"
          :rules="[v => (v && v.length >= 3) || 'Min. 3 characters']"
        />

        <v-alert v-if="scope" type="warning" density="compact" variant="tonal" class="mb-0">
          Selected counter values will be reset to zero.
        </v-alert>
      </v-card-text>
      <v-divider />
      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn variant="text" @click="close">Cancel</v-btn>
        <v-btn
          color="warning"
          :disabled="!isValid"
          :loading="loading"
          @click="submit"
        >
          <v-icon start size="small">mdi-restart</v-icon>
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
        modelValue: { type: Boolean, default: false },
        serviceData: { type: Object, default: () => ({}) },
        loading: { type: Boolean, default: false },
    },
    emits: ['update:modelValue', 'reset'],
    data() {
        return {
            scope: '',
            selectedKeys: [],
            component: '',
            description: '',
            // Vuetify 4 reads `title` where Vuetify 2 read `text`
            scopes: [
                { title: 'Machine Time', value: 'machine_time' },
                { title: 'Print Time', value: 'print_time' },
                { title: 'Pause Time', value: 'pause_time' },
                { title: 'Warmup Time', value: 'warmup_time' },
                { title: 'Jobs', value: 'jobs' },
                { title: 'Axes', value: 'axes' },
                { title: 'Extruders', value: 'extruders' },
                { title: 'Filament', value: 'filament' },
                { title: 'Heaters', value: 'heaters' },
                { title: 'Fans', value: 'fans' },
            ],
            components: [
                { title: 'Nozzle', value: 'nozzle' },
                { title: 'Extruder', value: 'extruder' },
                { title: 'Hotend Fan', value: 'fan_hotend' },
                { title: 'Heater (Bed)', value: 'heater_bed' },
                { title: 'Belt X', value: 'belt_x' },
                { title: 'Belt Y', value: 'belt_y' },
                { title: 'Mainboard', value: 'mainboard' },
                { title: 'Other', value: 'other' },
            ],
        }
    },
    computed: {
        visible: {
            get() { return this.modelValue },
            set(val) { this.$emit('update:modelValue', val) }
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
