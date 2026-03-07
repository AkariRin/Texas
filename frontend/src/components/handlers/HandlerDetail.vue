<script setup lang="ts">
import type { ControllerInfo } from '@/types/handler'

defineProps<{
  controller: ControllerInfo | null
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()
</script>

<template>
  <v-dialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    max-width="600"
  >
    <v-card v-if="controller">
      <v-card-title class="d-flex align-center">
        <v-icon icon="mdi-puzzle" class="mr-2" />
        {{ controller.name }}
        <v-chip size="small" class="ml-2" color="primary">v{{ controller.version }}</v-chip>
      </v-card-title>
      <v-card-subtitle>{{ controller.description }}</v-card-subtitle>
      <v-card-text>
        <v-table density="compact">
          <thead>
            <tr>
              <th>Method</th>
              <th>Type</th>
              <th>Priority</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in controller.methods" :key="m.method">
              <td><code>{{ m.method }}</code></td>
              <td>
                <v-chip size="x-small" color="secondary">{{ m.mappingType }}</v-chip>
              </td>
              <td>{{ m.priority }}</td>
            </tr>
          </tbody>
        </v-table>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn @click="emit('update:modelValue', false)">Close</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

