<template>
  <v-container fluid class="logs-container">
    <div class="logs-header d-flex align-center justify-space-between">
      <div>
        <h1 class="text-h4 font-weight-bold mb-1">应用日志</h1>
        <p class="text-body-2 text-medium-emphasis">实时日志流</p>
      </div>
      <div class="d-flex align-center ga-2">
        <v-chip
          :color="connected ? 'success' : 'error'"
          variant="tonal"
          size="small"
        >
          <v-icon start size="x-small" :icon="connected ? 'mdi-circle' : 'mdi-circle-outline'"></v-icon>
          {{ connected ? '已连接' : '已断开' }}
        </v-chip>
        <v-select
          v-model="level"
          :items="levels"
          density="compact"
          variant="outlined"
          hide-details
          style="max-width: 140px"
          label="级别"
        ></v-select>
        <v-tooltip text="自动滚动" location="bottom">
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              :icon="autoScroll ? 'mdi-arrow-down-bold' : 'mdi-arrow-down-bold-outline'"
              :color="autoScroll ? 'red' : undefined"
              variant="text"
              size="small"
              @click="autoScroll = !autoScroll"
            ></v-btn>
          </template>
        </v-tooltip>
        <v-tooltip text="清空" location="bottom">
          <template #activator="{ props }">
            <v-btn
              v-bind="props"
              icon="mdi-delete-outline"
              variant="text"
              size="small"
              @click="clearLogs"
            ></v-btn>
          </template>
        </v-tooltip>
      </div>
    </div>

    <v-card class="log-card" variant="flat">
      <div ref="logContainer" class="log-viewport" @scroll="onScroll">
        <div v-if="logs.length === 0" class="text-center text-medium-emphasis pa-8">
          <v-icon size="48" class="mb-2">mdi-text-box-search-outline</v-icon>
          <div>等待日志...</div>
        </div>
        <div
          v-for="(entry, idx) in logs"
          :key="idx"
          class="log-line"
          :class="`log-level-${entry.level.toLowerCase()}`"
        >
          <span class="log-time">{{ formatTime(entry.timestamp) }}</span>
          <span class="log-level" :class="`level-${entry.level.toLowerCase()}`">{{ padLevel(entry.level) }}</span>
          <span class="log-logger">{{ entry.logger }}</span>
          <span class="log-message">{{ entry.message }}</span>
        </div>
      </div>
    </v-card>
  </v-container>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'

interface LogEntry {
  timestamp: string
  level: string
  logger: string
  message: string
}

const MAX_LINES = 2000

const levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR']
const level = ref('DEBUG')
const autoScroll = ref(true)
const connected = ref(false)
const logs = ref<LogEntry[]>([])
const logContainer = ref<HTMLElement | null>(null)

let eventSource: EventSource | null = null

function connect() {
  disconnect()
  const url = `/api/logs?level=${encodeURIComponent(level.value)}`
  eventSource = new EventSource(url)

  eventSource.addEventListener('connected', () => {
    connected.value = true
  })

  eventSource.onmessage = (event) => {
    try {
      const entry: LogEntry = JSON.parse(event.data)
      logs.value.push(entry)
      // 限制最大行数
      if (logs.value.length > MAX_LINES) {
        logs.value = logs.value.slice(-MAX_LINES)
      }
      if (autoScroll.value) {
        nextTick(scrollToBottom)
      }
    } catch {
      // 忽略无法解析的消息
    }
  }

  eventSource.onerror = () => {
    connected.value = false
    // 自动重连（浏览器 EventSource 内建重连，此处仅更新状态）
  }
}

function disconnect() {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
  connected.value = false
}

function clearLogs() {
  logs.value = []
}

function scrollToBottom() {
  const el = logContainer.value
  if (el) {
    el.scrollTop = el.scrollHeight
  }
}

function onScroll() {
  const el = logContainer.value
  if (!el) return
  // 如果用户向上滚动，关闭自动滚动
  autoScroll.value = el.scrollHeight - el.scrollTop - el.clientHeight < 40
}

function formatTime(ts: string): string {
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString('zh-CN', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
      + '.' + String(d.getMilliseconds()).padStart(3, '0')
  } catch {
    return ts
  }
}

function padLevel(lvl: string): string {
  return lvl.padEnd(7)
}

// 切换级别时重连
watch(level, () => {
  connect()
})

onMounted(() => {
  connect()
})

onUnmounted(() => {
  disconnect()
})
</script>

<style scoped>
.logs-container {
  height: calc(100vh - 64px);
  display: flex;
  flex-direction: column;
  padding: 16px !important;
  overflow: hidden;
}

.logs-header {
  flex-shrink: 0;
  margin-bottom: 12px;
}

.log-card {
  flex: 1;
  min-height: 0;
  background: #0d1117 !important;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.log-viewport {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Consolas', monospace;
  font-size: 12.5px;
  line-height: 1.65;
}

/* 滚动条 */
.log-viewport::-webkit-scrollbar {
  width: 6px;
}
.log-viewport::-webkit-scrollbar-track {
  background: transparent;
}
.log-viewport::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 3px;
}

.log-line {
  white-space: pre-wrap;
  word-break: break-all;
  padding: 1px 0;
  display: flex;
  gap: 12px;
}

.log-time {
  color: #6e7681;
  flex-shrink: 0;
}

.log-level {
  flex-shrink: 0;
  font-weight: 600;
  min-width: 60px;
}

.level-debug { color: #8b949e; }
.level-info { color: #58a6ff; }
.level-warning { color: #d29922; }
.level-error { color: #f85149; }
.level-critical { color: #ff7b72; font-weight: 800; }
.level-trace { color: #6e7681; }

.log-logger {
  color: #7ee787;
  flex-shrink: 0;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.log-message {
  color: #c9d1d9;
  flex: 1;
}

/* 行悬停高亮 */
.log-line:hover {
  background: rgba(255, 255, 255, 0.04);
}

/* 级别行背景 */
.log-level-error {
  background: rgba(248, 81, 73, 0.06);
}
.log-level-warning {
  background: rgba(210, 153, 34, 0.04);
}
</style>

