<template>
  <v-dialog
    :model-value="modelValue"
    max-width="90vw"
    content-class="image-preview-dialog"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <v-card
      flat
      color="transparent"
      class="d-flex align-center justify-center"
      @click="$emit('update:modelValue', false)"
    >
      <v-img :src="src" max-width="90vw" max-height="90vh" contain class="rounded-lg elevation-8">
        <template #placeholder>
          <div class="d-flex align-center justify-center fill-height">
            <v-progress-circular indeterminate size="48" color="white"></v-progress-circular>
          </div>
        </template>
      </v-img>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
defineProps<{ modelValue: boolean; src: string }>()
defineEmits<{ 'update:modelValue': [value: boolean] }>()
</script>
