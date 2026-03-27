/**
 * Queue API 接口层 —— 封装 /api/queue 所有后端接口调用。
 */

// ── 类型定义 ──

export interface ScheduledTask {
  name: string
  task: string
  schedule: string
  schedule_raw: number | null
  args: unknown[] | null
  kwargs: Record<string, unknown> | null
  options: {
    expires: number | null
    queue: string | null
  }
  enabled: boolean
}

export interface ActiveTask {
  worker: string
  id: string
  name: string
  args: string
  kwargs: string
  started: number | null
  acknowledged: boolean
}

export interface ReservedTask {
  worker: string
  id: string
  name: string
  args: string
  kwargs: string
  acknowledged: boolean
}

export interface PendingTask {
  id: string
  name: string
  args: string | null
  kwargs: string | null
}

export interface WorkerInfo {
  name: string
  concurrency: number | null
  broker: string | null
  prefetch_count: number | null
  pid: number | null
  uptime: number | null
}

export interface QueueLength {
  queue: string
  length: number | null
}

/** 统一任务类型 —— 将定时 / 执行中 / 预取三种任务合并为一张表 */
export type TaskCategory = 'scheduled' | 'active' | 'reserved' | 'pending'

export interface UnifiedTask {
  /** 任务类别 */
  category: TaskCategory
  /** 任务 ID（定时任务无 id，使用 name 代替） */
  id: string
  /** 任务名称（定时任务为 beat schedule key） */
  name: string
  /** 任务函数全路径 */
  task: string
  /** 调度周期（仅定时任务） */
  schedule: string | null
  /** 是否启用（仅定时任务） */
  enabled: boolean | null
  /** 选项-超时秒数（仅定时任务） */
  expires: number | null
  /** 所在 Worker（执行中/预取任务） */
  worker: string | null
  /** 开始时间戳（执行中任务） */
  started: number | null
  /** 参数 */
  args: string | null
  /** 关键字参数 */
  kwargs: string | null
}

/** SSE 推送的完整队列状态数据 */
export interface QueueStreamData {
  scheduledTasks: ScheduledTask[]
  activeTasks: ActiveTask[]
  reservedTasks: ReservedTask[]
  pendingTasks: PendingTask[]
  workers: WorkerInfo[]
  queueLength: QueueLength
  error?: string
}

// ── SSE 实时推送 ──

/**
 * 建立 SSE 连接，实时接收队列状态数据。
 * @param onData  每次推送数据的回调
 * @param onError 连接错误回调
 * @param interval 服务端推送间隔（秒），默认 5
 * @returns 关闭连接的函数
 */
export function connectQueueStream(
  onData: (data: QueueStreamData) => void,
  onError?: (error: string) => void,
  interval: number = 5,
): () => void {
  const url = `/api/queue/stream?interval=${interval}`
  const eventSource = new EventSource(url)

  eventSource.onmessage = (event) => {
    try {
      const data: QueueStreamData = JSON.parse(event.data)
      if (data.error) {
        onError?.(data.error)
      } else {
        onData(data)
      }
    } catch (e) {
      onError?.(`解析 SSE 数据失败: ${e}`)
    }
  }

  eventSource.onerror = () => {
    onError?.('SSE 连接断开，正在重连…')
  }

  return () => {
    eventSource.onmessage = null
    eventSource.onerror = null
    eventSource.close()
  }
}
