<script setup lang="ts">
import { ref } from 'vue'

defineProps<{
  title?: string
}>()

const emit = defineEmits<{
  toggleDrawer: []
  toggleTheme: []
}>()
</script>

<template>
  <v-app-bar color="primary" density="default" elevation="2">
    <v-app-bar-nav-icon @click="emit('toggleDrawer')" />
    <v-app-bar-title>{{ title ?? 'Texas Bot' }}</v-app-bar-title>
    <v-spacer />
    <v-btn icon @click="emit('toggleTheme')">
      <v-icon>mdi-theme-light-dark</v-icon>
    </v-btn>
  </v-app-bar>
</template>

