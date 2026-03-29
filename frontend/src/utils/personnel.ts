/**
 * 人员相关 UI 辅助函数 —— 关系类型、角色的颜色、标签、图标映射。
 */

// ── 关系类型 ──

const RELATION_COLOR: Record<string, string> = {
  stranger: 'grey',
  group_member: 'blue',
  friend: 'green',
  admin: 'red',
}

const RELATION_LABEL: Record<string, string> = {
  stranger: '陌生人',
  group_member: '群友',
  friend: '好友',
  admin: '管理员',
}

const RELATION_ICON: Record<string, string> = {
  stranger: 'mdi-account-outline',
  group_member: 'mdi-account-multiple',
  friend: 'mdi-account-heart',
  admin: 'mdi-shield-account',
}

export function relationColor(r: string): string {
  return RELATION_COLOR[r] ?? 'grey'
}

export function relationLabel(r: string): string {
  return RELATION_LABEL[r] ?? r
}

export function relationIcon(r: string): string {
  return RELATION_ICON[r] ?? 'mdi-account'
}

// ── 群角色 ──

const ROLE_COLOR: Record<string, string> = {
  owner: 'amber',
  admin: 'green',
  member: 'grey',
}

const ROLE_LABEL: Record<string, string> = {
  owner: '群主',
  admin: '管理员',
  member: '成员',
}

export function roleColor(r: string | undefined): string {
  return ROLE_COLOR[r ?? ''] ?? 'grey'
}

export function roleLabel(r: string | undefined): string {
  return ROLE_LABEL[r ?? ''] ?? r ?? ''
}
