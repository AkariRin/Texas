/**
 * Personnel API 接口层 —— 封装 /api/v1/personnel 所有后端接口调用。
 */

import axios from 'axios'

// ── 类型定义 ──

export interface UserItem {
  qq: number
  nickname: string
  relation: string
  group_count: number
  last_synced: string | null
}

export interface UserDetail extends UserItem {
  memberships?: GroupMembershipInfo[]
}

export interface GroupItem {
  group_id: number
  group_name: string
  member_count: number
  max_member_count: number
  is_active: boolean
  last_synced: string | null
}

export interface GroupMemberItem {
  qq: number
  nickname: string
  card: string
  role: string
  relation: string
  join_time: number
  last_active_time: number
  title: string
}

export interface GroupMembershipInfo {
  group_id: number
  group_name: string
  card: string
  role: string
  is_active: boolean
}

export interface SyncStatus {
  last_sync_time: string | null
  duration_seconds: number | null
  status: string
  users_synced: number
  groups_synced: number
  memberships_synced: number
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

const BASE = '/api/v1/personnel'

export async function fetchUsers(params: {
  page?: number
  page_size?: number
  relation?: string | null
  qq?: number | null
  nickname?: string | null
}): Promise<PaginatedResult<UserItem>> {
  const query: Record<string, string | number> = {}
  if (params.page) query.page = params.page
  if (params.page_size) query.page_size = params.page_size
  if (params.relation) query.relation = params.relation
  if (params.qq) query.qq = params.qq
  if (params.nickname) query.nickname = params.nickname

  const { data } = await axios.get<ApiResponse<PaginatedResult<UserItem>>>(`${BASE}/users`, {
    params: query,
  })
  return data.data
}

export async function fetchUser(qq: number): Promise<UserDetail> {
  const { data } = await axios.get<ApiResponse<UserDetail>>(`${BASE}/users/${qq}`)
  return data.data
}

export async function fetchUserGroups(qq: number): Promise<GroupItem[]> {
  const { data } = await axios.get<ApiResponse<GroupItem[]>>(`${BASE}/users/${qq}/groups`)
  return data.data
}

export async function fetchGroups(params: {
  page?: number
  page_size?: number
  group_name?: string | null
  is_active?: boolean | null
}): Promise<PaginatedResult<GroupItem>> {
  const query: Record<string, string | number | boolean> = {}
  if (params.page) query.page = params.page
  if (params.page_size) query.page_size = params.page_size
  if (params.group_name) query.group_name = params.group_name
  if (params.is_active !== null && params.is_active !== undefined)
    query.is_active = params.is_active

  const { data } = await axios.get<ApiResponse<PaginatedResult<GroupItem>>>(`${BASE}/groups`, {
    params: query,
  })
  return data.data
}

export async function fetchGroup(groupId: number): Promise<GroupItem> {
  const { data } = await axios.get<ApiResponse<GroupItem>>(`${BASE}/groups/${groupId}`)
  return data.data
}

export async function fetchGroupMembers(
  groupId: number,
  params: {
    page?: number
    page_size?: number
    role?: string | null
    nickname?: string | null
  },
): Promise<PaginatedResult<GroupMemberItem>> {
  const query: Record<string, string | number> = {}
  if (params.page) query.page = params.page
  if (params.page_size) query.page_size = params.page_size
  if (params.role) query.role = params.role
  if (params.nickname) query.nickname = params.nickname

  const { data } = await axios.get<ApiResponse<PaginatedResult<GroupMemberItem>>>(
    `${BASE}/groups/${groupId}/members`,
    { params: query },
  )
  return data.data
}

export async function triggerSync(): Promise<void> {
  await axios.post<ApiResponse<null>>(`${BASE}/sync`)
}

export async function fetchSyncStatus(): Promise<SyncStatus> {
  const { data } = await axios.get<ApiResponse<SyncStatus>>(`${BASE}/sync/status`)
  return data.data
}

export async function fetchAdmins(): Promise<UserItem[]> {
  const { data } = await axios.get<ApiResponse<UserItem[]>>(`${BASE}/admins`)
  return data.data
}

export async function addAdmin(qq: number): Promise<void> {
  await axios.post<ApiResponse<null>>(`${BASE}/admins/${qq}/add`)
}

export async function removeAdmin(qq: number): Promise<void> {
  await axios.post<ApiResponse<null>>(`${BASE}/admins/${qq}/delete`)
}
