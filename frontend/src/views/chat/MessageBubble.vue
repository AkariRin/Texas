<template>
  <div class="message-bubble d-flex mb-3" :class="{ 'flex-row-reverse': isSelf }">
    <!-- 头像 -->
    <v-avatar size="36" class="flex-shrink-0" :class="isSelf ? 'ml-2' : 'mr-2'">
      <v-img
        :src="`https://q1.qlogo.cn/g?b=qq&nk=${message.user_id}&s=100`"
        :alt="message.sender_nickname"
      >
        <template #error>
          <v-icon>mdi-account-circle</v-icon>
        </template>
      </v-img>
    </v-avatar>

    <!-- 内容 -->
    <div class="message-content" :class="{ 'text-right': isSelf }" style="max-width: 70%;">
      <!-- 昵称与时间 -->
      <div class="d-flex align-center ga-2 mb-1" :class="{ 'flex-row-reverse': isSelf }">
        <span class="text-caption font-weight-medium">
          {{ displayName }}
        </span>
        <span v-if="message.sender_role && message.sender_role !== 'member'" class="text-caption">
          <v-chip size="x-small" variant="tonal" :color="roleColor">{{ roleLabel }}</v-chip>
        </span>
        <span class="text-caption text-medium-emphasis">
          {{ formatTime(message.created_at) }}
        </span>
      </div>

      <!-- 消息气泡 -->
      <div
        class="message-body rounded-lg pa-2 px-3"
        :class="isSelf ? 'bg-blue-lighten-4' : 'bg-grey-lighten-3'"
      >
        <MessageSegmentRenderer :segments="message.segments" @image-click="$emit('imageClick', $event)" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ChatMessage } from '@/services/chat'
import MessageSegmentRenderer from './MessageSegment.vue'

const props = defineProps<{
  message: ChatMessage
  selfId?: number
}>()

defineEmits<{
  imageClick: [url: string]
}>()

const isSelf = computed(() => {
  if (props.selfId) return props.message.user_id === props.selfId
  return props.message.message_type === 3 // SELF_SENT
})

const displayName = computed(() => {
  return props.message.sender_card || props.message.sender_nickname || String(props.message.user_id)
})

const roleColor = computed(() => {
  switch (props.message.sender_role) {
    case 'owner': return 'amber'
    case 'admin': return 'blue'
    default: return 'grey'
  }
})

const roleLabel = computed(() => {
  switch (props.message.sender_role) {
    case 'owner': return '群主'
    case 'admin': return '管理员'
    default: return props.message.sender_role
  }
})

function formatTime(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  const time = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  if (isToday) return time
  return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }) + ' ' + time
}
</script>

<style scoped>
.message-bubble {
  padding: 0 4px;
}

.message-body {
  display: inline-block;
  text-align: left;
  max-width: 100%;
}
</style>

