<template>
  <div class="mb-6">
    <div class="d-flex align-center">
      <v-icon size="32" class="mr-3">{{ icon }}</v-icon>
      <h1 class="text-h4 font-weight-bold">{{ title }}</h1>
      <v-spacer />
      <slot />
    </div>
    <p class="text-body-2 text-medium-emphasis mt-1">{{ subtitle }}</p>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  icon: string
  title: string
  subtitle: string
}>()
</script>
