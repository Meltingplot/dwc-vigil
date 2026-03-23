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
          outlined
          dense
          prepend-inner-icon="mdi-cog-outline"
        />
        <v-textarea
          v-model="description"
          label="Description"
          placeholder="What service was performed?"
          outlined
          dense
          rows="3"
          prepend-inner-icon="mdi-text"
          :rules="[v => (v && v.length >= 3) || 'Min. 3 characters']"
        />
      </v-card-text>
      <v-divider />
      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn text @click="close">Cancel</v-btn>
        <v-btn
          color="primary"
          :disabled="!isValid"
          :loading="loading"
          @click="submit"
        >
          <v-icon left small>mdi-check</v-icon>
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
        value: { type: Boolean, default: false },
        loading: { type: Boolean, default: false },
    },
    data() {
        return {
            component: 'other',
            description: '',
            components: [
                { text: 'Nozzle', value: 'nozzle' },
                { text: 'Extruder', value: 'extruder' },
                { text: 'Hotend Fan', value: 'fan_hotend' },
                { text: 'Part Fan', value: 'fan_part' },
                { text: 'Heater (Bed)', value: 'heater_bed' },
                { text: 'Heater (Hotend)', value: 'heater_hotend' },
                { text: 'Belt X', value: 'belt_x' },
                { text: 'Belt Y', value: 'belt_y' },
                { text: 'Linear Guide', value: 'linear_guide' },
                { text: 'Mainboard', value: 'mainboard' },
                { text: 'SD Card', value: 'sdcard' },
                { text: 'Firmware', value: 'firmware' },
                { text: 'Other', value: 'other' },
            ],
        }
    },
    computed: {
        visible: {
            get() { return this.value },
            set(val) { this.$emit('input', val) }
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
