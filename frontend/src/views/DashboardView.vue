<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <h1 class="text-h4 font-weight-bold mb-1">仪表盘</h1>
        <p class="text-body-2 text-medium-emphasis">Texas 机器人管理面板概览</p>
      </v-col>
    </v-row>

    <v-row>
      <!-- 机器人状态卡片 -->
      <v-col cols="12" sm="6" md="4">
        <v-card variant="tonal" :color="botStore.online ? 'success' : 'grey'" class="pa-4">
          <div class="d-flex align-center ga-2 mb-2">
            <v-icon :color="botStore.online ? 'success' : 'grey'">mdi-robot</v-icon>
            <span class="text-subtitle-2">机器人状态</span>
          </div>
          <div class="text-h5 font-weight-bold">
            {{ botStore.online ? '在线' : '离线' }}
          </div>
          <div class="text-caption text-medium-emphasis mt-1">
            {{ botStore.nickname ?? '未连接' }}
            <span v-if="botStore.userId"> ({{ botStore.userId }})</span>
          </div>
        </v-card>
      </v-col>

      <!-- 同步状态卡片 -->
      <v-col cols="12" sm="6" md="4">
        <v-card variant="tonal" :color="syncStatusColor" class="pa-4">
          <div class="d-flex align-center ga-2 mb-2">
            <v-icon :color="syncStatusColor">mdi-sync</v-icon>
            <span class="text-subtitle-2">数据同步</span>
          </div>
          <div class="text-h5 font-weight-bold">{{ syncStatusLabel }}</div>
          <div class="text-caption text-medium-emphasis mt-1">
            {{ personnelStore.syncStatus?.last_sync_time
              ? `上次: ${formatTime(personnelStore.syncStatus.last_sync_time)}`
              : '尚未同步' }}
          </div>
        </v-card>
      </v-col>

      <!-- 数据概况 -->
      <v-col cols="12" sm="6" md="4">
        <v-card variant="tonal" color="blue" class="pa-4">
          <div class="d-flex align-center ga-2 mb-2">
            <v-icon color="blue">mdi-database</v-icon>
            <span class="text-subtitle-2">数据概况</span>
          </div>
          <div class="text-body-1">
            <span class="font-weight-bold">{{ personnelStore.syncStatus?.users_synced ?? '-' }}</span> 用户 ·
            <span class="font-weight-bold">{{ personnelStore.syncStatus?.groups_synced ?? '-' }}</span> 群聊
          </div>
          <div class="text-caption text-medium-emphasis mt-1">
            {{ personnelStore.syncStatus?.memberships_synced ?? '-' }} 条成员关系
          </div>
        </v-card>
      </v-col>
    </v-row>

    <!-- 快捷入口 -->
    <v-row class="mt-2">
      <v-col cols="12">
        <div class="text-subtitle-1 font-weight-medium mb-2">快捷入口</div>
      </v-col>
      <v-col cols="6" sm="3" v-for="shortcut in shortcuts" :key="shortcut.to">
        <v-card
          :to="shortcut.to"
          variant="outlined"
          hover
          class="pa-4 text-center"
        >
          <v-icon :color="shortcut.color" size="32">{{ shortcut.icon }}</v-icon>
          <div class="text-body-2 mt-2">{{ shortcut.label }}</div>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useBotStore } from '@/stores/bot'
import { usePersonnelStore } from '@/stores/personnel'

const botStore = useBotStore()
const personnelStore = usePersonnelStore()

const shortcuts = [
  { label: '用户管理', icon: 'mdi-account-group', color: 'blue', to: '/personnel' },
  { label: '群聊管理', icon: 'mdi-forum', color: 'green', to: '/personnel' },
  { label: '管理员设置', icon: 'mdi-shield-account', color: 'red', to: '/personnel' },
  { label: '数据同步', icon: 'mdi-sync', color: 'purple', to: '/personnel' },
]

const syncStatusColor = computed(() => {
  const s = personnelStore.syncStatus?.status
  if (s === 'success') return 'success'
  if (s === 'running') return 'info'
  if (s === 'failure') return 'error'
  return 'grey'
})

const syncStatusLabel = computed(() => {
  const map: Record<string, string> = {
    success: '同步成功',
    running: '同步中…',
    failure: '同步失败',
    never: '从未同步',
  }
  return map[personnelStore.syncStatus?.status ?? ''] ?? '未知'
})

function formatTime(iso: string) {
  try {
    return new Date(iso).toLocaleString('zh-CN')
  } catch {
    return iso
  }
}

onMounted(() => {
  personnelStore.loadSyncStatus()
})
</script>

