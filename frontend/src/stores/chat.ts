/**
 * Chat Pinia Store —— 管理聊天记录数据状态。
 */

import { ref } from 'vue'
import { defineStore } from 'pinia'
import * as api from '@/apis/chat'
import type {
  OverviewStats,
  TrendItem,
  HeatmapItem,
  GroupRankItem,
  UserRankItem,
  ChatMessage,
  ArchiveLog,
  PaginatedResult,
} from '@/apis/chat'

export const useChatStore = defineStore('chat', () => {
  // ── 概览 ──
  const overview = ref<OverviewStats>({
    total_messages: 0,
    today_messages: 0,
    active_groups: 0,
    active_users: 0,
  })
  const overviewLoading = ref(false)

  async function loadOverview(groupId?: number) {
    overviewLoading.value = true
    try {
      overview.value = await api.fetchOverview(groupId)
    } finally {
      overviewLoading.value = false
    }
  }

  // ── 趋势 ──
  const trend = ref<TrendItem[]>([])
  const trendLoading = ref(false)

  async function loadTrend(params?: { groupId?: number; granularity?: string; days?: number }) {
    trendLoading.value = true
    try {
      trend.value = await api.fetchTrend(params)
    } finally {
      trendLoading.value = false
    }
  }

  // ── 热力图 ──
  const heatmap = ref<HeatmapItem[]>([])

  async function loadHeatmap(groupId?: number) {
    heatmap.value = await api.fetchHeatmap(groupId)
  }

  // ── 排行榜 ──
  const groupRanking = ref<GroupRankItem[]>([])
  const userRanking = ref<UserRankItem[]>([])

  async function loadGroupRanking(limit?: number) {
    groupRanking.value = await api.fetchGroupRanking(limit)
  }

  async function loadUserRanking(params?: { groupId?: number; limit?: number }) {
    userRanking.value = await api.fetchUserRanking(params)
  }

  // ── 消息列表 ──
  const messages = ref<ChatMessage[]>([])
  const messagesLoading = ref(false)
  const hasMore = ref(true)

  async function loadGroupMessages(
    groupId: number,
    params?: {
      before?: string
      limit?: number
      keyword?: string
      userId?: number
      startDate?: string
      endDate?: string
    },
  ) {
    messagesLoading.value = true
    try {
      const result = await api.fetchGroupMessages(groupId, params)
      if (params?.before) {
        // 追加更早的消息
        messages.value = [...messages.value, ...result]
      } else {
        messages.value = result
      }
      hasMore.value = result.length >= (params?.limit ?? 50)
    } finally {
      messagesLoading.value = false
    }
  }

  async function loadPrivateMessages(userId: number, params?: { before?: string; limit?: number }) {
    messagesLoading.value = true
    try {
      const result = await api.fetchPrivateMessages(userId, params)
      if (params?.before) {
        messages.value = [...messages.value, ...result]
      } else {
        messages.value = result
      }
      hasMore.value = result.length >= (params?.limit ?? 50)
    } finally {
      messagesLoading.value = false
    }
  }

  function clearMessages() {
    messages.value = []
    hasMore.value = true
  }

  // ── 归档 ──
  const archives = ref<PaginatedResult<ArchiveLog>>({
    items: [],
    total: 0,
    page: 1,
    page_size: 20,
    pages: 0,
  })
  const archivesLoading = ref(false)

  async function loadArchives(page?: number, pageSize?: number) {
    archivesLoading.value = true
    try {
      archives.value = await api.fetchArchives(page, pageSize)
    } finally {
      archivesLoading.value = false
    }
  }

  async function doTriggerArchive(partitionName?: string) {
    return await api.triggerArchive(partitionName)
  }

  return {
    // 概览
    overview,
    overviewLoading,
    loadOverview,
    // 趋势
    trend,
    trendLoading,
    loadTrend,
    // 热力图
    heatmap,
    loadHeatmap,
    // 排行榜
    groupRanking,
    userRanking,
    loadGroupRanking,
    loadUserRanking,
    // 消息
    messages,
    messagesLoading,
    hasMore,
    loadGroupMessages,
    loadPrivateMessages,
    clearMessages,
    // 归档
    archives,
    archivesLoading,
    loadArchives,
    doTriggerArchive,
  }
})
