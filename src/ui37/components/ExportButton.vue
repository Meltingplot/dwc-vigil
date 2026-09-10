<template>
  <v-menu>
    <template #activator="{ props: menu }">
      <v-btn variant="outlined" size="small" :loading="loading" v-bind="menu">
        <v-icon start size="small">mdi-download</v-icon>
        Export
      </v-btn>
    </template>
    <v-list density="compact">
      <v-list-item prepend-icon="mdi-code-json" @click="$emit('export', 'json')">
        <v-list-item-title>Export JSON</v-list-item-title>
      </v-list-item>
      <v-list-item prepend-icon="mdi-file-delimited" @click="$emit('export', 'csv')">
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
    },
    emits: ['export'],
}
</script>
