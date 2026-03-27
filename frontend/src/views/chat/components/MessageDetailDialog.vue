<template>
  <v-dialog :model-value="modelValue" max-width="640" scrollable @update:model-value="$emit('update:modelValue', $event)">
    <v-card rounded="lg">
      <v-card-title class="d-flex align-center">
        <v-icon class="mr-2" size="small">mdi-code-json</v-icon>
        消息详情
        <v-spacer></v-spacer>
        <v-btn icon="mdi-close" size="small" variant="text" @click="$emit('update:modelValue', false)"></v-btn>
      </v-card-title>
      <v-divider></v-divider>
      <v-card-text class="pa-0">
        <v-table density="compact">
          <tbody>
            <tr>
              <td class="text-caption font-weight-bold" style="width: 140px">ID</td>
              <td class="text-caption">{{ message?.id }}</td>
            </tr>
            <tr>
              <td class="text-caption font-weight-bold">Message ID</td>
              <td class="text-caption">{{ message?.message_id }}</td>
            </tr>
            <tr>
              <td class="text-caption font-weight-bold">消息类型</td>
              <td class="text-caption">{{ formatMessageType(message?.message_type) }}</td>
            </tr>
            <tr>
              <td class="text-caption font-weight-bold">群号</td>
              <td class="text-caption">{{ message?.group_id ?? '-' }}</td>
            </tr>
            <tr>
              <td class="text-caption font-weight-bold">发送者 QQ</td>
              <td class="text-caption">{{ message?.user_id }}</td>
            </tr>
            <tr>
              <td class="text-caption font-weight-bold">昵称</td>
              <td class="text-caption">{{ message?.sender_nickname }}</td>
            </tr>
            <tr>
              <td class="text-caption font-weight-bold">群名片</td>
              <td class="text-caption">{{ message?.sender_card ?? '-' }}</td>
            </tr>
            <tr>
              <td class="text-caption font-weight-bold">角色</td>
              <td class="text-caption">{{ message?.sender_role ?? '-' }}</td>
            </tr>
            <tr>
              <td class="text-caption font-weight-bold">原始消息</td>
              <td class="text-caption" style="white-space: pre-wrap; word-break: break-all">
                {{ message?.raw_message }}
              </td>
            </tr>
            <tr>
              <td class="text-caption font-weight-bold">创建时间</td>
              <td class="text-caption">{{ message?.created_at ?? '-' }}</td>
            </tr>
            <tr>
              <td class="text-caption font-weight-bold">存储时间</td>
              <td class="text-caption">{{ message?.stored_at ?? '-' }}</td>
            </tr>
          </tbody>
        </v-table>
        <v-divider></v-divider>
        <div class="pa-3">
          <div class="text-caption font-weight-bold mb-1">Segments (JSON)</div>
          <pre class="text-caption detail-json pa-2 rounded bg-grey-lighten-4">{{
            JSON.stringify(message?.segments, null, 2)
          }}</pre>
        </div>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import type { ChatMessage } from '@/apis/chat'

defineProps<{ modelValue: boolean; message: ChatMessage | null }>()
defineEmits<{ 'update:modelValue': [value: boolean] }>()

function formatMessageType(type: number | undefined): string {
  switch (type) {
    case 1: return '群消息'
    case 2: return '私聊消息'
    case 3: return '自己发送'
    default: return String(type ?? '-')
  }
}
</script>

<style scoped>
.detail-json {
  overflow-x: auto;
  max-height: 300px;
  font-family: monospace;
  white-space: pre;
  word-break: break-all;
}
</style>
