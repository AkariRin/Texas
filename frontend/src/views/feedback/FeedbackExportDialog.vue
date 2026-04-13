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

type ExportMode = 'full' | 'requirements-only'

const props = defineProps<{
  modelValue: boolean
  selected: Feedback[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const exportMode = ref<ExportMode>('full')

function doExport() {
  const content =
    exportMode.value === 'full'
      ? generateFullMarkdown(props.selected)
      : generateRequirementsOnlyMarkdown(props.selected)
  const timestamp = new Date().toISOString().slice(0, 10)
  downloadMarkdown(content, `feedback-export-${exportMode.value}-${timestamp}.md`)
  emit('update:modelValue', false)
}

function generateFullMarkdown(feedbacks: Feedback[]): string {
  const lines: string[] = [
    '# 用户反馈导出（完整模式）',
    '',
    `导出时间：${new Date().toLocaleString('zh-CN')}`,
    `总计：${feedbacks.length} 条`,
    '',
    '---',
    '',
  ]
  feedbacks.forEach((fb, index) => {
    lines.push(`## ${index + 1}. 反馈 #${fb.id}`, '')
    lines.push(`- **提交者 ID**: ${fb.user_id}`)
    lines.push(`- **类型**: ${fb.feedback_type || '未分类'}`)
    lines.push(`- **来源**: ${fb.source}`)
    lines.push(`- **状态**: ${fb.status}`)
    lines.push(`- **提交时间**: ${fb.created_at}`)
    if (fb.processed_at) lines.push(`- **处理时间**: ${fb.processed_at}`)
    lines.push('', '**内容**:', '', fb.content, '')
    if (fb.admin_reply) lines.push('**管理员回复**:', '', fb.admin_reply, '')
    lines.push('---', '')
  })
  return lines.join('\n')
}

function generateRequirementsOnlyMarkdown(feedbacks: Feedback[]): string {
  const lines: string[] = [
    '# 用户反馈导出（仅需求模式）',
    '',
    `导出时间：${new Date().toLocaleString('zh-CN')}`,
    `总计：${feedbacks.length} 条`,
    '',
    '---',
    '',
  ]
  const groups: Record<string, Feedback[]> = { Bug: [], 建议: [], 投诉: [], 其他: [] }
  feedbacks.forEach((fb) => {
    const type = fb.feedback_type || '其他'
    ;(groups[type] ?? groups['其他']!).push(fb)
  })
  for (const type of ['Bug', '建议', '投诉', '其他']) {
    const items = groups[type]
    if (!items?.length) continue
    lines.push(`## ${type}`, '')
    items.forEach((fb, i) => lines.push(`${i + 1}. ${fb.content}`, ''))
    lines.push('---', '')
  }
  return lines.join('\n')
}

function downloadMarkdown(content: string, filename: string): void {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
</script>
