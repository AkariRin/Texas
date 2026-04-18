<template>
  <PageLayout>
    <!-- 群号选择器 -->
    <v-row class="mb-4" align="center">
      <v-col cols="12" sm="4" md="3">
        <v-text-field
          v-model.number="groupId"
          label="群号"
          density="compact"
          variant="solo-filled"
          hide-details
          clearable
          type="number"
          prepend-inner-icon="mdi-account-group"
          @update:model-value="onGroupChange"
        />
      </v-col>
    </v-row>

    <!-- 汇总卡片 -->
    <v-row class="mb-6">
      <v-col v-for="card in summaryCards" :key="card.label" cols="12" sm="4">
        <v-card variant="tonal" :color="card.color">
          <v-card-text>
            <div class="text-caption text-medium-emphasis">{{ card.label }}</div>
            <div class="text-h4 font-weight-bold mt-1">
              <span v-if="summaryLoading">—</span>
              <span v-else>{{ card.value }}</span>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- 排行榜 -->
    <v-card flat class="mb-6">
      <v-card-title class="d-flex align-center ga-2">
        排行榜
        <v-btn-toggle v-model="leaderBy" density="compact" variant="outlined" mandatory>
          <v-btn value="total" size="small">累计榜</v-btn>
          <v-btn value="streak" size="small">连续榜</v-btn>
        </v-btn-toggle>
      </v-card-title>
      <v-skeleton-loader v-if="leaderLoading" type="list-item-two-line@5" class="pa-2" />
      <v-list v-else lines="one" density="compact">
        <v-list-item
          v-for="entry in leaderboard"
          :key="entry.user_id"
          :subtitle="`${personnelStore.getUserName(entry.user_id)}（${entry.user_id}）`"
        >
          <template #prepend>
            <v-avatar size="32" class="mr-2">
              <v-img :src="`https://q1.qlogo.cn/g?b=qq&nk=${entry.user_id}&s=40`">
                <template #error><v-icon>mdi-account-circle</v-icon></template>
              </v-img>
            </v-avatar>
            <v-chip size="x-small" :color="rankColor(entry.rank)" class="mr-2">
              {{ entry.rank }}
            </v-chip>
          </template>
          <template #append>
            <span class="text-body-2 font-weight-medium"> {{ entry.value }} 天 </span>
          </template>
        </v-list-item>
        <v-list-item v-if="!leaderboard.length && !leaderLoading">
          <v-list-item-title class="text-medium-emphasis">暂无数据</v-list-item-title>
        </v-list-item>
      </v-list>
    </v-card>

    <!-- 趋势图 -->
    <v-card flat>
      <v-card-title>签到趋势（近 30 天）</v-card-title>
      <v-card-text>
        <v-skeleton-loader v-if="trendLoading" type="image" height="120" />
        <div v-else-if="trendData.length" class="trend-chart">
          <v-sparkline
            :model-value="trendValues"
            :labels="trendLabels"
            type="trend"
            smooth
            color="primary"
            line-width="2"
            height="100"
            padding="8"
            auto-line-width
          />
        </div>
        <div v-else class="text-medium-emphasis text-caption pa-4">暂无趋势数据</div>
      </v-card-text>
    </v-card>
  </PageLayout>
</template>

<script setup lang="ts">
/**
 * 签到统计面板 —— 展示指定群的签到汇总、排行榜与近 30 天趋势。
 */
import { computed, onMounted, ref, watch } from 'vue'

import * as checkinApi from '@/apis/checkin'
import type { DayCount, LeaderEntry, Summary } from '@/apis/checkin'
import PageLayout from '@/layouts/PageLayout.vue'
import { usePersonnelStore } from '@/stores/personnel'

const personnelStore = usePersonnelStore()

const groupId = ref<number | null>(null)

// ── 汇总卡片 ──
const summaryLoading = ref(false)
const summary = ref<Summary | null>(null)

const summaryCards = computed(() => [
  { label: '历史签到总人次', value: summary.value?.total_checkins ?? 0, color: 'primary' },
  { label: '今日签到人数', value: summary.value?.today_checkins ?? 0, color: 'success' },
  { label: '近 30 天活跃用户', value: summary.value?.active_users ?? 0, color: 'info' },
])

// ── 排行榜 ──
const leaderLoading = ref(false)
const leaderboard = ref<LeaderEntry[]>([])
const leaderBy = ref<'total' | 'streak'>('total')

function rankColor(rank: number): string {
  if (rank === 1) return 'warning'
  if (rank === 2) return 'blue-grey'
  if (rank === 3) return 'deep-orange-lighten-2'
  return 'default'
}

// ── 趋势图 ──
const trendLoading = ref(false)
const trendData = ref<DayCount[]>([])

const trendValues = computed(() => trendData.value.map((d) => d.count))
// 每 7 天显示一个标签，避免拥挤
const trendLabels = computed(() =>
  trendData.value.map((d, i) => (i % 7 === 0 ? d.date.slice(5) : '')),
)

// ── 数据加载 ──
async function loadAll() {
  summaryLoading.value = true
  leaderLoading.value = true
  trendLoading.value = true

  await Promise.all([
    checkinApi
      .getSummary(groupId.value)
      .then((d) => {
        summary.value = d
      })
      .finally(() => {
        summaryLoading.value = false
      }),
    loadLeaderboard(),
    checkinApi
      .getDailyTrend(groupId.value)
      .then((d) => {
        trendData.value = d
      })
      .finally(() => {
        trendLoading.value = false
      }),
  ])
}

async function loadLeaderboard() {
  leaderLoading.value = true
  try {
    leaderboard.value = await checkinApi.getLeaderboard(groupId.value, leaderBy.value)
    const userIds = leaderboard.value.map((e) => e.user_id)
    personnelStore.prefetchIds(userIds, [])
  } finally {
    leaderLoading.value = false
  }
}

function onGroupChange() {
  loadAll()
}

watch(leaderBy, () => loadLeaderboard())

onMounted(() => loadAll())
</script>

<style scoped>
.trend-chart {
  min-height: 120px;
}
</style>
