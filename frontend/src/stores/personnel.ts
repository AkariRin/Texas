/**
 * 用户管理 Pinia Store —— 管理用户数据状态。
 */

import { ref, shallowRef, triggerRef } from 'vue'
import { defineStore } from 'pinia'
import * as api from '@/apis/personnel'
import type {
  UserItem,
  UserDetail,
  GroupItem,
  GroupMemberItem,
  SyncStatus,
  PaginatedResult,
  ResolvedUser,
  ResolvedGroup,
} from '@/apis/personnel'

export const usePersonnelStore = defineStore('personnel', () => {
  // ── 用户列表 ──
  const users = ref<PaginatedResult<UserItem>>({
    items: [],
    total: 0,
    page: 1,
    page_size: 20,
    pages: 0,
  })
  const usersLoading = ref(false)

  async function loadUsers(params: {
    page?: number
    page_size?: number
    relation?: string | null
    qq?: number | null
    nickname?: string | null
  }) {
    usersLoading.value = true
    try {
      users.value = await api.fetchUsers(params)
    } finally {
      usersLoading.value = false
    }
  }

  // ── 用户详情 ──
  const currentUser = ref<UserDetail | null>(null)
  const currentUserGroups = ref<GroupItem[]>([])

  async function loadUser(qq: number) {
    currentUser.value = await api.fetchUser(qq)
  }

  async function loadUserGroups(qq: number) {
    currentUserGroups.value = await api.fetchUserGroups(qq)
  }

  // ── 群列表 ──
  const groups = ref<PaginatedResult<GroupItem>>({
    items: [],
    total: 0,
    page: 1,
    page_size: 20,
    pages: 0,
  })
  const groupsLoading = ref(false)

  async function loadGroups(params: {
    page?: number
    page_size?: number
    group_name?: string | null
    is_active?: boolean | null
  }) {
    groupsLoading.value = true
    try {
      groups.value = await api.fetchGroups(params)
    } finally {
      groupsLoading.value = false
    }
  }

  // ── 群成员 ──
  const groupMembers = ref<PaginatedResult<GroupMemberItem>>({
    items: [],
    total: 0,
    page: 1,
    page_size: 20,
    pages: 0,
  })
  const membersLoading = ref(false)

  async function loadGroupMembers(
    groupId: number,
    params: {
      page?: number
      page_size?: number
      role?: string | null
      nickname?: string | null
      qq?: number | null
    },
  ) {
    membersLoading.value = true
    try {
      groupMembers.value = await api.fetchGroupMembers(groupId, params)
    } finally {
      membersLoading.value = false
    }
  }

  // ── 会话选择器专用列表（不影响人员管理页面的分页状态） ──
  const sessionGroups = ref<GroupItem[]>([])
  const sessionUsers = ref<UserItem[]>([])
  const sessionLoading = ref(false)

  async function loadSessionData() {
    sessionLoading.value = true
    try {
      const [groupResult, userResult] = await Promise.all([
        api.fetchGroups({ page: 1, page_size: 100 }),
        api.fetchUsers({ page: 1, page_size: 100, relation: 'friend' }),
      ])
      sessionGroups.value = groupResult.items
      sessionUsers.value = userResult.items
    } catch {
      // 静默失败，列表保持空状态（非关键数据，不阻断主流程）
    } finally {
      sessionLoading.value = false
    }
  }

  // ── 非共享状态的数据获取函数（组件内部使用，不写入共享 ref） ──

  async function fetchUserDetail(qq: number): Promise<{ user: UserDetail; groups: GroupItem[] }> {
    const [user, groups] = await Promise.all([api.fetchUser(qq), api.fetchUserGroups(qq)])
    return { user, groups }
  }

  async function fetchMemberDetail(groupId: number, qq: number): Promise<GroupMemberItem | null> {
    const result = await api.fetchGroupMembers(groupId, { page: 1, page_size: 1, qq })
    return result.items[0] ?? null
  }

  async function fetchGroupDetail(groupId: number): Promise<GroupItem> {
    return api.fetchGroup(groupId)
  }

  // ── 同步状态 ──
  const syncStatus = ref<SyncStatus | null>(null)
  const syncLoading = ref(false)

  async function loadSyncStatus() {
    syncStatus.value = await api.fetchSyncStatus()
  }

  async function doSync() {
    syncLoading.value = true
    try {
      await api.triggerSync()
      // 同步后清空解析缓存，确保名称数据与最新同步结果一致
      clearCache()
      // 延迟后刷新状态，静默失败（主流程已完成，状态轮询会反映真实结果）
      setTimeout(() => loadSyncStatus().catch(() => {}), 2000)
    } finally {
      syncLoading.value = false
    }
  }

  // ── ID 解析缓存 ──

  // shallowRef 包裹 Map，修改后手动 triggerRef 触发响应式更新
  const userCache = shallowRef(new Map<number, ResolvedUser>())
  const groupCache = shallowRef(new Map<number, ResolvedGroup>())

  // 待解析的 ID 集合（非响应式，仅用于批量合并）
  const pendingUserIds = new Set<number>()
  const pendingGroupIds = new Set<number>()
  let flushScheduled = false

  async function _flushPending() {
    flushScheduled = false
    const userIds = [...pendingUserIds].filter((id) => !userCache.value.has(id))
    const groupIds = [...pendingGroupIds].filter((id) => !groupCache.value.has(id))
    pendingUserIds.clear()
    pendingGroupIds.clear()

    if (!userIds.length && !groupIds.length) return

    try {
      const result = await api.resolvePersonnel(userIds, groupIds)
      for (const [k, v] of Object.entries(result.users)) {
        userCache.value.set(Number(k), v)
      }
      for (const [k, v] of Object.entries(result.groups)) {
        groupCache.value.set(Number(k), v)
      }
      // 统一触发响应式更新
      triggerRef(userCache)
      triggerRef(groupCache)
    } catch {
      // 静默失败，下次访问时重新尝试
    }
  }

  function _scheduleFlush() {
    if (flushScheduled) return
    flushScheduled = true
    queueMicrotask(() => _flushPending())
  }

  /**
   * 同步获取用户昵称；缓存未命中时返回 QQ 号字符串，并自动调度批量解析。
   */
  function getUserName(qq: number): string {
    const cached = userCache.value.get(qq)
    if (cached) return cached.nickname
    pendingUserIds.add(qq)
    _scheduleFlush()
    return String(qq)
  }

  /**
   * 同步获取群名称；缓存未命中时返回群号字符串，并自动调度批量解析。
   */
  function getGroupName(groupId: number): string {
    const cached = groupCache.value.get(groupId)
    if (cached) return cached.group_name
    pendingGroupIds.add(groupId)
    _scheduleFlush()
    return String(groupId)
  }

  /**
   * 主动预取一批 ID，在数据加载完成后立即调用以减少渲染闪烁。
   */
  function prefetchIds(userIds: number[], groupIds: number[]) {
    userIds.forEach((id) => {
      if (!userCache.value.has(id)) pendingUserIds.add(id)
    })
    groupIds.forEach((id) => {
      if (!groupCache.value.has(id)) pendingGroupIds.add(id)
    })
    _scheduleFlush()
  }

  /**
   * 清空解析缓存（在数据同步完成后调用）。
   */
  function clearCache() {
    userCache.value.clear()
    groupCache.value.clear()
    triggerRef(userCache)
    triggerRef(groupCache)
  }

  // ── 超级管理员 ──
  const admins = ref<UserItem[]>([])
  const adminsLoading = ref(false)

  async function loadAdmins() {
    adminsLoading.value = true
    try {
      admins.value = await api.fetchAdmins()
    } finally {
      adminsLoading.value = false
    }
  }

  async function setAdmin(qq: number) {
    await api.addAdmin(qq)
    await loadAdmins()
  }

  async function unsetAdmin(qq: number) {
    await api.removeAdmin(qq)
    await loadAdmins()
  }

  return {
    // 用户
    users,
    usersLoading,
    loadUsers,
    currentUser,
    currentUserGroups,
    loadUser,
    loadUserGroups,
    // 群
    groups,
    groupsLoading,
    loadGroups,
    groupMembers,
    membersLoading,
    loadGroupMembers,
    // 非共享状态获取函数
    fetchUserDetail,
    fetchMemberDetail,
    fetchGroupDetail,
    // 会话选择器
    sessionGroups,
    sessionUsers,
    sessionLoading,
    loadSessionData,
    // 同步
    syncStatus,
    syncLoading,
    loadSyncStatus,
    doSync,
    // 超级管理员
    admins,
    adminsLoading,
    loadAdmins,
    setAdmin,
    unsetAdmin,
    // ID 解析缓存
    getUserName,
    getGroupName,
    prefetchIds,
    clearCache,
  }
})
