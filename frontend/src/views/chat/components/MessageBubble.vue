<template>
  <div class="message-bubble px-1 d-flex align-start mb-3">
    <!-- 头像 -->
    <v-avatar size="36" class="flex-shrink-0 mr-2">
      <v-img :src="`https://q1.qlogo.cn/g?b=qq&nk=${msg.user_id}&s=100`" :alt="msg.sender_nickname">
        <template #error>
          <v-icon>mdi-account-circle</v-icon>
        </template>
      </v-img>
    </v-avatar>

    <!-- 内容 -->
    <div class="message-content" style="max-width: 70%">
      <!-- 昵称与时间 -->
      <div class="d-flex align-center ga-2 mb-1">
        <span class="text-caption font-weight-medium">
          {{ msg.sender_card || msg.sender_nickname || String(msg.user_id) }}
        </span>
        <span v-if="msg.sender_role && msg.sender_role !== 'member'" class="text-caption">
          <v-chip size="x-small" variant="elevated" :color="roleColor(msg.sender_role)">
            {{ roleLabel(msg.sender_role) }}
          </v-chip>
        </span>
        <span class="text-caption text-medium-emphasis">
          {{ formatMsgTime(msg.created_at) }}
        </span>
      </div>

      <!-- 无法解析的消息 -->
      <v-card
        v-if="!msg.segments || msg.segments.length === 0"
        elevation="2"
        rounded="lg"
        class="message-body"
        color="red-lighten-5"
        variant="elevated"
      >
        <div class="d-flex align-center ga-2 py-2 px-3">
          <v-icon size="small" color="red-darken-1">mdi-alert-circle-outline</v-icon>
          <span class="text-body-2 text-red-darken-1">消息无法解析</span>
        </div>
      </v-card>

      <!-- 正常消息卡片 -->
      <v-card
        v-else
        elevation="2"
        rounded="lg"
        class="message-body"
        :color="isSelf ? 'blue-lighten-4' : undefined"
      >
        <div class="d-flex align-center flex-wrap ga-2 py-2 px-3">
          <MessageSegmentRenderer
            :segments="msg.segments"
            :member-name-map="memberNameMap"
            @open-member="emit('openMember', $event)"
            @open-image="emit('openImage', $event)"
          />
        </div>
      </v-card>
    </div>

    <!-- 详情按钮 -->
    <v-btn
      icon="mdi-information-outline"
      size="x-small"
      variant="text"
      color="grey"
      class="ml-1 mt-5 flex-shrink-0 detail-btn"
      @click="emit('showDetail', msg)"
    ></v-btn>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ChatMessage } from '@/apis/chat'
import { roleColor, roleLabel } from '@/utils/personnel'
import MessageSegmentRenderer from './MessageSegmentRenderer.vue'

const props = defineProps<{
  msg: ChatMessage
  memberNameMap: Map<number, string>
}>()

const emit = defineEmits<{
  showDetail: [msg: ChatMessage]
  openMember: [qq: unknown]
  openImage: [src: string]
}>()

const isSelf = computed(() => props.msg.message_type === 3)

function formatMsgTime(iso: string | null): string {
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
.message-body {
  text-align: left;
  max-width: 100%;
}

.detail-btn {
  opacity: 0;
  transition: opacity 0.15s ease;
}

.message-bubble:hover .detail-btn {
  opacity: 1;
}
</style>
