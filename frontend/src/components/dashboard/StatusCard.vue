<script setup lang="ts">
defineProps<{
  title: string
  value: string | number
  icon: string
  color?: string
}>()
</script>

<template>
  <v-card :color="color" variant="tonal" class="pa-4">
    <div class="d-flex align-center">
      <v-icon :icon="icon" size="40" class="mr-4" />
      <div>
        <div class="text-caption text-medium-emphasis">{{ title }}</div>
        <div class="text-h5 font-weight-bold">{{ value }}</div>
      </div>
    </div>
  </v-card>
</template>

