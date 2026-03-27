/**
 * 权限管理 API 接口层 —— 封装 /api/permissions 所有后端接口调用。
 */

import http from './client'
import type { ApiResponse } from './types'

// ── 类型定义 ──

export interface FeatureItem {
  name: string
  parent: string | null
  display_name: string
  description: string
  default_enabled: boolean
  enabled: boolean
  private_mode: 'blacklist' | 'whitelist'
  is_active: boolean
  // 内存元数据注解字段（从装饰器同步）
  admin?: boolean
  message_scope?: string
  mapping_type?: string
  tags?: string[]
  children: FeatureItem[]
}

export interface GroupFeaturePermission {
  feature_name: string
  display_name: string
  enabled: boolean
  is_explicit: boolean
  parent: string | null
}

/** matrix feature 子项（method 级） */
export interface MatrixMethodFeature {
  name: string
  display_name: string
  description: string
  enabled: boolean
  admin: boolean
  message_scope: string
  mapping_type: string
}

/** matrix feature 顶级项（controller 级） */
export interface MatrixControllerFeature {
  name: string
  display_name: string
  description: string
  enabled: boolean
  admin: boolean
  tags: string[]
  children: MatrixMethodFeature[]
}

export interface PermissionMatrixGroup {
  group_id: number
  group_name: string
  bot_enabled: boolean
  permissions: Record<string, boolean>
}

export interface PermissionMatrix {
  features: MatrixControllerFeature[]
  groups: PermissionMatrixGroup[]
}

export interface FeatureUpdateData {
  enabled?: boolean
  private_mode?: 'blacklist' | 'whitelist'
}

export interface GroupFeatureSetData {
  features: { feature_name: string; enabled: boolean }[]
}

// ── API 调用 ──

const BASE = '/api/permissions'

// ── 功能树 ──

export async function fetchFeatures(): Promise<FeatureItem[]> {
  const { data } = await http.get<ApiResponse<FeatureItem[]>>(`${BASE}/features`)
  return data.data
}

export async function updateFeature(name: string, payload: FeatureUpdateData): Promise<void> {
  await http.post<ApiResponse<unknown>>(
    `${BASE}/features/${encodeURIComponent(name)}/update`,
    payload,
  )
}

// ── 群聊权限 ──

export async function fetchGroupFeatures(groupId: number): Promise<GroupFeaturePermission[]> {
  const { data } = await http.get<ApiResponse<GroupFeaturePermission[]>>(
    `${BASE}/groups/${groupId}/features`,
  )
  return data.data
}

export async function setGroupFeatures(
  groupId: number,
  payload: GroupFeatureSetData,
): Promise<void> {
  await http.post<ApiResponse<null>>(`${BASE}/groups/${groupId}/features`, payload)
}

export async function setGroupSwitch(groupId: number, enabled: boolean): Promise<void> {
  await http.post<ApiResponse<null>>(`${BASE}/groups/${groupId}/switch`, { enabled })
}

// ── 私聊权限 ──

export async function fetchPrivateUsers(featureName: string): Promise<number[]> {
  const { data } = await http.get<ApiResponse<number[]>>(
    `${BASE}/features/${encodeURIComponent(featureName)}/private-users`,
  )
  return data.data
}

export async function addPrivateUser(featureName: string, userQq: number): Promise<void> {
  await http.post<ApiResponse<null>>(
    `${BASE}/features/${encodeURIComponent(featureName)}/private-users`,
    { user_qq: userQq },
  )
}

export async function removePrivateUser(featureName: string, userQq: number): Promise<void> {
  await http.post<ApiResponse<null>>(
    `${BASE}/features/${encodeURIComponent(featureName)}/private-users/remove`,
    { user_qq: userQq },
  )
}

// ── 权限矩阵 ──

export async function fetchPermissionMatrix(): Promise<PermissionMatrix> {
  const { data } = await http.get<ApiResponse<PermissionMatrix>>(`${BASE}/matrix`)
  return data.data
}
