<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <div class="d-flex align-center justify-space-between mb-1">
          <div>
            <h1 class="text-h4 font-weight-bold">任务队列</h1>
            <p class="text-body-2 text-medium-emphasis">查看定时任务调度与消息队列状态</p>
          </div>
          <v-btn
            color="red"
            variant="tonal"
            prepend-icon="mdi-refresh"
            :loading="store.loading"
            @click="store.loadAll()"
          >
            刷新
          </v-btn>
        </div>
      </v-col>
    </v-row>

    <!-- 概览卡片 -->
    <v-row>
      <v-col cols="12" sm="6" md="3">
        <v-card variant="tonal" color="purple" class="pa-4">
          <div class="d-flex align-center ga-2 mb-2">
            <v-icon color="purple">mdi-clock-outline</v-icon>
            <span class="text-subtitle-2">定时任务</span>
          </div>
          <div class="text-h5 font-weight-bold">{{ store.scheduledTasks.length }}</div>
          <div class="text-caption text-medium-emphasis mt-1">已注册的周期性任务</div>
        </v-card>
      </v-col>

      <v-col cols="12" sm="6" md="3">
        <v-card variant="tonal" :color="store.workers.length > 0 ? 'success' : 'grey'" class="pa-4">
          <div class="d-flex align-center ga-2 mb-2">
            <v-icon :color="store.workers.length > 0 ? 'success' : 'grey'">mdi-server</v-icon>
            <span class="text-subtitle-2">Worker 节点</span>
          </div>
          <div class="text-h5 font-weight-bold">{{ store.workers.length }}</div>
          <div class="text-caption text-medium-emphasis mt-1">
            {{ store.workers.length > 0 ? '在线' : '无在线节点' }}
          </div>
        </v-card>
      </v-col>

      <v-col cols="12" sm="6" md="3">
        <v-card variant="tonal" color="blue" class="pa-4">
          <div class="d-flex align-center ga-2 mb-2">
            <v-icon color="blue">mdi-run</v-icon>
            <span class="text-subtitle-2">执行中</span>
          </div>
          <div class="text-h5 font-weight-bold">{{ store.activeTasks.length }}</div>
          <div class="text-caption text-medium-emphasis mt-1">正在执行的任务</div>
        </v-card>
      </v-col>

      <v-col cols="12" sm="6" md="3">
        <v-card variant="tonal" color="orange" class="pa-4">
          <div class="d-flex align-center ga-2 mb-2">
            <v-icon color="orange">mdi-inbox-arrow-down</v-icon>
            <span class="text-subtitle-2">队列消息</span>
          </div>
          <div class="text-h5 font-weight-bold">
            {{ store.queueLength?.length ?? '-' }}
          </div>
          <div class="text-caption text-medium-emphasis mt-1">
            {{ store.queueLength?.queue ?? 'celery' }} 队列等待中
          </div>
        </v-card>
      </v-col>
    </v-row>

    <!-- 错误提示 -->
    <v-row v-if="store.error">
      <v-col cols="12">
        <v-alert type="warning" variant="tonal" closable @click:close="store.error = null">
          {{ store.error }}
        </v-alert>
      </v-col>
    </v-row>

    <!-- 定时任务列表 -->
    <v-row class="mt-2">
      <v-col cols="12">
        <v-card>
          <v-card-title class="d-flex align-center ga-2">
            <v-icon color="purple">mdi-clock-outline</v-icon>
            定时任务（Beat Schedule）
          </v-card-title>
          <v-divider />
          <v-data-table
            :headers="scheduledHeaders"
            :items="store.scheduledTasks"
            :items-per-page="-1"
            density="comfortable"
            hover
            no-data-text="暂无定时任务"
          >
            <template #item.enabled="{ item }">
              <v-chip :color="item.enabled ? 'success' : 'grey'" size="small" variant="tonal">
                {{ item.enabled ? '启用' : '禁用' }}
              </v-chip>
            </template>
            <template #item.task="{ item }">
              <code class="text-caption">{{ item.task }}</code>
            </template>
            <template #item.schedule="{ item }">
              <v-chip color="purple" size="small" variant="tonal">
                {{ item.schedule }}
              </v-chip>
            </template>
            <template #item.options="{ item }">
              <span v-if="item.options.expires" class="text-caption">
                超时: {{ item.options.expires }}s
              </span>
              <span v-else class="text-caption text-medium-emphasis">-</span>
            </template>
            <template #bottom />
          </v-data-table>
        </v-card>
      </v-col>
    </v-row>

    <!-- Worker 信息 -->
    <v-row class="mt-2">
      <v-col cols="12">
        <v-card>
          <v-card-title class="d-flex align-center ga-2">
            <v-icon color="success">mdi-server</v-icon>
            Worker 节点
          </v-card-title>
          <v-divider />
          <v-data-table
            :headers="workerHeaders"
            :items="store.workers"
            :items-per-page="-1"
            density="comfortable"
            hover
            no-data-text="无在线 Worker，请检查 Celery Worker 是否已启动"
          >
            <template #item.name="{ item }">
              <div class="d-flex align-center ga-2">
                <v-icon color="success" size="small">mdi-circle</v-icon>
                <code class="text-caption">{{ item.name }}</code>
              </div>
            </template>
            <template #item.pid="{ item }">
              <code class="text-caption">{{ item.pid ?? '-' }}</code>
            </template>
            <template #bottom />
          </v-data-table>
        </v-card>
      </v-col>
    </v-row>

    <!-- 执行中的任务 & 预取任务 -->
    <v-row class="mt-2">
      <v-col cols="12" md="6">
        <v-card>
          <v-card-title class="d-flex align-center ga-2">
            <v-icon color="blue">mdi-run</v-icon>
            执行中的任务
            <v-chip size="x-small" color="blue" variant="tonal" class="ml-1">
              {{ store.activeTasks.length }}
            </v-chip>
          </v-card-title>
          <v-divider />
          <v-list v-if="store.activeTasks.length > 0" density="compact">
            <v-list-item
              v-for="task in store.activeTasks"
              :key="task.id"
              :subtitle="task.worker"
            >
              <template #title>
                <code class="text-caption">{{ task.name }}</code>
              </template>
              <template #append>
                <v-chip size="x-small" color="blue" variant="tonal">
                  {{ task.started ? formatTimestamp(task.started) : '运行中' }}
                </v-chip>
              </template>
            </v-list-item>
          </v-list>
          <v-card-text v-else class="text-center text-medium-emphasis">
            <v-icon size="48" class="mb-2" color="grey">mdi-check-circle-outline</v-icon>
            <div>当前没有正在执行的任务</div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="6">
        <v-card>
          <v-card-title class="d-flex align-center ga-2">
            <v-icon color="orange">mdi-inbox-arrow-down</v-icon>
            预取任务（Reserved）
            <v-chip size="x-small" color="orange" variant="tonal" class="ml-1">
              {{ store.reservedTasks.length }}
            </v-chip>
          </v-card-title>
          <v-divider />
          <v-list v-if="store.reservedTasks.length > 0" density="compact">
            <v-list-item
              v-for="task in store.reservedTasks"
              :key="task.id"
              :subtitle="task.worker"
            >
              <template #title>
                <code class="text-caption">{{ task.name }}</code>
              </template>
              <template #append>
                <v-chip size="x-small" color="orange" variant="tonal">等待执行</v-chip>
              </template>
            </v-list-item>
          </v-list>
          <v-card-text v-else class="text-center text-medium-emphasis">
            <v-icon size="48" class="mb-2" color="grey">mdi-inbox-outline</v-icon>
            <div>当前没有预取的任务</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- 自动刷新 -->
    <v-row class="mt-4">
      <v-col cols="12" class="d-flex align-center justify-center ga-4">
        <v-switch
          v-model="autoRefresh"
          label="自动刷新"
          color="red"
          hide-details
          density="compact"
        />
        <v-select
          v-model="refreshInterval"
          :items="intervalOptions"
          item-title="label"
          item-value="value"
          label="刷新间隔"
          variant="outlined"
          density="compact"
          hide-details
          style="max-width: 160px"
          :disabled="!autoRefresh"
        />
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useQueueStore } from '@/stores/queue'

