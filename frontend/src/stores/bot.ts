import { ref } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'

export interface BotStatus {
  online: boolean
  nickname: string | null
  user_id: number | null
  avatar_url: string | null
}

export const useBotStore = defineStore('bot', () => {
  const online = ref(false)
  const nickname = ref<string | null>(null)
  const userId = ref<number | null>(null)
  const avatarUrl = ref<string | null>(null)
  const loading = ref(false)

  async function fetchStatus() {
    loading.value = true
    try {
      const { data } = await axios.get<{ code: number; data: BotStatus }>('/api/bot/status')
      if (data.code === 0) {
        online.value = data.data.online
        nickname.value = data.data.nickname
        userId.value = data.data.user_id
        avatarUrl.value = data.data.avatar_url
      }
    } catch {
      online.value = false
      nickname.value = null
      userId.value = null
      avatarUrl.value = null
    } finally {
      loading.value = false
    }
  }

  /** 启动定时轮询 */
  let timer: ReturnType<typeof setInterval> | null = null

  function startPolling(intervalMs = 15000) {
    stopPolling()
    fetchStatus()
    timer = setInterval(fetchStatus, intervalMs)
  }

  function stopPolling() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  return { online, nickname, userId, avatarUrl, loading, fetchStatus, startPolling, stopPolling }
})

