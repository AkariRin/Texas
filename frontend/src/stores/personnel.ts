/**
 * Personnel Pinia Store —— 管理用户数据状态。
 */

import { ref } from 'vue'
import { defineStore } from 'pinia'
import * as api from '@/apis/personnel'
import type {
  UserItem,
  UserDetail,
  GroupItem,
  GroupMemberItem,
  SyncStatus,
  PaginatedResult,
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
    },
  ) {
    membersLoading.value = true
    try {
      groupMembers.value = await api.fetchGroupMembers(groupId, params)
    } finally {
      membersLoading.value = false
    }
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
      // 延迟后刷新状态
      setTimeout(() => loadSyncStatus(), 2000)
    } finally {
      syncLoading.value = false
    }
  }

  // ── 管理员 ──
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
    // 同步
    syncStatus,
    syncLoading,
    loadSyncStatus,
    doSync,
    // 管理员
    admins,
    adminsLoading,
    loadAdmins,
    setAdmin,
    unsetAdmin,
  }
})
