import { ref, shallowRef, computed } from 'vue'
import { defineStore } from 'pinia'
import {
  connectQueueStream,
  type ScheduledTask,
  type ActiveTask,
  type ReservedTask,
  type PendingTask,
  type WorkerInfo,
  type QueueLength,
  type UnifiedTask,
} from '@/apis/queue'

export const useQueueStore = defineStore('queue', () => {
  // shallowRef：这些数组每次 SSE 推送都整体替换，不需要深度响应式
  const scheduledTasks = shallowRef<ScheduledTask[]>([])
  const activeTasks = shallowRef<ActiveTask[]>([])
  const reservedTasks = shallowRef<ReservedTask[]>([])
  const pendingTasks = shallowRef<PendingTask[]>([])
  const workers = shallowRef<WorkerInfo[]>([])
  const queueLength = shallowRef<QueueLength | null>(null)

  const connected = ref(false)
  const error = ref<string | null>(null)

  let closeStream: (() => void) | null = null

  /** 合并所有任务为统一列表 */
  const allTasks = computed<UnifiedTask[]>(() => {
    const items: UnifiedTask[] = []

    for (const t of scheduledTasks.value) {
      items.push({
        category: 'scheduled',
        id: t.name,
        name: t.name,
        task: t.task,
        schedule: t.schedule,
        enabled: t.enabled,
        expires: t.options?.expires ?? null,
        worker: null,
        started: null,
        args: t.args ? JSON.stringify(t.args) : null,
        kwargs: t.kwargs ? JSON.stringify(t.kwargs) : null,
      })
    }

    for (const t of activeTasks.value) {
      items.push({
        category: 'active',
        id: t.id,
        name: t.name,
        task: t.name,
        schedule: null,
        enabled: null,
        expires: null,
        worker: t.worker,
        started: t.started,
        args: t.args,
        kwargs: t.kwargs,
      })
    }

    for (const t of reservedTasks.value) {
      items.push({
        category: 'reserved',
        id: t.id,
        name: t.name,
        task: t.name,
        schedule: null,
        enabled: null,
        expires: null,
        worker: t.worker,
        started: null,
        args: t.args,
        kwargs: t.kwargs,
      })
    }

    for (const t of pendingTasks.value) {
      items.push({
        category: 'pending',
        id: t.id,
        name: t.name,
        task: t.name,
        schedule: null,
        enabled: null,
        expires: null,
        worker: null,
        started: null,
        args: t.args,
        kwargs: t.kwargs,
      })
    }

    return items
  })

  /** 建立 SSE 连接，开始实时接收队列状态 */
  function connect(interval: number = 5) {
    disconnect()
    error.value = null
    connected.value = true

    // 仅在数据实际变化时更新引用，避免 SSE 心跳引发不必要的重渲染
    // 数组先比较长度（O(1) 快路径），长度相同再做全量序列化比较
    function setIfChanged<T>(ref: { value: T }, next: T) {
      if (Array.isArray(ref.value) && Array.isArray(next) && ref.value.length !== next.length) {
        ref.value = next
        return
      }
      if (JSON.stringify(ref.value) !== JSON.stringify(next)) ref.value = next
    }

    closeStream = connectQueueStream(
      (data) => {
        setIfChanged(scheduledTasks, data.scheduledTasks)
        setIfChanged(activeTasks, data.activeTasks)
        setIfChanged(reservedTasks, data.reservedTasks)
        setIfChanged(pendingTasks, data.pendingTasks ?? [])
        setIfChanged(workers, data.workers)
        setIfChanged(queueLength, data.queueLength)
        error.value = null
      },
      (err) => {
        error.value = err
      },
      interval,
    )
  }

  /** 关闭 SSE 连接 */
  function disconnect() {
    if (closeStream) {
      closeStream()
      closeStream = null
    }
    connected.value = false
  }

  return {
    scheduledTasks,
    activeTasks,
    reservedTasks,
    pendingTasks,
    allTasks,
    workers,
    queueLength,
    connected,
    error,
    connect,
    disconnect,
  }
})
