<template>
  <div class="d-flex align-center pa-2" style="gap: 8px;">
    <template v-for="seg in segments" :key="seg">
      <!-- 文本 -->
      <span v-if="seg.type === 'text'" class="message-text" v-html="escapeHtml(String(seg.data?.text ?? ''))"></span>

      <!-- 图片 -->
      <v-img
        v-else-if="seg.type === 'image'"
        :src="String(seg.data?.url ?? '')"
        max-width="200"
        max-height="200"
        class="rounded message-image cursor-pointer"
        @click="$emit('imageClick', String(seg.data?.url ?? ''))"
      >
        <template #placeholder>
          <div class="d-flex align-center justify-center fill-height">
            <v-progress-circular indeterminate size="24" color="grey"></v-progress-circular>
          </div>
        </template>
        <template #error>
          <div class="d-flex align-center justify-center fill-height bg-grey-lighten-3 rounded pa-2">
            <v-icon color="grey">mdi-image-broken</v-icon>
          </div>
        </template>
      </v-img>

      <!-- @ 某人 -->
      <v-chip
        v-else-if="seg.type === 'at'"
        size="small"
        color="blue-lighten-4"
        variant="flat"
        class="mx-1"
      >
        @{{ seg.data?.qq === 'all' ? '全体成员' : seg.data?.qq }}
      </v-chip>

      <!-- 回复引用 -->
      <v-chip
        v-else-if="seg.type === 'reply'"
        size="x-small"
        color="grey-lighten-2"
        variant="flat"
        prepend-icon="mdi-reply"
        class="mr-1"
      >
        回复 #{{ seg.data?.id }}
      </v-chip>

      <!-- 表情 -->
      <span v-else-if="seg.type === 'face'" class="message-face" :title="`表情 ${seg.data?.id}`">
        [表情{{ seg.data?.id }}]
      </span>

      <!-- 其他类型 -->
      <v-chip v-else size="x-small" color="grey-lighten-2" variant="flat">
        [{{ seg.type }}]
      </v-chip>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { MessageSegment } from '@/services/chat'

defineProps<{
  segments: MessageSegment[]
}>()

defineEmits<{
  imageClick: [url: string]
}>()

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
}
</script>

<style scoped>
.message-text {
  white-space: pre-wrap;
  word-break: break-word;
}

.message-image {
  border: 1px solid rgba(0, 0, 0, 0.1);
}

.message-face {
  color: #f59e0b;
  font-size: 0.9em;
}
</style>

