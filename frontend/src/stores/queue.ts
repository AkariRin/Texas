import { ref } from 'vue'
import { defineStore } from 'pinia'
import {
  fetchScheduledTasks,
  fetchActiveTasks,
  fetchReservedTasks,
  fetchWorkers,
  fetchQueueLength,
  type ScheduledTask,
  type ActiveTask,
  type ReservedTask,
  type WorkerInfo,
  type QueueLength,
} from '@/services/queue'

export const useQueueStore = defineStore('queue', () => {
  const scheduledTasks = ref<ScheduledTask[]>([])
  const activeTasks = ref<ActiveTask[]>([])
  const reservedTasks = ref<ReservedTask[]>([])
  const workers = ref<WorkerInfo[]>([])
  const queueLength = ref<QueueLength | null>(null)

  const loading = ref(false)
  const error = ref<string | null>(null)

  async function loadScheduledTasks() {
    try {
      scheduledTasks.value = await fetchScheduledTasks()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '获取定时任务失败'
    }
  }

  async function loadActiveTasks() {
    try {
      activeTasks.value = await fetchActiveTasks()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '获取活跃任务失败'
    }
  }

  async function loadReservedTasks() {
    try {
      reservedTasks.value = await fetchReservedTasks()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '获取预留任务失败'
    }
  }

  async function loadWorkers() {
    try {
      workers.value = await fetchWorkers()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '获取 Worker 信息失败'
    }
  }

  async function loadQueueLength() {
    try {
      queueLength.value = await fetchQueueLength()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '获取队列长度失败'
    }
  }

  async function loadAll() {
    loading.value = true
    error.value = null
    await Promise.all([
      loadScheduledTasks(),
      loadActiveTasks(),
      loadReservedTasks(),
      loadWorkers(),
      loadQueueLength(),
    ])
    loading.value = false
  }

  return {
    scheduledTasks,
    activeTasks,
    reservedTasks,
    workers,
    queueLength,
    loading,
    error,
    loadScheduledTasks,
    loadActiveTasks,
    loadReservedTasks,
    loadWorkers,
    loadQueueLength,
    loadAll,
  }
})

