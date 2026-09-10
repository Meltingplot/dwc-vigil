<template>
  <v-card class="vigil-card" style="border-radius: 8px">
    <v-tabs v-model="internalTab" bg-color="transparent" grow>
      <v-tab :value="0">
        <v-icon start size="small">mdi-infinity</v-icon>
        Lifetime
      </v-tab>
      <v-tab :value="1">
        <v-icon start size="small">mdi-wrench-outline</v-icon>
        Since Service
      </v-tab>
      <v-tab :value="2">
        <v-icon start size="small">mdi-clock-outline</v-icon>
        Session
      </v-tab>
    </v-tabs>
  </v-card>
</template>

<script>
export default {
    name: 'CounterTabs',
    props: {
        modelValue: { type: Number, default: 0 }
    },
    emits: ['update:modelValue'],
    computed: {
        internalTab: {
            get() { return this.modelValue },
            set(val) { this.$emit('update:modelValue', val) }
        }
    }
}
</script>
