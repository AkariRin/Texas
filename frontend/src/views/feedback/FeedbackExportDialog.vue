<template>
  <v-dialog
    :model-value="modelValue"
    max-width="500"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <v-card>
      <v-card-title class="pa-4">导出反馈</v-card-title>
      <v-divider />
      <v-card-text class="pa-4">
        <div class="text-body-2 mb-3">已选择 {{ selected.length }} 条反馈</div>
        <v-radio-group v-model="exportMode" density="compact">
          <v-radio label="完整模式（包含所有信息）" value="full" />
          <v-radio label="仅需求模式（按类型分组）" value="requirements-only" />
        </v-radio-group>
      </v-card-text>
      <v-card-actions class="pa-4">
        <v-spacer />
        <v-btn variant="elevated" @click="emit('update:modelValue', false)">取消</v-btn>
        <v-btn variant="elevated" color="primary" @click="doExport">下载 Markdown</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { Feedback } from '@/apis/feedback'
import { exportToMarkdown, type ExportMode } from '@/utils/feedbackExport'

const props = defineProps<{
  modelValue: boolean
  selected: Feedback[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const exportMode = ref<ExportMode>('full')

function doExport() {
  exportToMarkdown(props.selected, exportMode.value)
  emit('update:modelValue', false)
}
</script>
