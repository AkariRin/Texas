/**
 * 用户群签到 API 接口层 —— 封装 /api/checkin 所有后端接口调用。
 */

import http from './client'
import type { ApiResponse, PaginatedResult } from './types'

// ── 类型定义 ──

export interface CheckinRecord {
  id: number
  group_id: number
  user_id: number
  checkin_date: string
  checkin_at: string
}

export interface LeaderEntry {
  rank: number
  user_id: number
  value: number
}

export interface DayCount {
  date: string
  count: number
}

export interface Summary {
  total_checkins: number
  today_checkins: number
  active_users: number
}

export interface ListRecordsParams {
  group_id: number
  user_id?: number | null
  date?: string | null
  page?: number
  page_size?: number
}

// ── API 调用 ──

const BASE = '/api/checkin'

export async function listRecords(
  params: ListRecordsParams,
): Promise<PaginatedResult<CheckinRecord>> {
  const query: Record<string, string | number> = { group_id: params.group_id }
  if (params.user_id != null) query.user_id = params.user_id
  if (params.date) query.date = params.date
  if (params.page) query.page = params.page
  if (params.page_size) query.page_size = params.page_size

  const { data } = await http.get<ApiResponse<PaginatedResult<CheckinRecord>>>(`${BASE}/records`, {
    params: query,
  })
  return data.data
}

export async function getLeaderboard(
  groupId: number,
  by: 'total' | 'streak' = 'total',
  limit = 20,
): Promise<LeaderEntry[]> {
  const { data } = await http.get<ApiResponse<LeaderEntry[]>>(`${BASE}/leaderboard`, {
    params: { group_id: groupId, by, limit },
  })
  return data.data
}

export async function getDailyTrend(groupId: number, days = 30): Promise<DayCount[]> {
  const { data } = await http.get<ApiResponse<DayCount[]>>(`${BASE}/trend`, {
    params: { group_id: groupId, days },
  })
  return data.data
}

export async function getSummary(groupId: number): Promise<Summary> {
  const { data } = await http.get<ApiResponse<Summary>>(`${BASE}/summary`, {
    params: { group_id: groupId },
  })
  return data.data
}
