<script setup lang="ts">
import type { ControllerInfo } from '@/types/handler'

defineProps<{
  controller: ControllerInfo
}>()

const emit = defineEmits<{
  click: []
}>()
</script>

<template>
  <v-card variant="outlined" class="pa-4 cursor-pointer" @click="emit('click')">
    <div class="d-flex align-center mb-2">
      <v-icon icon="mdi-puzzle" class="mr-2" />
      <span class="text-h6">{{ controller.name }}</span>
      <v-chip size="x-small" class="ml-2" color="primary">v{{ controller.version }}</v-chip>
    </div>
    <div class="text-body-2 text-medium-emphasis mb-2">
      {{ controller.description || 'No description' }}
    </div>
    <div class="text-caption">
      {{ controller.handlerCount }} handler(s)
    </div>
  </v-card>
</template>

