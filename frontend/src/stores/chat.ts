/**
 * Chat Pinia Store —— 管理聊天记录数据状态。
 */

import { ref } from 'vue'
import { defineStore } from 'pinia'
import * as api from '@/apis/chat'
import type { ChatMessage, ArchiveLog, PaginatedResult } from '@/apis/chat'

export const useChatStore = defineStore('chat', () => {
  // ── 消息列表 ──
  const messages = ref<ChatMessage[]>([])
  const messagesLoading = ref(false)
  const messagesError = ref<string | null>(null)
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
    messagesError.value = null
    try {
      const result = await api.fetchGroupMessages(groupId, params)
      if (params?.before) {
        // 追加更早的消息
        messages.value = [...messages.value, ...result]
      } else {
        messages.value = result
      }
      hasMore.value = result.length >= (params?.limit ?? 50)
    } catch (err) {
      messagesError.value = err instanceof Error ? err.message : '加载消息失败'
    } finally {
      messagesLoading.value = false
    }
  }

  async function loadPrivateMessages(userId: number, params?: { before?: string; limit?: number }) {
    messagesLoading.value = true
    messagesError.value = null
    try {
      const result = await api.fetchPrivateMessages(userId, params)
      if (params?.before) {
        messages.value = [...messages.value, ...result]
      } else {
        messages.value = result
      }
      hasMore.value = result.length >= (params?.limit ?? 50)
    } catch (err) {
      messagesError.value = err instanceof Error ? err.message : '加载消息失败'
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
    // 消息
    messages,
    messagesLoading,
    messagesError,
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
