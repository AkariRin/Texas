<template>
  <v-dialog v-model="dialogVisible" max-width="600" persistent>
    <v-card rounded="lg">
      <v-card-title class="d-flex align-center">
        <v-icon class="mr-2">mdi-archive</v-icon>
        归档详情
        <v-spacer></v-spacer>
        <v-btn icon="mdi-close" variant="text" size="small" @click="close"></v-btn>
      </v-card-title>
      <v-divider></v-divider>
      <v-card-text v-if="archive">
        <v-list density="compact" class="bg-transparent">
          <v-list-item>
            <v-list-item-title class="text-medium-emphasis">分区名称</v-list-item-title>
            <v-list-item-subtitle class="font-weight-medium">{{ archive.partition_name }}</v-list-item-subtitle>
          </v-list-item>
          <v-list-item>
            <v-list-item-title class="text-medium-emphasis">归档周期</v-list-item-title>
            <v-list-item-subtitle>{{ archive.period_start }} — {{ archive.period_end }}</v-list-item-subtitle>
          </v-list-item>
          <v-list-item>
            <v-list-item-title class="text-medium-emphasis">状态</v-list-item-title>
            <v-list-item-subtitle>
              <v-chip :color="statusColor(archive.status)" size="small" variant="flat">
                {{ archive.status }}
              </v-chip>
            </v-list-item-subtitle>
          </v-list-item>
          <v-list-item>
            <v-list-item-title class="text-medium-emphasis">总行数</v-list-item-title>
            <v-list-item-subtitle>{{ formatNumber(archive.total_rows) }}</v-list-item-subtitle>
          </v-list-item>
          <v-list-item>
            <v-list-item-title class="text-medium-emphasis">原始大小</v-list-item-title>
            <v-list-item-subtitle>{{ formatBytes(archive.original_bytes) }}</v-list-item-subtitle>
          </v-list-item>
          <v-list-item>
            <v-list-item-title class="text-medium-emphasis">压缩后大小</v-list-item-title>
            <v-list-item-subtitle>{{ formatBytes(archive.compressed_bytes) }}</v-list-item-subtitle>
          </v-list-item>
          <v-list-item v-if="archive.original_bytes > 0 && archive.compressed_bytes > 0">
            <v-list-item-title class="text-medium-emphasis">压缩率</v-list-item-title>
            <v-list-item-subtitle>
              {{ (archive.original_bytes / archive.compressed_bytes).toFixed(1) }}:1
            </v-list-item-subtitle>
          </v-list-item>
          <v-list-item>
            <v-list-item-title class="text-medium-emphasis">S3 路径</v-list-item-title>
            <v-list-item-subtitle class="text-caption" style="word-break: break-all;">
              s3://{{ archive.s3_bucket }}/{{ archive.s3_key }}
            </v-list-item-subtitle>
          </v-list-item>
          <v-list-item>
            <v-list-item-title class="text-medium-emphasis">创建时间</v-list-item-title>
            <v-list-item-subtitle>{{ formatTime(archive.created_at) }}</v-list-item-subtitle>
          </v-list-item>
          <v-list-item v-if="archive.completed_at">
            <v-list-item-title class="text-medium-emphasis">完成时间</v-list-item-title>
            <v-list-item-subtitle>{{ formatTime(archive.completed_at) }}</v-list-item-subtitle>
          </v-list-item>
          <v-list-item v-if="archive.error_message">
            <v-list-item-title class="text-medium-emphasis text-error">错误信息</v-list-item-title>
            <v-list-item-subtitle class="text-error">{{ archive.error_message }}</v-list-item-subtitle>
          </v-list-item>
        </v-list>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ArchiveLog } from '@/services/chat'

const props = defineProps<{
  modelValue: boolean
  archive: ArchiveLog | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

function close() {
  dialogVisible.value = false
}

function statusColor(status: string): string {
  const colors: Record<string, string> = {
    pending: 'grey',
    exporting: 'blue',
    uploading: 'indigo',
    uploaded: 'teal',
    partition_dropped: 'cyan',
    completed: 'green',
    failed: 'red',
  }
  return colors[status] ?? 'grey'
}

function formatNumber(n: number): string {
  return n.toLocaleString()
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + units[i]
}

function formatTime(iso: string | null): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN')
}
</script>

