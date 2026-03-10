<template>
  <v-container fluid class="pa-6">
    <div class="d-flex align-center mb-6">
      <div>
        <h1 class="text-h4 font-weight-bold">消息概览</h1>
        <p class="text-body-2 text-medium-emphasis mt-1">聊天记录统计与数据概览</p>
      </div>
      <v-spacer></v-spacer>
      <v-btn
        variant="tonal"
        color="primary"
        prepend-icon="mdi-refresh"
        :loading="store.overviewLoading"
        @click="refreshAll"
      >
        刷新
      </v-btn>
    </div>

    <!-- 统计卡片 -->
    <v-row class="mb-6">
      <v-col cols="12" sm="6" lg="3">
        <v-card rounded="lg" elevation="2">
          <v-card-text class="d-flex align-center pa-5">
            <v-avatar color="blue-lighten-4" size="56" class="mr-4">
              <v-icon color="blue" size="28">mdi-message-text</v-icon>
            </v-avatar>
            <div>
              <div class="text-h5 font-weight-bold">{{ formatNumber(store.overview.total_messages) }}</div>
              <div class="text-body-2 text-medium-emphasis">总消息数</div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" sm="6" lg="3">
        <v-card rounded="lg" elevation="2">
          <v-card-text class="d-flex align-center pa-5">
            <v-avatar color="green-lighten-4" size="56" class="mr-4">
              <v-icon color="green" size="28">mdi-trending-up</v-icon>
            </v-avatar>
            <div>
              <div class="text-h5 font-weight-bold">+{{ formatNumber(store.overview.today_messages) }}</div>
              <div class="text-body-2 text-medium-emphasis">今日新增</div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" sm="6" lg="3">
        <v-card rounded="lg" elevation="2">
          <v-card-text class="d-flex align-center pa-5">
            <v-avatar color="orange-lighten-4" size="56" class="mr-4">
              <v-icon color="orange" size="28">mdi-account-group</v-icon>
            </v-avatar>
            <div>
              <div class="text-h5 font-weight-bold">{{ store.overview.active_groups }}</div>
              <div class="text-body-2 text-medium-emphasis">活跃群数</div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" sm="6" lg="3">
        <v-card rounded="lg" elevation="2">
          <v-card-text class="d-flex align-center pa-5">
            <v-avatar color="purple-lighten-4" size="56" class="mr-4">
              <v-icon color="purple" size="28">mdi-account</v-icon>
            </v-avatar>
            <div>
              <div class="text-h5 font-weight-bold">{{ formatNumber(store.overview.active_users) }}</div>
              <div class="text-body-2 text-medium-emphasis">活跃用户</div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-row>
      <!-- 消息趋势（占位） -->
      <v-col cols="12" lg="8">
        <v-card rounded="lg" elevation="2">
          <v-card-title class="d-flex align-center">
            <v-icon class="mr-2">mdi-chart-line</v-icon>
            消息趋势（近 {{ trendDays }} 天）
            <v-spacer></v-spacer>
            <v-btn-toggle v-model="trendDays" density="compact" mandatory color="primary" variant="outlined">
              <v-btn :value="7" size="small">7天</v-btn>
              <v-btn :value="30" size="small">30天</v-btn>
              <v-btn :value="90" size="small">90天</v-btn>
            </v-btn-toggle>
          </v-card-title>
          <v-card-text>
            <div v-if="store.trendLoading" class="d-flex justify-center align-center" style="height: 240px;">
              <v-progress-circular indeterminate color="primary"></v-progress-circular>
            </div>
            <div v-else-if="store.trend.length > 0" style="height: 240px;">
              <!-- 简易文本柱状图（待集成图表库） -->
              <div class="d-flex flex-column ga-1 overflow-y-auto" style="max-height: 240px;">
                <div v-for="item in store.trend" :key="item.period" class="d-flex align-center ga-2">
                  <span class="text-caption text-medium-emphasis" style="min-width: 80px;">
                    {{ item.period.slice(0, 10) }}
                  </span>
                  <v-progress-linear
                    :model-value="(item.count / maxTrendCount) * 100"
                    color="blue"
                    height="16"
                    rounded
                  >
                    <template #default>
                      <span class="text-caption">{{ formatNumber(item.count) }}</span>
                    </template>
                  </v-progress-linear>
                </div>
              </div>
            </div>
            <div v-else class="d-flex justify-center align-center text-medium-emphasis" style="height: 240px;">
              暂无趋势数据
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <!-- 消息类型分布 -->
      <v-col cols="12" lg="4">
        <v-card rounded="lg" elevation="2" style="height: 100%;">
          <v-card-title>
            <v-icon class="mr-2">mdi-chart-pie</v-icon>
            消息类型分布
          </v-card-title>
          <v-card-text>
            <v-list density="compact">
              <v-list-item v-for="(count, type) in stats.type_distribution" :key="type">
                <template #prepend>
                  <v-icon :color="getTypeColor(Number(type))">{{ getTypeIcon(Number(type)) }}</v-icon>
                </template>
                <v-list-item-title>{{ getTypeName(Number(type)) }}</v-list-item-title>
                <template #append>
                  <v-chip size="small" variant="tonal" :color="getTypeColor(Number(type))">
                    {{ formatNumber(count) }}
                  </v-chip>
                </template>
              </v-list-item>
              <v-list-item v-if="Object.keys(stats.type_distribution).length === 0">
                <v-list-item-title class="text-medium-emphasis">暂无数据</v-list-item-title>
              </v-list-item>
            </v-list>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-row class="mt-2">
      <!-- 群消息排行 -->
      <v-col cols="12" lg="6">
        <v-card rounded="lg" elevation="2">
          <v-card-title>
            <v-icon class="mr-2">mdi-podium</v-icon>
            群消息排行（近 30 天）
          </v-card-title>
          <v-card-text>
            <v-table density="compact" v-if="store.groupRanking.length > 0">
              <thead>
                <tr>
                  <th>排名</th>
                  <th>群号</th>
                  <th>消息数</th>
                  <th>活跃成员</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(item, index) in store.groupRanking" :key="item.group_id">
                  <td>
                    <v-chip
                      size="x-small"
                      :color="index < 3 ? ['amber', 'grey', 'brown'][index] : 'default'"
                      variant="flat"
                    >
                      #{{ index + 1 }}
                    </v-chip>
                  </td>
                  <td>{{ item.group_id }}</td>
                  <td>{{ formatNumber(item.message_count) }}</td>
                  <td>{{ item.active_members }}</td>
                </tr>
              </tbody>
            </v-table>
            <div v-else class="text-center text-medium-emphasis pa-4">暂无数据</div>
          </v-card-text>
        </v-card>
      </v-col>

      <!-- 用户消息排行 -->
      <v-col cols="12" lg="6">
        <v-card rounded="lg" elevation="2">
          <v-card-title>
            <v-icon class="mr-2">mdi-account-star</v-icon>
            用户消息排行（近 30 天）
          </v-card-title>
          <v-card-text>
            <v-table density="compact" v-if="store.userRanking.length > 0">
              <thead>
                <tr>
                  <th>排名</th>
                  <th>昵称</th>
                  <th>QQ</th>
                  <th>消息数</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(item, index) in store.userRanking" :key="item.user_id">
                  <td>
                    <v-chip
                      size="x-small"
                      :color="index < 3 ? ['amber', 'grey', 'brown'][index] : 'default'"
                      variant="flat"
                    >
                      #{{ index + 1 }}
                    </v-chip>
                  </td>
                  <td>{{ item.nickname || '-' }}</td>
                  <td>{{ item.user_id }}</td>
                  <td>{{ formatNumber(item.message_count) }}</td>
                </tr>
              </tbody>
            </v-table>
            <div v-else class="text-center text-medium-emphasis pa-4">暂无数据</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- 时段热力图（占位） -->
    <v-row class="mt-2">
      <v-col cols="12">
        <v-card rounded="lg" elevation="2">
          <v-card-title>
            <v-icon class="mr-2">mdi-grid</v-icon>
            时段热力图（近 90 天）
          </v-card-title>
          <v-card-text>
            <div v-if="store.heatmap.length > 0">
              <!-- 简易热力图：使用表格 + 背景色 -->
              <div class="overflow-x-auto">
                <table class="heatmap-table">
                  <thead>
                    <tr>
                      <th></th>
                      <th v-for="h in 24" :key="h" class="text-caption text-center">{{ h - 1 }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="d in 7" :key="d">
                      <td class="text-caption text-medium-emphasis" style="min-width: 40px;">
                        {{ dayNames[d - 1] }}
                      </td>
                      <td
                        v-for="h in 24"
                        :key="h"
                        class="heatmap-cell"
                        :style="{ backgroundColor: getHeatmapColor(getHeatmapValue(d - 1, h - 1)) }"
                        :title="`${dayNames[d - 1]} ${h - 1}:00 — ${getHeatmapValue(d - 1, h - 1)} 条`"
                      ></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
            <div v-else class="text-center text-medium-emphasis pa-4">暂无热力图数据</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useChatStore } from '@/stores/chat'
