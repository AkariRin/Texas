/** Bot 状态管理。 */

import { ref } from 'vue'
import { defineStore } from 'pinia'
import type { BotStatus } from '@/types/bot'
import { fetchBotStatus } from '@/api/bot'

export const useBotStore = defineStore('bot', () => {
  const status = ref<BotStatus | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function loadStatus() {
    loading.value = true
    error.value = null
    try {
      status.value = await fetchBotStatus()
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Unknown error'
    } finally {
      loading.value = false
    }
  }

  return { status, loading, error, loadStatus }
})

