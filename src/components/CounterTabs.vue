<template>
  <v-tabs v-model="internalTab" background-color="transparent" grow>
    <v-tab>Lifetime</v-tab>
    <v-tab>Ab Service</v-tab>
    <v-tab>Session</v-tab>
  </v-tabs>
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
