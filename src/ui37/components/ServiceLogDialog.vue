<template>
  <v-dialog v-model="visible" max-width="700" scrollable>
    <v-card style="border-radius: 8px">
      <v-card-title class="d-flex align-center">
        <v-icon color="primary" class="mr-2">mdi-history</v-icon>
        Service Log
        <v-spacer />
        <v-btn icon="mdi-close" variant="text" size="small" @click="visible = false" />
      </v-card-title>
      <v-divider />
      <v-card-text style="max-height: 500px">
        <div v-if="loading" class="d-flex flex-column align-center justify-center" style="min-height: 200px">
          <v-progress-circular indeterminate size="32" color="primary" />
          <div class="text-caption text-medium-emphasis mt-2">Loading service log&hellip;</div>
        </div>
        <div v-else-if="entries.length === 0" class="d-flex flex-column align-center justify-center" style="min-height: 200px">
          <v-icon size="48" color="grey-lighten-1">mdi-clipboard-text-outline</v-icon>
          <div class="text-caption text-medium-emphasis mt-2">No service events logged yet</div>
        </div>
        <v-timeline v-else density="compact" align="start" side="end">
          <v-timeline-item
            v-for="(entry, i) in entries"
            :key="i"
            :dot-color="entry.type === 'counter_reset' ? 'amber-darken-1' : 'primary'"
            :icon="entry.type === 'counter_reset' ? 'mdi-restart' : 'mdi-wrench'"
            size="small"
          >
            <div class="d-flex align-start">
              <div style="flex: 1">
                <div class="text-body-2 font-weight-medium">{{ entry.description }}</div>
                <div class="text-caption text-medium-emphasis mt-1">
                  {{ formatDate(entry.timestamp) }}
                  <span v-if="entry.type === 'counter_reset'" class="text-amber-darken-2">
                    &mdash; Reset: {{ entry.reset_scope }}
                    <template v-if="entry.reset_keys">({{ entry.reset_keys.join(', ') }})</template>
                  </span>
                </div>
              </div>
              <v-chip v-if="entry.component" size="x-small" variant="outlined" class="ml-2 mt-1">
                {{ entry.component }}
              </v-chip>
            </div>
          </v-timeline-item>
        </v-timeline>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script>
export default {
    name: 'ServiceLogDialog',
    props: {
        modelValue: { type: Boolean, default: false },
        entries: { type: Array, default: () => [] },
        loading: { type: Boolean, default: false },
    },
    emits: ['update:modelValue'],
    computed: {
        visible: {
            get() { return this.modelValue },
            set(val) { this.$emit('update:modelValue', val) }
        }
    },
    methods: {
        formatDate(iso) {
            if (!iso) return ''
            try {
                return new Date(iso).toLocaleString()
            } catch {
                return iso
            }
        }
    }
}
</script>
