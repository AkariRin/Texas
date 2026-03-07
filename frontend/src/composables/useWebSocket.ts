/** 用于实时仪表盘更新的 WebSocket 组合式函数。 */

import { ref, onMounted, onUnmounted } from 'vue'

export function useWebSocket(url: string) {
  const connected = ref(false)
  const lastMessage = ref<unknown>(null)
  const error = ref<string | null>(null)

  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  const RECONNECT_DELAY = 3000

  function connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}${url}`

    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      connected.value = true
      error.value = null
    }

    ws.onmessage = (event: MessageEvent) => {
      try {
        lastMessage.value = JSON.parse(event.data as string)
      } catch {
        lastMessage.value = event.data
      }
    }

    ws.onclose = () => {
      connected.value = false
      scheduleReconnect()
    }

    ws.onerror = () => {
      error.value = 'WebSocket 连接错误'
      connected.value = false
    }
  }

  function scheduleReconnect() {
    if (reconnectTimer) return
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      connect()
    }, RECONNECT_DELAY)
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    ws?.close()
    ws = null
  }

  onMounted(connect)
  onUnmounted(disconnect)

  return { connected, lastMessage, error, disconnect }
}

