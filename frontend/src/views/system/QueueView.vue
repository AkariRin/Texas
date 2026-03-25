<template>
  <v-container fluid>
    <PageHeader>
      <v-chip
        :color="store.connected ? 'success' : 'grey'"
        variant="elevated"
        :prepend-icon="store.connected ? 'mdi-access-point' : 'mdi-access-point-off'"
      >
        {{ store.connected ? '实时推送中' : '未连接' }}
      </v-chip>
    </PageHeader>

    <!-- 概览卡片 -->
    <v-row>
      <v-col cols="12" sm="6" md="3">
        <v-card variant="elevated" color="purple" class="pa-4">
          <div class="d-flex align-center ga-2 mb-2">
            <v-icon color="white">mdi-clock-outline</v-icon>
            <span class="text-subtitle-2">定时任务</span>
          </div>
          <div class="text-h5 font-weight-bold">{{ store.scheduledTasks.length }}</div>
          <div class="text-caption text-medium-emphasis mt-1">已注册的周期性任务</div>
        </v-card>
      </v-col>

      <v-col cols="12" sm="6" md="3">
        <v-card
          variant="elevated"
          :color="store.workers.length > 0 ? 'success' : 'grey'"
          class="pa-4"
        >
          <div class="d-flex align-center ga-2 mb-2">
            <v-icon color="white">mdi-server</v-icon>
            <span class="text-subtitle-2">Worker 节点</span>
          </div>
          <div class="text-h5 font-weight-bold">{{ store.workers.length }}</div>
          <div class="text-caption text-medium-emphasis mt-1">
            {{ store.workers.length > 0 ? '在线' : '无在线节点' }}
          </div>
        </v-card>
      </v-col>

      <v-col cols="12" sm="6" md="3">
        <v-card variant="elevated" color="blue" class="pa-4">
          <div class="d-flex align-center ga-2 mb-2">
            <v-icon color="white">mdi-run</v-icon>
            <span class="text-subtitle-2">执行中</span>
          </div>
          <div class="text-h5 font-weight-bold">{{ store.activeTasks.length }}</div>
          <div class="text-caption text-medium-emphasis mt-1">正在执行的任务</div>
        </v-card>
      </v-col>

      <v-col cols="12" sm="6" md="3">
        <v-card variant="elevated" color="orange" class="pa-4">
          <div class="d-flex align-center ga-2 mb-2">
            <v-icon color="white">mdi-inbox-arrow-down</v-icon>
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
        <v-alert type="warning" variant="elevated" closable @click:close="store.error = null">
          {{ store.error }}
        </v-alert>
      </v-col>
    </v-row>

    <!-- 统一任务列表 -->
    <v-row class="mt-2">
      <v-col cols="12">
        <v-card>
          <v-card-title class="d-flex align-center ga-2">
            <v-icon color="purple">mdi-format-list-bulleted</v-icon>
            全部任务
            <v-chip size="x-small" color="purple" variant="elevated" class="ml-1">
              {{ store.allTasks.length }}
            </v-chip>
            <v-spacer />
            <v-btn-toggle v-model="taskFilter" density="compact" variant="elevated" divided>
              <v-btn value="all" size="small">全部</v-btn>
              <v-btn value="scheduled" size="small" color="purple">定时</v-btn>
              <v-btn value="active" size="small" color="blue">执行中</v-btn>
              <v-btn value="reserved" size="small" color="orange">预取</v-btn>
              <v-btn value="pending" size="small" color="teal">等待中</v-btn>
            </v-btn-toggle>
          </v-card-title>
          <v-divider />
          <v-data-table
            :headers="unifiedHeaders"
            :items="filteredTasks"
            :items-per-page="20"
            density="comfortable"
            hover
            no-data-text="暂无任务"
          >
            <template #item.category="{ item }">
              <v-chip :color="categoryColor(item.category)" size="small" variant="elevated">
                {{ categoryLabel(item.category) }}
              </v-chip>
            </template>
            <template #item.task="{ item }">
              <code class="text-caption">{{ item.task }}</code>
            </template>
            <template #item.schedule="{ item }">
              <v-chip v-if="item.schedule" color="purple" size="small" variant="elevated">
                {{ item.schedule }}
              </v-chip>
              <span v-else class="text-caption text-medium-emphasis">-</span>
            </template>
            <template #item.enabled="{ item }">
              <template v-if="item.enabled !== null">
                <v-chip :color="item.enabled ? 'success' : 'grey'" size="small" variant="elevated">
                  {{ item.enabled ? '启用' : '禁用' }}
                </v-chip>
              </template>
              <span v-else class="text-caption text-medium-emphasis">-</span>
            </template>
            <template #item.worker="{ item }">
              <code v-if="item.worker" class="text-caption">{{ item.worker }}</code>
              <span v-else class="text-caption text-medium-emphasis">-</span>
            </template>
            <template #item.started="{ item }">
              <v-chip v-if="item.started" size="x-small" color="blue" variant="elevated">
                {{ formatTimestamp(item.started) }}
              </v-chip>
              <span v-else class="text-caption text-medium-emphasis">-</span>
            </template>
          </v-data-table>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { useQueueStore } from '@/stores/queue'
import type { TaskCategory } from '@/apis/queue'
import PageHeader from '@/components/PageHeader.vue'

const store = useQueueStore()

const taskFilter = ref<'all' | TaskCategory>('all')

const unifiedHeaders = [
  { title: '类型', key: 'category', sortable: true, width: '100px' },
  { title: '任务名称', key: 'name', sortable: true },
  { title: '任务函数', key: 'task', sortable: false },
  { title: '调度周期', key: 'schedule', sortable: false },
  { title: '状态', key: 'enabled', sortable: false, width: '90px' },
  { title: 'Worker', key: 'worker', sortable: true },
  { title: '开始时间', key: 'started', sortable: true },
]

const filteredTasks = computed(() => {
  if (taskFilter.value === 'all') return store.allTasks
  return store.allTasks.filter((t) => t.category === taskFilter.value)
})

function categoryLabel(cat: TaskCategory): string {
  const map: Record<TaskCategory, string> = {
    scheduled: '定时',
    active: '执行中',
    reserved: '预取',
    pending: '等待中',
  }
  return map[cat] ?? cat
}

function categoryColor(cat: TaskCategory): string {
  const map: Record<TaskCategory, string> = {
    scheduled: 'purple',
    active: 'blue',
    reserved: 'orange',
    pending: 'teal',
  }
  return map[cat] ?? 'grey'
}

function formatTimestamp(ts: number): string {
  try {
    return new Date(ts * 1000).toLocaleString('zh-CN')
  } catch {
    return String(ts)
  }
}

onMounted(() => {
  store.connect()
})

onUnmounted(() => {
  store.disconnect()
})
</script>
