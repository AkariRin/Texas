<template>
  <v-card flat>
    <v-card-title class="d-flex align-center ga-2">
      <v-icon start>mdi-sync</v-icon>
      <span>数据同步</span>
      <v-spacer />
      <v-btn
        color="red"
        variant="tonal"
        prepend-icon="mdi-sync"
        :loading="store.syncLoading"
        @click="triggerSync"
      >
        手动同步
      </v-btn>
      <v-btn
        icon
        size="small"
        variant="text"
        class="ml-1"
        @click="refresh"
      >
        <v-icon>mdi-refresh</v-icon>
        <v-tooltip activator="parent" location="top">刷新状态</v-tooltip>
      </v-btn>
    </v-card-title>

    <v-card-text>
      <v-row v-if="status">
        <!-- 同步状态卡片 -->
        <v-col cols="12" sm="6" md="4">
          <v-card variant="tonal" :color="statusColor" class="pa-4">
            <div class="d-flex align-center ga-2 mb-2">
              <v-icon :color="statusColor">{{ statusIcon }}</v-icon>
              <span class="text-subtitle-2">同步状态</span>
            </div>
            <div class="text-h5 font-weight-bold">{{ statusLabel }}</div>
          </v-card>
        </v-col>

        <!-- 最后同步时间 -->
        <v-col cols="12" sm="6" md="4">
          <v-card variant="tonal" color="blue-grey" class="pa-4">
            <div class="d-flex align-center ga-2 mb-2">
              <v-icon color="blue-grey">mdi-clock-outline</v-icon>
              <span class="text-subtitle-2">最后同步时间</span>
            </div>
            <div class="text-h6 font-weight-medium">
              {{ status.last_sync_time ? formatTime(status.last_sync_time) : '从未同步' }}
            </div>
          </v-card>
        </v-col>

        <!-- 同步耗时 -->
        <v-col cols="12" sm="6" md="4">
          <v-card variant="tonal" color="purple" class="pa-4">
            <div class="d-flex align-center ga-2 mb-2">
              <v-icon color="purple">mdi-timer-outline</v-icon>
              <span class="text-subtitle-2">同步耗时</span>
            </div>
            <div class="text-h6 font-weight-medium">
              {{ status.duration_seconds != null ? `${status.duration_seconds.toFixed(2)} 秒` : '-' }}
            </div>
          </v-card>
        </v-col>

        <!-- 同步数据统计 -->
        <v-col cols="12">
          <v-card variant="outlined" class="pa-4">
            <div class="text-subtitle-2 mb-3">最近一次同步统计</div>
            <v-row dense>
              <v-col cols="12" sm="4">
                <div class="d-flex align-center ga-2">
                  <v-icon color="blue" size="20">mdi-account-group</v-icon>
                  <span class="text-body-2 text-medium-emphasis">同步用户数</span>
                </div>
                <div class="text-h5 font-weight-bold mt-1">{{ status.users_synced }}</div>
              </v-col>
              <v-col cols="12" sm="4">
                <div class="d-flex align-center ga-2">
                  <v-icon color="green" size="20">mdi-forum</v-icon>
                  <span class="text-body-2 text-medium-emphasis">同步群聊数</span>
                </div>
                <div class="text-h5 font-weight-bold mt-1">{{ status.groups_synced }}</div>
              </v-col>
              <v-col cols="12" sm="4">
                <div class="d-flex align-center ga-2">
                  <v-icon color="orange" size="20">mdi-link-variant</v-icon>
                  <span class="text-body-2 text-medium-emphasis">同步成员关系数</span>
                </div>
                <div class="text-h5 font-weight-bold mt-1">{{ status.memberships_synced }}</div>
              </v-col>
            </v-row>
          </v-card>
        </v-col>
      </v-row>

      <!-- 加载中 -->
      <div v-else class="text-center pa-8">
        <v-progress-circular indeterminate color="red" />
        <div class="text-caption mt-2 text-medium-emphasis">加载同步状态…</div>
      </div>
    </v-card-text>

    <!-- 提示 snackbar -->
    <v-snackbar v-model="snackbar" :color="snackColor" :timeout="3000" location="top">
      {{ snackText }}
    </v-snackbar>
  </v-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { usePersonnelStore } from '@/stores/personnel'

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
    running: '同步中…',
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

function refresh() {
  store.loadSyncStatus()
}

onMounted(() => store.loadSyncStatus())
</script>

