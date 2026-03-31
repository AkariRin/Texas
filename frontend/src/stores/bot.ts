import { ref } from 'vue'
import { defineStore } from 'pinia'
import http from '@/apis/client'
import { getBotInfo } from '@/apis/bot'

export interface HealthStatus {
  status: string
  ws_connected: boolean
}

export const useBotStore = defineStore(
  'bot',
  () => {
    const online = ref(false)
    const nickname = ref<string | null>(null)
    const userId = ref<number | null>(null)
    const avatarUrl = ref<string | null>(null)
    const loading = ref(false)

    // 非响应式变量：仅用于逻辑比较，无需触发视图更新，不持久化
    let prevOnline = false

    async function fetchHealth() {
      try {
        const { data } = await http.get<HealthStatus>('/health')
        online.value = data.ws_connected
      } catch {
        online.value = false
      }
    }

    async function fetchBotInfo() {
      try {
        const { data } = await getBotInfo()
        if (data.code === 0) {
          nickname.value = data.data.nickname
          userId.value = data.data.user_id
          avatarUrl.value = data.data.avatar_url
        }
      } catch {
        // 获取失败时不清空缓存，保留上次的信息
      }
    }

    async function fetchStatus() {
      loading.value = true
      try {
        await fetchHealth()
        if (online.value) {
          // 首次上线或重连时重新获取 Bot 信息
          if (!prevOnline || nickname.value === null) {
            await fetchBotInfo()
          }
        }
        // 离线时保留已缓存的昵称、QQ号和头像，不做清空
        prevOnline = online.value
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
  },
  {
    persist: {
      // 仅持久化 Bot 显示信息，离线或刷新页面后仍可展示
      pick: ['nickname', 'userId', 'avatarUrl'],
    },
  },
)
