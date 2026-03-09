import { ref } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'

export interface HealthStatus {
  status: string
  ws_connected: boolean
}

export interface BotInfo {
  nickname: string | null
  user_id: number | null
  avatar_url: string | null
}

const BOT_CACHE_KEY = 'texas_bot_cache'

interface BotCache {
  nickname: string | null
  userId: number | null
  avatarUrl: string | null
}

function loadCache(): BotCache {
  try {
    const raw = localStorage.getItem(BOT_CACHE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as BotCache
      return {
        nickname: parsed.nickname ?? null,
        userId: parsed.userId ?? null,
        avatarUrl: parsed.avatarUrl ?? null,
      }
    }
  } catch {
    // 解析失败时忽略，使用默认值
  }
  return { nickname: null, userId: null, avatarUrl: null }
}

function saveCache(cache: BotCache) {
  try {
    localStorage.setItem(BOT_CACHE_KEY, JSON.stringify(cache))
  } catch {
    // 写入失败时忽略（如隐私模式下存储已满）
  }
}

export const useBotStore = defineStore('bot', () => {
  const cached = loadCache()
  const online = ref(false)
  const nickname = ref<string | null>(cached.nickname)
  const userId = ref<number | null>(cached.userId)
  const avatarUrl = ref<string | null>(cached.avatarUrl)
  const loading = ref(false)

  // 记录上一次的在线状态，用于检测重连
  let prevOnline = false

  async function fetchHealth() {
    try {
      const { data } = await axios.get<HealthStatus>('/health')
      online.value = data.ws_connected
    } catch {
      online.value = false
    }
  }

  async function fetchBotInfo() {
    try {
      const { data } = await axios.get<{ code: number; data: BotInfo }>('/api/bot/info')
      if (data.code === 0) {
        nickname.value = data.data.nickname
        userId.value = data.data.user_id
        avatarUrl.value = data.data.avatar_url
        // 持久化到 localStorage，离线或刷新页面后仍可显示
        saveCache({
          nickname: nickname.value,
          userId: userId.value,
          avatarUrl: avatarUrl.value,
        })
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
})

