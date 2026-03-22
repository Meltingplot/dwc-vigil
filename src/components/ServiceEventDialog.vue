<template>
  <v-dialog v-model="visible" max-width="450" persistent>
    <v-card>
      <v-card-title>Log Service Event</v-card-title>
      <v-card-text>
        <v-select
          v-model="component"
          :items="components"
          label="Component"
          outlined
          dense
        />
        <v-textarea
          v-model="description"
          label="Description (required)"
          outlined
          dense
          rows="3"
          :rules="[v => (v && v.length >= 3) || 'Min. 3 characters']"
        />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn text @click="close">Cancel</v-btn>
        <v-btn
          color="primary"
          :disabled="!isValid"
          :loading="loading"
          @click="submit"
        >
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
