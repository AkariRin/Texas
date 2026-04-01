<template>
  <template v-for="seg in segments" :key="seg">
    <span
      v-if="seg.type === 'text'"
      class="message-text"
      v-html="escapeHtml(String(seg.data?.text ?? ''))"
    ></span>
    <v-img
      v-else-if="seg.type === 'image'"
      :src="getImageSrc(seg)"
      max-width="200"
      max-height="200"
      class="rounded message-image cursor-pointer"
      @click="emit('openImage', getImageSrc(seg))"
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
    <v-chip
      v-else-if="seg.type === 'at'"
      size="small"
      color="blue-lighten-4"
      variant="elevated"
      class="mx-1 cursor-pointer"
      :class="{ 'at-chip-clickable': seg.data?.qq !== 'all' }"
      @click="emit('openMember', seg.data?.qq)"
    >
      @{{ getAtDisplayName(seg.data?.qq) }}
    </v-chip>
    <v-chip
      v-else-if="seg.type === 'reply'"
      size="x-small"
      color="grey-lighten-2"
      variant="elevated"
      prepend-icon="mdi-reply"
      class="mr-1"
    >
      回复 #{{ seg.data?.id }}
    </v-chip>
    <span v-else-if="seg.type === 'face'" class="message-face" :title="`表情 ${seg.data?.id}`">
      [表情{{ seg.data?.id }}]
    </span>
    <!-- 商城表情 mface -->
    <v-img
      v-else-if="seg.type === 'mface' && seg.data?.url"
      :src="String(seg.data.url)"
      max-width="120"
      max-height="120"
      class="rounded message-image cursor-pointer"
      :title="String(seg.data?.summary ?? '商城表情')"
      @click="emit('openImage', String(seg.data.url))"
    >
      <template #error>
        <v-chip size="x-small" color="amber-lighten-4" variant="elevated">
          {{ seg.data?.summary ?? '[商城表情]' }}
        </v-chip>
      </template>
    </v-img>
    <v-chip
      v-else-if="seg.type === 'mface'"
      size="small"
      color="amber-lighten-4"
      variant="elevated"
    >
      {{ seg.data?.summary ?? '[商城表情]' }}
    </v-chip>
    <!-- 视频 -->
    <v-card
      v-else-if="seg.type === 'video'"
      variant="outlined"
      rounded="lg"
      class="pa-2"
      max-width="240"
    >
      <div class="d-flex align-center ga-2">
        <v-icon color="blue">mdi-video-outline</v-icon>
        <div>
          <div class="text-body-2">{{ seg.data?.name || '视频' }}</div>
          <div v-if="seg.data?.file_size" class="text-caption text-medium-emphasis">
            {{ formatBytes(Number(seg.data.file_size)) }}
          </div>
        </div>
      </div>
      <video
        v-if="seg.data?.url || seg.data?.file"
        :src="String(seg.data?.url ?? seg.data?.file ?? '')"
        controls
        preload="metadata"
        class="rounded mt-1"
        style="max-width: 220px; max-height: 200px"
      ></video>
    </v-card>
    <!-- 语音 -->
    <v-card
      v-else-if="seg.type === 'record'"
      variant="outlined"
      rounded="lg"
      class="pa-2"
      max-width="260"
    >
      <div class="d-flex align-center ga-2">
        <v-icon color="green">mdi-microphone</v-icon>
        <span class="text-body-2">语音消息</span>
      </div>
      <audio
        v-if="seg.data?.url || seg.data?.file"
        :src="String(seg.data?.url ?? seg.data?.file ?? '')"
        controls
        preload="metadata"
        class="mt-1"
        style="max-width: 240px"
      ></audio>
    </v-card>
    <!-- 文件 -->
    <v-chip
      v-else-if="seg.type === 'file'"
      color="blue-grey-lighten-4"
      variant="elevated"
      prepend-icon="mdi-file-outline"
    >
      <span class="text-body-2">{{ seg.data?.name || '文件' }}</span>
      <span v-if="seg.data?.file_size" class="text-caption text-medium-emphasis ml-1">
        ({{ formatBytes(Number(seg.data.file_size)) }})
      </span>
    </v-chip>
    <!-- 转发消息 -->
    <v-chip
      v-else-if="seg.type === 'forward'"
      size="small"
      color="teal-lighten-4"
      variant="elevated"
      prepend-icon="mdi-share"
    >
      [合并转发]
    </v-chip>
    <!-- JSON 卡片消息 -->
    <v-chip
      v-else-if="seg.type === 'json'"
      size="small"
      color="purple-lighten-4"
      variant="elevated"
      prepend-icon="mdi-code-json"
    >
      [卡片消息]
    </v-chip>
    <!-- 戳一戳 -->
    <v-chip
      v-else-if="seg.type === 'poke'"
      size="small"
      color="pink-lighten-4"
      variant="elevated"
      prepend-icon="mdi-hand-pointing-right"
    >
      [戳一戳]
    </v-chip>
    <!-- 骰子 / 猜拳 -->
    <v-chip
      v-else-if="seg.type === 'dice'"
      size="small"
      color="orange-lighten-4"
      variant="elevated"
      prepend-icon="mdi-dice-multiple"
    >
      [骰子] {{ seg.data?.result != null ? `点数: ${seg.data.result}` : '' }}
    </v-chip>
    <v-chip
      v-else-if="seg.type === 'rps'"
      size="small"
      color="orange-lighten-4"
      variant="elevated"
      prepend-icon="mdi-hand-back-right"
    >
      [猜拳] {{ seg.data?.result != null ? `结果: ${seg.data.result}` : '' }}
    </v-chip>
    <!-- Markdown -->
    <div
      v-else-if="seg.type === 'markdown'"
      class="message-text"
      v-html="escapeHtml(String(seg.data?.content ?? ''))"
    ></div>
    <!-- 未知消息段类型 -->
    <v-chip
      v-else
      size="x-small"
      color="red-lighten-4"
      text-color="red-darken-1"
      variant="elevated"
      prepend-icon="mdi-alert-circle-outline"
    >
      无法解析: {{ seg.type }}
    </v-chip>
  </template>
</template>

<script setup lang="ts">
import type { ChatMessage } from '@/apis/chat'
import { formatBytes } from '@/utils/format'

const props = defineProps<{
  segments: ChatMessage['segments']
  memberNameMap: Map<number, string>
}>()

const emit = defineEmits<{
  openMember: [qq: unknown]
  openImage: [src: string]
}>()

function getAtDisplayName(qq: unknown): string {
  if (qq === 'all') return '全体成员'
  const qqNum = Number(qq)
  if (isNaN(qqNum)) return String(qq)
  return props.memberNameMap.get(qqNum) || String(qq)
}

function getImageSrc(seg: { data?: Record<string, unknown> }): string {
  const url = seg.data?.url
  if (url && typeof url === 'string' && url.length > 0) return url
  const file = seg.data?.file
  if (file && typeof file === 'string' && file.length > 0) return file
  const path = seg.data?.path
  if (path && typeof path === 'string' && path.length > 0) return path
  return ''
}

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

.at-chip-clickable:hover {
  filter: brightness(0.92);
  text-decoration: underline;
}
</style>
