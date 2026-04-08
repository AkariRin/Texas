<template>
  <PageLayout class="logs-container d-flex flex-column overflow-hidden">
    <template #actions>
      <div class="d-flex align-center ga-2">
        <v-chip :color="connected ? 'success' : 'error'" variant="elevated" size="small">
          <v-icon
            start
            size="x-small"
            :icon="connected ? 'mdi-circle' : 'mdi-circle-outline'"
          ></v-icon>
          {{ connected ? '已连接' : '已断开' }}
        </v-chip>
        <v-select
          v-model="level"
          :items="levels"
          density="compact"
          variant="solo-filled"
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
              variant="elevated"
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
              variant="elevated"
              size="small"
              @click="clearLogs"
            ></v-btn>
          </template>
        </v-tooltip>
      </div>
    </template>

    <v-card class="log-card flex-grow-1 d-flex flex-column overflow-hidden" variant="elevated">
      <div class="log-search-bar px-3 pt-2 pb-1">
        <v-text-field
          v-model="searchQuery"
          density="compact"
          variant="solo-filled"
          hide-details
          clearable
          prepend-inner-icon="mdi-magnify"
          placeholder="搜索日志..."
          class="log-search-input"
        ></v-text-field>
      </div>
      <div ref="logContainer" class="log-viewport flex-grow-1 overflow-y-auto" @scroll="onScroll">
        <div v-if="logs.length === 0" class="text-center pa-8 text-white">
          <v-icon size="48" class="mb-2" color="white">mdi-text-box-search-outline</v-icon>
          <div>等待日志...</div>
        </div>
        <div
          v-for="(entry, idx) in filteredLogs"
          :key="idx"
          class="log-line d-flex ga-3"
          :class="`log-level-${entry.level.toLowerCase()}`"
        >
          <span class="log-time">{{ formatTime(entry.timestamp) }}</span>
          <span class="log-level" :class="`level-${entry.level.toLowerCase()}`">{{
            padLevel(entry.level)
          }}</span>
          <span class="log-logger">{{ entry.logger }}</span>
          <span class="log-message">{{ entry.message }}</span>
        </div>
      </div>
    </v-card>
  </PageLayout>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import PageLayout from '@/layouts/PageLayout.vue'

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
const searchQuery = ref('')
const logContainer = ref<HTMLElement | null>(null)

const filteredLogs = computed(() => {
  if (!searchQuery.value) return logs.value
  const q = searchQuery.value.toLowerCase()
  return logs.value.filter(
    (e) =>
      e.message.toLowerCase().includes(q) ||
      e.logger.toLowerCase().includes(q) ||
      e.level.toLowerCase().includes(q) ||
      e.timestamp.toLowerCase().includes(q),
  )
})

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
    return (
      d.toLocaleTimeString('zh-CN', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      }) +
      '.' +
      String(d.getMilliseconds()).padStart(3, '0')
    )
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
  padding: 16px !important;
}

.log-card {
  min-height: 0;
  background: #0d1117 !important;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  border-radius: 8px;
}

.log-search-bar {
  flex-shrink: 0;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}

:deep(.log-search-input .v-field) {
  background: rgba(255, 255, 255, 0.05) !important;
  color: #c9d1d9 !important;
}

:deep(.log-search-input .v-field__outline) {
  --v-field-border-opacity: 0.2;
}

:deep(.log-search-input input::placeholder) {
  color: #6e7681 !important;
}

:deep(.log-search-input .v-icon) {
  color: #6e7681 !important;
}

.log-viewport {
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
  background: rgba(var(--v-theme-on-surface), 0.15);
  border-radius: 3px;
}

.log-line {
  white-space: pre-wrap;
  word-break: break-all;
  padding: 1px 0;
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

.level-debug {
  color: #8b949e;
}
.level-info {
  color: #58a6ff;
}
.level-warning {
  color: #d29922;
}
.level-error {
  color: #f85149;
}
.level-critical {
  color: #ff7b72;
  font-weight: 800;
}
.level-trace {
  color: #6e7681;
}

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
  background: rgba(var(--v-theme-on-surface), 0.04);
}

/* 级别行背景 */
.log-level-error {
  background: rgba(248, 81, 73, 0.06);
}
.log-level-warning {
  background: rgba(210, 153, 34, 0.04);
}
</style>
