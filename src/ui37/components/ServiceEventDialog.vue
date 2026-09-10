<template>
  <v-dialog v-model="visible" max-width="450" persistent>
    <v-card style="border-radius: 8px">
      <v-card-title class="d-flex align-center">
        <v-icon color="primary" class="mr-2">mdi-wrench</v-icon>
        Log Service Event
      </v-card-title>
      <v-divider />
      <v-card-text class="pt-4">
        <v-select
          v-model="component"
          :items="components"
          label="Component"
          variant="outlined"
          density="compact"
          prepend-inner-icon="mdi-cog-outline"
        />
        <v-textarea
          v-model="description"
          label="Description"
          placeholder="What service was performed?"
          variant="outlined"
          density="compact"
          rows="3"
          prepend-inner-icon="mdi-text"
          :rules="[v => (v && v.length >= 3) || 'Min. 3 characters']"
        />
      </v-card-text>
      <v-divider />
      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn variant="text" @click="close">Cancel</v-btn>
        <v-btn
          color="primary"
          :disabled="!isValid"
          :loading="loading"
          @click="submit"
        >
          <v-icon start size="small">mdi-check</v-icon>
          Save
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script>
export default {
    name: 'ServiceEventDialog',
    props: {
        modelValue: { type: Boolean, default: false },
        loading: { type: Boolean, default: false },
    },
    emits: ['update:modelValue', 'submit'],
    data() {
        return {
            component: 'other',
            description: '',
            // Vuetify 4 reads `title` where Vuetify 2 read `text`
            components: [
                { title: 'Nozzle', value: 'nozzle' },
                { title: 'Extruder', value: 'extruder' },
                { title: 'Hotend Fan', value: 'fan_hotend' },
                { title: 'Part Fan', value: 'fan_part' },
                { title: 'Heater (Bed)', value: 'heater_bed' },
                { title: 'Heater (Hotend)', value: 'heater_hotend' },
                { title: 'Belt X', value: 'belt_x' },
                { title: 'Belt Y', value: 'belt_y' },
                { title: 'Linear Guide', value: 'linear_guide' },
                { title: 'Mainboard', value: 'mainboard' },
                { title: 'SD Card', value: 'sdcard' },
                { title: 'Firmware', value: 'firmware' },
                { title: 'Other', value: 'other' },
            ],
        }
    },
    computed: {
        visible: {
            get() { return this.modelValue },
            set(val) { this.$emit('update:modelValue', val) }
        },
        isValid() {
            return this.component && this.description && this.description.length >= 3
        }
    },
    methods: {
        submit() {
            this.$emit('submit', {
                component: this.component,
                description: this.description,
            })
        },
        close() {
            this.component = 'other'
            this.description = ''
            this.visible = false
        }
    }
}
</script>
