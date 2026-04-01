/**
 * 树形结构与权限矩阵工具函数。
 */

import type { FeatureItem, PermissionMatrixGroup } from '@/apis/permission'

/**
 * 在功能树中找到指定名称的节点并原地更新其字段。
 * 支持多级 children 递归。
 */
export function updateFeatureInTree(
  features: FeatureItem[],
  name: string,
  enabled?: boolean,
  privateMode?: string,
): void {
  for (const f of features) {
    if (f.name === name) {
      if (enabled !== undefined) f.enabled = enabled
      if (privateMode !== undefined) f.private_mode = privateMode as 'blacklist' | 'whitelist'
    }
    if (f.children?.length) updateFeatureInTree(f.children, name, enabled, privateMode)
  }
}

/**
 * 将功能权限批量写入群组的 permissions 映射。
 */
export function applyGroupFeaturePermissions(
  groups: PermissionMatrixGroup[],
  groupId: number,
  items: { feature_name: string; enabled: boolean }[],
): void {
  const group = groups.find((g) => g.group_id === groupId)
  if (!group) return
  for (const item of items) {
    group.permissions[item.feature_name] = item.enabled
  }
}

/**
 * 更新群组的 bot_enabled 开关状态。
 */
export function applyGroupSwitch(
  groups: PermissionMatrixGroup[],
  groupId: number,
  enabled: boolean,
): void {
  const group = groups.find((g) => g.group_id === groupId)
  if (group) group.bot_enabled = enabled
}
