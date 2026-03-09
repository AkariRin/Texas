/**
 * Queue API 服务层 —— 封装 /api/queue 所有后端接口调用。
 */

import axios from 'axios'

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

interface ApiResponse<T> {
  code: number
  data: T
  message: string
}

// ── API 调用 ──

export async function fetchScheduledTasks(): Promise<ScheduledTask[]> {
  const { data } = await axios.get<ApiResponse<ScheduledTask[]>>('/api/queue/scheduled-tasks')
  return data.data
}

export async function fetchActiveTasks(): Promise<ActiveTask[]> {
  const { data } = await axios.get<ApiResponse<ActiveTask[]>>('/api/queue/active-tasks')
  return data.data
}

export async function fetchReservedTasks(): Promise<ReservedTask[]> {
  const { data } = await axios.get<ApiResponse<ReservedTask[]>>('/api/queue/reserved-tasks')
  return data.data
}

export async function fetchWorkers(): Promise<WorkerInfo[]> {
  const { data } = await axios.get<ApiResponse<WorkerInfo[]>>('/api/queue/workers')
  return data.data
}

export async function fetchQueueLength(): Promise<QueueLength> {
  const { data } = await axios.get<ApiResponse<QueueLength>>('/api/queue/queue-length')
  return data.data
}

