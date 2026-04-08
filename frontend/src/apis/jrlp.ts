/**
 * 今日老婆 API 接口层 —— 封装 /api/jrlp 所有后端接口调用。
 */

import http from './client'
import type { ApiResponse, PaginatedResult } from './types'

// ── 类型定义 ──

export interface WifeRecord {
  id: number
  group_id: number
  group_name: string
  user_id: number
  user_nickname: string
  wife_qq: number
  wife_nickname: string
  date: string
  drawn_at: string | null
}

export interface ListRecordsParams {
  group_id?: number | null
  user_id?: number | null
  date?: string | null
  page?: number
  page_size?: number
}

export interface SetWifeRequest {
  group_id: number
  user_id: number
  wife_qq: number
  date: string
}

export interface UpdateRecordRequest {
  id: number
  wife_qq: number
}

export interface DeleteRecordRequest {
  id: number
}

// ── API 调用 ──

const BASE = '/api/jrlp'

export async function listRecords(params: ListRecordsParams): Promise<PaginatedResult<WifeRecord>> {
  const query: Record<string, string | number> = {}
  if (params.group_id != null) query.group_id = params.group_id
  if (params.user_id != null) query.user_id = params.user_id
  if (params.date) query.date = params.date
  if (params.page) query.page = params.page
  if (params.page_size) query.page_size = params.page_size

  const { data } = await http.get<ApiResponse<PaginatedResult<WifeRecord>>>(`${BASE}/records`, {
    params: query,
  })
  return data.data
}

export async function setWife(body: SetWifeRequest): Promise<WifeRecord> {
  const { data } = await http.post<ApiResponse<WifeRecord>>(`${BASE}/records/create`, body)
  return data.data
}

export async function updateRecord(body: UpdateRecordRequest): Promise<WifeRecord> {
  const { data } = await http.post<ApiResponse<WifeRecord>>(`${BASE}/records/update`, body)
  return data.data
}

export async function deleteRecord(body: DeleteRecordRequest): Promise<void> {
  await http.post<ApiResponse<null>>(`${BASE}/records/delete`, body)
}
