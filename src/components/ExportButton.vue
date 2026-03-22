<template>
  <v-menu offset-y>
    <template #activator="{ on, attrs }">
      <v-btn outlined v-bind="attrs" :loading="loading" v-on="on">
        <v-icon left>mdi-download</v-icon>
        Export
      </v-btn>
    </template>
    <v-list dense>
      <v-list-item @click="$emit('export', 'json')">
        <v-list-item-title>Export JSON</v-list-item-title>
      </v-list-item>
      <v-list-item @click="$emit('export', 'csv')">
        <v-list-item-title>Export CSV</v-list-item-title>
      </v-list-item>
    </v-list>
  </v-menu>
</template>

<script>
export default {
    name: 'ExportButton',
    props: {
        loading: { type: Boolean, default: false },
    }
}
</script>
