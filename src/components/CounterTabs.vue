<template>
  <v-card class="vigil-card" style="border-radius: 8px">
    <v-tabs v-model="internalTab" background-color="transparent" grow slider-size="3">
      <v-tab>
        <v-icon left small>mdi-infinity</v-icon>
        Lifetime
      </v-tab>
      <v-tab>
        <v-icon left small>mdi-wrench-outline</v-icon>
        Since Service
      </v-tab>
      <v-tab>
        <v-icon left small>mdi-clock-outline</v-icon>
        Session
      </v-tab>
    </v-tabs>
  </v-card>
</template>

<script>
export default {
    name: 'CounterTabs',
    props: {
        value: { type: Number, default: 0 }
    },
    computed: {
        internalTab: {
            get() { return this.value },
            set(val) { this.$emit('input', val) }
        }
    }
}
</script>
