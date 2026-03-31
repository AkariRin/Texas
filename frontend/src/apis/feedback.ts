/**
 * 用户反馈 API 接口层 —— 封装 /api/v1/feedback 所有后端接口调用。
 */

import http from './client'
import type { ApiResponse, PaginatedResult } from './types'

// ── 类型定义 ──

export type { PaginatedResult } from './types'

export interface Feedback {
  id: string
  user_id: number
  group_id: number | null
  content: string
  status: string
  feedback_type: string | null
  source: string
  admin_reply: string | null
  created_at: string
  updated_at: string
  processed_at: string | null
}

export interface FeedbackListParams {
  page?: number
  page_size?: number
  status?: string | null
  feedback_type?: string | null
  user_id?: number | null
  source?: string | null
  search?: string | null
}

export interface UpdateStatusRequest {
  status: string
  admin_reply?: string | null
}

// ── API 调用 ──

const BASE = '/api/feedbacks'

export async function list(params: FeedbackListParams): Promise<PaginatedResult<Feedback>> {
  const query: Record<string, string | number> = {}
  if (params.page) query.page = params.page
  if (params.page_size) query.page_size = params.page_size
  if (params.status) query.status = params.status
  if (params.feedback_type) query.feedback_type = params.feedback_type
  if (params.user_id) query.user_id = params.user_id
  if (params.source) query.source = params.source
  if (params.search) query.search = params.search

  const { data } = await http.get<ApiResponse<PaginatedResult<Feedback>>>(`${BASE}`, {
    params: query,
  })
  return data.data
}

export async function get(id: string): Promise<Feedback> {
  const { data } = await http.get<ApiResponse<Feedback>>(`${BASE}/${id}`)
  return data.data
}

export async function updateStatus(id: string, body: UpdateStatusRequest): Promise<void> {
  await http.post<ApiResponse<null>>(`${BASE}/${id}/status`, body)
}
