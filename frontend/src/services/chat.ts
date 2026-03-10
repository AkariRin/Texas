/**
 * Chat API 服务层 —— 封装 /api/v1/chat 所有后端接口调用。
 */

import axios from 'axios'

// ── 类型定义 ──

export interface OverviewStats {
  total_messages: number
  today_messages: number
  active_groups: number
  active_users: number
}

export interface TrendItem {
  period: string
  count: number
}

export interface HeatmapItem {
  day_of_week: number
  hour: number
  count: number
}

export interface GroupRankItem {
  group_id: number
  message_count: number
  active_members: number
}

export interface UserRankItem {
  user_id: number
  nickname: string
  message_count: number
}

export interface ChatMessage {
  id: number
  message_id: number
  message_type: number
  group_id: number | null
  user_id: number
  self_id: number
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

export interface MessageStats {
  type_distribution: Record<string, number>
  daily_counts: { day: string; count: number }[]
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

export interface PaginatedResult<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

interface ApiResponse<T> {
  code: number
  data: T
  message: string
}

// ── API 调用 ──

const BASE = '/api/v1/chat'

// ── 概览 & 统计 ──

export async function fetchOverview(groupId?: number): Promise<OverviewStats> {
  const params: Record<string, number> = {}
  if (groupId) params.group_id = groupId
  const { data } = await axios.get<ApiResponse<OverviewStats>>(`${BASE}/overview`, { params })
  return data.data
}

export async function fetchTrend(params?: {
  groupId?: number
  granularity?: string
  days?: number
}): Promise<TrendItem[]> {
  const query: Record<string, string | number> = {}
  if (params?.groupId) query.group_id = params.groupId
  if (params?.granularity) query.granularity = params.granularity
  if (params?.days) query.days = params.days
  const { data } = await axios.get<ApiResponse<TrendItem[]>>(`${BASE}/trend`, { params: query })
  return data.data
}

export async function fetchHeatmap(groupId?: number): Promise<HeatmapItem[]> {
  const params: Record<string, number> = {}
  if (groupId) params.group_id = groupId
  const { data } = await axios.get<ApiResponse<HeatmapItem[]>>(`${BASE}/heatmap`, { params })
  return data.data
}

export async function fetchGroupRanking(limit?: number): Promise<GroupRankItem[]> {
  const params: Record<string, number> = {}
  if (limit) params.limit = limit
  const { data } = await axios.get<ApiResponse<GroupRankItem[]>>(`${BASE}/rankings/groups`, {
    params,
  })
  return data.data
}

export async function fetchUserRanking(params?: {
  groupId?: number
  limit?: number
}): Promise<UserRankItem[]> {
  const query: Record<string, number> = {}
  if (params?.groupId) query.group_id = params.groupId
  if (params?.limit) query.limit = params.limit
  const { data } = await axios.get<ApiResponse<UserRankItem[]>>(`${BASE}/rankings/users`, {
    params: query,
  })
  return data.data
}

export async function fetchStats(groupId?: number): Promise<MessageStats> {
  const params: Record<string, number> = {}
  if (groupId) params.group_id = groupId
  const { data } = await axios.get<ApiResponse<MessageStats>>(`${BASE}/stats`, { params })
  return data.data
}

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
  const { data } = await axios.get<ApiResponse<ChatMessage[]>>(
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
  const { data } = await axios.get<ApiResponse<ChatMessage[]>>(
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
  const { data } = await axios.get<ApiResponse<MessageContext>>(
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
  const { data } = await axios.get<ApiResponse<PaginatedResult<ArchiveLog>>>(`${BASE}/archives`, {
    params,
  })
  return data.data
}

export async function triggerArchive(partitionName?: string): Promise<{ task_id: string }> {
  const body = partitionName ? { partition_name: partitionName } : {}
  const { data } = await axios.post<ApiResponse<{ task_id: string }>>(
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
  const { data } = await axios.get<ApiResponse<ChatMessage[]>>(`${BASE}/archives/query`, {
    params,
  })
  return data.data
}

