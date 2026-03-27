/**
 * Chat API 接口层 —— 封装 /api/v1/chat 所有后端接口调用。
 */

import http from './client'
import type { ApiResponse, PaginatedResult } from './types'

// ── 类型定义 ──

export type { PaginatedResult } from './types'

export interface ChatMessage {
  id: number
  message_id: number
  message_type: number
  group_id: number | null
  user_id: number
  raw_message: string
  segments: MessageSegment[]
  sender_nickname: string
  sender_card: string | null
  sender_role: string | null
  created_at: string | null
  stored_at: string | null
}

export interface MessageSegment {
  type: string
  data: Record<string, unknown>
}

export interface MessageContext {
  before: ChatMessage[]
  current: ChatMessage[]
  after: ChatMessage[]
}

export interface ArchiveLog {
  id: string
  partition_name: string
  period_start: string
  period_end: string
  total_rows: number
  original_bytes: number
  compressed_bytes: number
  s3_bucket: string
  s3_key: string
  status: string
  error_message: string | null
  created_at: string | null
  completed_at: string | null
}

// ── API 调用 ──

const BASE = '/api/v1/chat'

// ── 消息查询 ──

export async function fetchGroupMessages(
  groupId: number,
  params?: {
    before?: string
    limit?: number
    keyword?: string
    userId?: number
    startDate?: string
    endDate?: string
  },
): Promise<ChatMessage[]> {
  const query: Record<string, string | number> = {}
  if (params?.before) query.before = params.before
  if (params?.limit) query.limit = params.limit
  if (params?.keyword) query.keyword = params.keyword
  if (params?.userId) query.user_id = params.userId
  if (params?.startDate) query.start_date = params.startDate
  if (params?.endDate) query.end_date = params.endDate
  const { data } = await http.get<ApiResponse<ChatMessage[]>>(
    `${BASE}/messages/group/${groupId}`,
    { params: query },
  )
  return data.data
}

export async function fetchPrivateMessages(
  userId: number,
  params?: { before?: string; limit?: number },
): Promise<ChatMessage[]> {
  const query: Record<string, string | number> = {}
  if (params?.before) query.before = params.before
  if (params?.limit) query.limit = params.limit
  const { data } = await http.get<ApiResponse<ChatMessage[]>>(
    `${BASE}/messages/private/${userId}`,
    { params: query },
  )
  return data.data
}

export async function fetchMessageContext(
  messageId: number,
  createdAt: string,
  context?: number,
): Promise<MessageContext> {
  const params: Record<string, string | number> = { created_at: createdAt }
  if (context) params.context = context
  const { data } = await http.get<ApiResponse<MessageContext>>(
    `${BASE}/messages/${messageId}/context`,
    { params },
  )
  return data.data
}

// ── 归档管理 ──

export async function fetchArchives(
  page?: number,
  pageSize?: number,
): Promise<PaginatedResult<ArchiveLog>> {
  const params: Record<string, number> = {}
  if (page) params.page = page
  if (pageSize) params.page_size = pageSize
  const { data } = await http.get<ApiResponse<PaginatedResult<ArchiveLog>>>(`${BASE}/archives`, {
    params,
  })
  return data.data
}

export async function triggerArchive(partitionName?: string): Promise<{ task_id: string }> {
  const body = partitionName ? { partition_name: partitionName } : {}
  const { data } = await http.post<ApiResponse<{ task_id: string }>>(
    `${BASE}/archives/trigger`,
    body,
  )
  return data.data
}

export async function queryArchive(
  periodStart: string,
  groupId?: number,
  limit?: number,
): Promise<ChatMessage[]> {
  const params: Record<string, string | number> = { period_start: periodStart }
  if (groupId) params.group_id = groupId
  if (limit) params.limit = limit
  const { data } = await http.get<ApiResponse<ChatMessage[]>>(`${BASE}/archives/query`, {
    params,
  })
  return data.data
}