import { fetchStats } from '@/services/chat'
import type { MessageStats } from '@/services/chat'

const store = useChatStore()

const trendDays = ref(30)
const stats = ref<MessageStats>({ type_distribution: {}, daily_counts: [] })
const dayNames = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

const maxTrendCount = computed(() => {
  if (store.trend.length === 0) return 1
  return Math.max(...store.trend.map((t) => t.count), 1)
})

function formatNumber(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}

function getTypeName(type: number): string {
  const names: Record<number, string> = { 1: '私聊', 2: '群聊', 3: '自发消息' }
  return names[type] ?? `类型${type}`
}

function getTypeIcon(type: number): string {
  const icons: Record<number, string> = {
    1: 'mdi-account',
    2: 'mdi-account-group',
    3: 'mdi-robot',
  }
  return icons[type] ?? 'mdi-message'
}

function getTypeColor(type: number): string {
  const colors: Record<number, string> = { 1: 'blue', 2: 'green', 3: 'orange' }
  return colors[type] ?? 'grey'
}

// ── 热力图辅助 ──

function getHeatmapValue(day: number, hour: number): number {
  const item = store.heatmap.find((h) => h.day_of_week === day && h.hour === hour)
  return item?.count ?? 0
}

const maxHeatmapCount = computed(() => {
  if (store.heatmap.length === 0) return 1
  return Math.max(...store.heatmap.map((h) => h.count), 1)
})

function getHeatmapColor(count: number): string {
  if (count === 0) return 'rgba(0, 0, 0, 0.04)'
  const intensity = Math.min(count / maxHeatmapCount.value, 1)
  const r = Math.round(229 - intensity * 180)
  const g = Math.round(229 - intensity * 200)
  const b = Math.round(229 + intensity * 26)
  return `rgb(${r}, ${g}, ${b})`
}

// ── 数据加载 ──

async function refreshAll() {
  await Promise.all([
    store.loadOverview(),
    store.loadTrend({ days: trendDays.value }),
    store.loadHeatmap(),
    store.loadGroupRanking(10),
    store.loadUserRanking({ limit: 10 }),
    loadStats(),
  ])
}

async function loadStats() {
  try {
    stats.value = await fetchStats()
  } catch {
    // 忽略统计加载失败
  }
}

watch(trendDays, (days) => {
  store.loadTrend({ days })
})

onMounted(() => {
  refreshAll()
})
</script>

<style scoped>
.heatmap-table {
  border-collapse: collapse;
  width: 100%;
}

.heatmap-cell {
  width: 28px;
  height: 20px;
  min-width: 28px;
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: 2px;
}
</style>

