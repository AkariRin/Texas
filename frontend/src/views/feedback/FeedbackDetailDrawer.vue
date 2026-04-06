<template>
  <v-navigation-drawer
    :model-value="modelValue"
    location="right"
    temporary
    width="500"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <v-card v-if="feedback" flat>
      <v-card-title class="d-flex align-center ga-2 pa-4">
        <v-icon>mdi-message-text</v-icon>
        <span>反馈详情</span>
        <v-spacer />
        <v-btn icon size="small" variant="text" @click="emit('update:modelValue', false)">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>

      <v-divider />

      <v-card-text class="pa-4">
        <v-row dense>
          <v-col cols="12">
            <div class="text-caption text-medium-emphasis">反馈 ID</div>
            <div class="text-body-2 font-weight-medium">{{ feedback.id }}</div>
          </v-col>
          <v-col cols="6">
            <div class="text-caption text-medium-emphasis">提交者</div>
            <div class="d-flex align-center ga-2 mt-1">
              <v-avatar size="24">
                <v-img :src="`https://q1.qlogo.cn/g?b=qq&nk=${feedback.user_id}&s=40`" />
              </v-avatar>
              <span class="text-body-2">{{ feedback.user_id }}</span>
            </div>
          </v-col>
          <v-col cols="6">
            <div class="text-caption text-medium-emphasis">来源</div>
            <div class="text-body-2 font-weight-medium">{{ sourceLabel(feedback.source) }}</div>
          </v-col>
          <v-col cols="6">
            <div class="text-caption text-medium-emphasis">类型</div>
            <v-chip :color="typeColor(feedback.feedback_type)" size="small" variant="elevated">
              {{ feedback.feedback_type || '未分类' }}
            </v-chip>
          </v-col>
          <v-col cols="6">
            <div class="text-caption text-medium-emphasis">状态</div>
            <v-chip :color="statusColor(feedback.status)" size="small" variant="elevated">
              {{ statusLabel(feedback.status) }}
            </v-chip>
          </v-col>
          <v-col cols="12">
            <div class="text-caption text-medium-emphasis">提交时间</div>
            <div class="text-body-2">{{ formatTime(feedback.created_at) }}</div>
          </v-col>
          <v-col v-if="feedback.processed_at" cols="12">
            <div class="text-caption text-medium-emphasis">处理时间</div>
            <div class="text-body-2">{{ formatTime(feedback.processed_at) }}</div>
          </v-col>
        </v-row>

        <v-divider class="my-4" />

        <div class="text-subtitle-2 mb-2">反馈内容</div>
        <v-card variant="elevated" class="pa-3 mb-4">
          <div class="text-body-2">{{ feedback.content }}</div>
        </v-card>

        <div v-if="feedback.admin_reply" class="mb-4">
          <div class="text-subtitle-2 mb-2">管理员回复</div>
          <v-card variant="elevated" color="blue-lighten-5" class="pa-3">
            <div class="text-body-2">{{ feedback.admin_reply }}</div>
          </v-card>
        </div>

        <v-divider class="my-4" />

        <div class="text-subtitle-2 mb-2">管理操作</div>
        <v-select
          v-model="editStatus"
          :items="statusOptions"
          label="状态"
          density="compact"
          variant="outlined"
          class="mb-3"
        />
        <v-textarea
          v-model="editReply"
          label="管理员回复"
          density="compact"
          variant="outlined"
          rows="4"
          class="mb-3"
        />
        <v-alert
          v-if="updateError"
          type="error"
          density="compact"
          class="mb-3"
          closable
          @click:close="updateError = null"
        >
          {{ updateError }}
        </v-alert>
        <v-btn
          block
          variant="elevated"
          color="primary"
          :loading="updateLoading"
          @click="saveAndNotify"
        >
          保存并通知用户
        </v-btn>
      </v-card-text>
    </v-card>
  </v-navigation-drawer>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import * as feedbackApi from '@/apis/feedback'
import type { Feedback } from '@/apis/feedback'
import { formatTime } from '@/utils/format'
import { statusOptions, statusColor, statusLabel, sourceLabel, typeColor } from '@/utils/feedback'

const props = defineProps<{
  modelValue: boolean
  feedback: Feedback | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  saved: []
}>()

const editStatus = ref('')
const editReply = ref('')
const updateLoading = ref(false)
const updateError = ref<string | null>(null)

watch(
  () => props.feedback,
  (fb) => {
    if (fb) {
      editStatus.value = fb.status
      editReply.value = fb.admin_reply || ''
    }
  },
  { immediate: true },
)

async function saveAndNotify() {
  if (!props.feedback) return
  updateLoading.value = true
  updateError.value = null
  try {
    await feedbackApi.updateStatus(props.feedback.id, {
      status: editStatus.value,
      admin_reply: editReply.value || null,
    })
    emit('update:modelValue', false)
    emit('saved')
  } catch (e: unknown) {
    // 更新失败时保持抽屉打开，用户可重试
    updateError.value = e instanceof Error ? e.message : '更新失败，请重试'
  } finally {
    updateLoading.value = false
  }
}
</script>