const store = useQueueStore()

const autoRefresh = ref(false)
const refreshInterval = ref(10)
let timer: ReturnType<typeof setInterval> | null = null

const intervalOptions = [
  { label: '5 秒', value: 5 },
  { label: '10 秒', value: 10 },
  { label: '30 秒', value: 30 },
  { label: '60 秒', value: 60 },
]

const scheduledHeaders = [
  { title: '任务名称', key: 'name', sortable: false },
  { title: '任务函数', key: 'task', sortable: false },
  { title: '调度周期', key: 'schedule', sortable: false },
  { title: '选项', key: 'options', sortable: false },
  { title: '状态', key: 'enabled', sortable: false },
]

const workerHeaders = [
  { title: '节点名称', key: 'name', sortable: false },
  { title: '并发数', key: 'concurrency', sortable: false },
  { title: '预取数', key: 'prefetch_count', sortable: false },
  { title: 'PID', key: 'pid', sortable: false },
  { title: 'Broker', key: 'broker', sortable: false },
]

function formatTimestamp(ts: number): string {
  try {
    return new Date(ts * 1000).toLocaleString('zh-CN')
  } catch {
    return String(ts)
  }
}

function startTimer() {
  stopTimer()
  if (autoRefresh.value) {
    timer = setInterval(() => store.loadAll(), refreshInterval.value * 1000)
  }
}

function stopTimer() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

watch([autoRefresh, refreshInterval], () => {
  startTimer()
})

onMounted(() => {
  store.loadAll()
})

onUnmounted(() => {
  stopTimer()
})
</script>

