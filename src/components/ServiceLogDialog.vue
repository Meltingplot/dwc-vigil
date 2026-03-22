<template>
  <v-dialog v-model="visible" max-width="700" scrollable>
    <v-card>
      <v-card-title class="d-flex align-center">
        Service Log
        <v-spacer />
        <v-btn icon @click="visible = false">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text style="max-height: 500px">
        <div v-if="loading" class="text-center py-8">
          <v-progress-circular indeterminate size="32" />
        </div>
        <div v-else-if="entries.length === 0" class="text-center grey--text py-8">
          No service events logged yet
        </div>
        <v-list v-else dense>
          <v-list-item v-for="(entry, i) in entries" :key="i" class="px-0">
            <v-list-item-icon class="mr-3">
              <v-icon :color="entry.type === 'counter_reset' ? 'warning' : 'primary'" small>
                {{ entry.type === 'counter_reset' ? 'mdi-restart' : 'mdi-wrench' }}
              </v-icon>
            </v-list-item-icon>
            <v-list-item-content>
              <v-list-item-title>
                {{ entry.description }}
                <v-chip v-if="entry.component" x-small outlined class="ml-1">
                  {{ entry.component }}
                </v-chip>
              </v-list-item-title>
              <v-list-item-subtitle>
                {{ formatDate(entry.timestamp) }}
                <span v-if="entry.type === 'counter_reset'" class="warning--text">
                  — Reset: {{ entry.reset_scope }}
                  <template v-if="entry.reset_keys">({{ entry.reset_keys.join(', ') }})</template>
                </span>
              </v-list-item-subtitle>
            </v-list-item-content>
          </v-list-item>
        </v-list>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script>
export default {
    name: 'ServiceLogDialog',
    props: {
        value: { type: Boolean, default: false },
        entries: { type: Array, default: () => [] },
        loading: { type: Boolean, default: false },
    },
    computed: {
        visible: {
            get() { return this.value },
            set(val) { this.$emit('input', val) }
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
