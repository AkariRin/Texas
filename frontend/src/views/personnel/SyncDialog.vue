<template>
  <v-dialog v-model="dialog" max-width="600">
    <v-card>
      <v-card-title class="d-flex align-center ga-2 pa-4">
        <v-icon color="red">mdi-sync</v-icon>
        <span>数据同步</span>
      </v-card-title>

      <v-divider />

      <v-card-text>
        <v-row v-if="status" class="mt-1">
          <!-- 同步状态 -->
          <v-col cols="12" sm="4">
            <v-card variant="elevated" :color="statusColor" class="pa-3">
              <div class="d-flex align-center ga-2 mb-1">
                <v-icon size="18">{{ statusIcon }}</v-icon>
                <span class="text-caption">同步状态</span>
              </div>
              <div class="text-h6 font-weight-bold">{{ statusLabel }}</div>
            </v-card>
          </v-col>

          <!-- 最后同步时间 -->
          <v-col cols="12" sm="8">
            <v-card variant="elevated" color="blue-grey" class="pa-3">
              <div class="d-flex align-center ga-2 mb-1">
                <v-icon size="18">mdi-clock-outline</v-icon>
                <span class="text-caption">最后同步时间</span>
              </div>
              <div class="text-body-1 font-weight-medium">
                {{ status.last_sync_time ? formatTime(status.last_sync_time) : '从未同步' }}
                <span
                  v-if="status.duration_seconds != null"
                  class="text-caption text-medium-emphasis ml-2"
                >
                  耗时 {{ status.duration_seconds.toFixed(2) }} 秒
                </span>
              </div>
            </v-card>
          </v-col>

          <!-- 同步统计 -->
          <v-col cols="12">
            <v-card variant="elevated" class="pa-3">
              <div class="text-caption text-medium-emphasis mb-2">最近一次同步统计</div>
              <v-row dense>
                <v-col cols="4">
                  <div class="d-flex align-center ga-1 mb-1">
                    <v-icon color="blue" size="16">mdi-account-group</v-icon>
                    <span class="text-caption text-medium-emphasis">用户</span>
                  </div>
                  <div class="text-h6 font-weight-bold">{{ status.users_synced }}</div>
                </v-col>
                <v-col cols="4">
                  <div class="d-flex align-center ga-1 mb-1">
                    <v-icon color="green" size="16">mdi-forum</v-icon>
                    <span class="text-caption text-medium-emphasis">群聊</span>
                  </div>
                  <div class="text-h6 font-weight-bold">{{ status.groups_synced }}</div>
                </v-col>
                <v-col cols="4">
                  <div class="d-flex align-center ga-1 mb-1">
                    <v-icon color="orange" size="16">mdi-link-variant</v-icon>
                    <span class="text-caption text-medium-emphasis">成员关系</span>
                  </div>
                  <div class="text-h6 font-weight-bold">{{ status.memberships_synced }}</div>
                </v-col>
              </v-row>
            </v-card>
          </v-col>
        </v-row>

        <!-- 加载中 -->
        <v-row v-else class="mt-1">
          <v-col cols="12" sm="4">
            <v-skeleton-loader type="text, heading" elevation="1" rounded="lg" />
          </v-col>
          <v-col cols="12" sm="8">
            <v-skeleton-loader type="text, heading" elevation="1" rounded="lg" />
          </v-col>
          <v-col cols="12">
            <v-skeleton-loader type="text, list-item-three-line" elevation="1" rounded="lg" />
          </v-col>
        </v-row>
      </v-card-text>

      <v-card-actions>
        <v-btn
          color="red"
          variant="elevated"
          prepend-icon="mdi-sync"
          :loading="store.syncLoading"
          @click="triggerSync"
        >
          手动同步
        </v-btn>
        <v-btn color="blue-grey" variant="elevated" prepend-icon="mdi-refresh" @click="store.loadSyncStatus()">
          刷新
        </v-btn>
        <v-spacer />
        <v-btn variant="elevated" @click="dialog = false">关闭</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- 提示 snackbar -->
  <v-snackbar v-model="snackbar" :color="snackColor" :timeout="3000" location="bottom">
    {{ snackText }}
  </v-snackbar>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { usePersonnelStore } from '@/stores/personnel'

const dialog = defineModel<boolean>({ default: false })

const store = usePersonnelStore()

const snackbar = ref(false)
const snackText = ref('')
const snackColor = ref('success')

const status = computed(() => store.syncStatus)

const statusColor = computed(() => {
  const s = status.value?.status
  if (s === 'success') return 'success'
  if (s === 'running') return 'info'
  if (s === 'failure') return 'error'
  return 'grey'
})

const statusIcon = computed(() => {
  const s = status.value?.status
  if (s === 'success') return 'mdi-check-circle'
  if (s === 'running') return 'mdi-loading mdi-spin'
  if (s === 'failure') return 'mdi-alert-circle'
  return 'mdi-help-circle'
})

const statusLabel = computed(() => {
  const map: Record<string, string> = {
    success: '同步成功',
    running: '同步中...',
    failure: '同步失败',
    never: '从未同步',
  }
  return map[status.value?.status ?? ''] ?? '未知'
})

function formatTime(iso: string) {
  try {
    return new Date(iso).toLocaleString('zh-CN')
  } catch {
    return iso
  }
}

function showSnack(text: string, color = 'success') {
  snackText.value = text
  snackColor.value = color
  snackbar.value = true
}

async function triggerSync() {
  try {
    await store.doSync()
    showSnack('同步任务已触发，请稍后刷新查看结果')
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    const msg = err?.response?.data?.detail || '触发同步失败'
    showSnack(msg, 'error')
  }
}

watch(dialog, (open) => {
  if (open) {
    store.loadSyncStatus()
  }
})
</script>
