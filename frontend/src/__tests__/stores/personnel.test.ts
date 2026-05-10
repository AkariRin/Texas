import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { usePersonnelStore } from '@/stores/personnel'

vi.mock('@/apis/personnel', () => ({
  fetchUsers: vi.fn(),
  fetchUser: vi.fn(),
  fetchUserGroups: vi.fn(),
  fetchGroups: vi.fn(),
  fetchGroup: vi.fn(),
  fetchGroupMembers: vi.fn(),
  fetchSyncStatus: vi.fn(),
  triggerSync: vi.fn(),
  fetchAdmins: vi.fn(),
  addAdmin: vi.fn(),
  removeAdmin: vi.fn(),
  resolvePersonnel: vi.fn(),
}))

import * as api from '@/apis/personnel'

const mockPaginatedUsers = {
  items: [{ qq: 1, nickname: 'Alice' }],
  total: 1,
  page: 1,
  page_size: 20,
  pages: 1,
}
const mockPaginatedGroups = {
  items: [{ group_id: 100, group_name: 'TestGroup' }],
  total: 1,
  page: 1,
  page_size: 20,
  pages: 1,
}
const mockPaginatedMembers = {
  items: [{ qq: 1, nickname: 'Alice', role: 'member' }],
  total: 1,
  page: 1,
  page_size: 20,
  pages: 1,
}
const mockUserDetail = { qq: 1, nickname: 'Alice', sex: 'male', age: 20 }
const mockSyncStatus = { last_sync: '2024-01-01T00:00:00Z', is_syncing: false }

describe('usePersonnelStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  // ── 初始状态 ──

  describe('初始状态', () => {
    it('users 初始为空分页结构', () => {
      const store = usePersonnelStore()
      expect(store.users.items).toEqual([])
      expect(store.users.total).toBe(0)
    })

    it('usersLoading 初始为 false', () => {
      const store = usePersonnelStore()
      expect(store.usersLoading).toBe(false)
    })

    it('currentUser 初始为 null', () => {
      const store = usePersonnelStore()
      expect(store.currentUser).toBeNull()
    })

    it('groups 初始为空分页结构', () => {
      const store = usePersonnelStore()
      expect(store.groups.items).toEqual([])
    })

    it('syncStatus 初始为 null', () => {
      const store = usePersonnelStore()
      expect(store.syncStatus).toBeNull()
    })

    it('admins 初始为空数组', () => {
      const store = usePersonnelStore()
      expect(store.admins).toEqual([])
    })
  })

  // ── loadUsers() ──

  describe('loadUsers()', () => {
    it('成功时更新 users', async () => {
      vi.mocked(api.fetchUsers).mockResolvedValue(mockPaginatedUsers)
      const store = usePersonnelStore()

      await store.loadUsers({})

      expect(store.users).toEqual(mockPaginatedUsers)
    })

    it('加载过程中 usersLoading 为 true，结束后为 false', async () => {
      let resolve!: (v: typeof mockPaginatedUsers) => void
      vi.mocked(api.fetchUsers).mockReturnValue(
        new Promise((r) => {
          resolve = r
        }),
      )
      const store = usePersonnelStore()

      const p = store.loadUsers({})
      expect(store.usersLoading).toBe(true)
      resolve(mockPaginatedUsers)
      await p
      expect(store.usersLoading).toBe(false)
    })

    it('API 抛出异常时 usersLoading 仍恢复为 false', async () => {
      vi.mocked(api.fetchUsers).mockRejectedValue(new Error('网络错误'))
      const store = usePersonnelStore()

      await expect(store.loadUsers({})).rejects.toThrow()
      expect(store.usersLoading).toBe(false)
    })
  })

  // ── loadUser() ──

  describe('loadUser()', () => {
    it('成功时更新 currentUser', async () => {
      vi.mocked(api.fetchUser).mockResolvedValue(mockUserDetail)
      const store = usePersonnelStore()

      await store.loadUser(1)

      expect(store.currentUser).toEqual(mockUserDetail)
    })

    it('失败时 currentUser 被设为 null 并重新抛出错误', async () => {
      vi.mocked(api.fetchUser).mockRejectedValue(new Error('404'))
      const store = usePersonnelStore()
      store.currentUser = mockUserDetail

      await expect(store.loadUser(1)).rejects.toThrow('加载用户详情失败')
      expect(store.currentUser).toBeNull()
    })
  })

  // ── loadGroups() ──

  describe('loadGroups()', () => {
    it('成功时更新 groups', async () => {
      vi.mocked(api.fetchGroups).mockResolvedValue(mockPaginatedGroups)
      const store = usePersonnelStore()

      await store.loadGroups({})

      expect(store.groups).toEqual(mockPaginatedGroups)
    })

    it('加载过程中 groupsLoading 为 true，结束后为 false', async () => {
      let resolve!: (v: typeof mockPaginatedGroups) => void
      vi.mocked(api.fetchGroups).mockReturnValue(
        new Promise((r) => {
          resolve = r
        }),
      )
      const store = usePersonnelStore()

      const p = store.loadGroups({})
      expect(store.groupsLoading).toBe(true)
      resolve(mockPaginatedGroups)
      await p
      expect(store.groupsLoading).toBe(false)
    })
  })

  // ── loadGroupMembers() ──

  describe('loadGroupMembers()', () => {
    it('成功时更新 groupMembers', async () => {
      vi.mocked(api.fetchGroupMembers).mockResolvedValue(mockPaginatedMembers)
      const store = usePersonnelStore()

      await store.loadGroupMembers(100, {})

      expect(store.groupMembers).toEqual(mockPaginatedMembers)
    })

    it('加载过程中 membersLoading 为 true，结束后为 false', async () => {
      let resolve!: (v: typeof mockPaginatedMembers) => void
      vi.mocked(api.fetchGroupMembers).mockReturnValue(
        new Promise((r) => {
          resolve = r
        }),
      )
      const store = usePersonnelStore()

      const p = store.loadGroupMembers(100, {})
      expect(store.membersLoading).toBe(true)
      resolve(mockPaginatedMembers)
      await p
      expect(store.membersLoading).toBe(false)
    })
  })

  // ── loadSyncStatus() ──

  describe('loadSyncStatus()', () => {
    it('成功时更新 syncStatus', async () => {
      vi.mocked(api.fetchSyncStatus).mockResolvedValue(mockSyncStatus)
      const store = usePersonnelStore()

      await store.loadSyncStatus()

      expect(store.syncStatus).toEqual(mockSyncStatus)
    })
  })

  // ── doSync() ──

  describe('doSync()', () => {
    it('调用 triggerSync 并在完成后 syncLoading 恢复为 false', async () => {
      vi.mocked(api.triggerSync).mockResolvedValue(undefined)
      vi.mocked(api.fetchSyncStatus).mockResolvedValue(mockSyncStatus)
      const store = usePersonnelStore()

      await store.doSync()

      expect(api.triggerSync).toHaveBeenCalledOnce()
      expect(store.syncLoading).toBe(false)
    })

    it('triggerSync 失败时 syncLoading 仍恢复为 false', async () => {
      vi.mocked(api.triggerSync).mockRejectedValue(new Error('同步失败'))
      const store = usePersonnelStore()

      await expect(store.doSync()).rejects.toThrow()
      expect(store.syncLoading).toBe(false)
    })
  })

  // ── loadAdmins() / setAdmin() / unsetAdmin() ──

  describe('管理员操作', () => {
    const mockAdmins = [{ qq: 1, nickname: 'Alice' }]

    it('loadAdmins() 成功时更新 admins', async () => {
      vi.mocked(api.fetchAdmins).mockResolvedValue(mockAdmins)
      const store = usePersonnelStore()

      await store.loadAdmins()

      expect(store.admins).toEqual(mockAdmins)
    })

    it('setAdmin() 调用 addAdmin 后刷新 admins', async () => {
      vi.mocked(api.addAdmin).mockResolvedValue(undefined)
      vi.mocked(api.fetchAdmins).mockResolvedValue(mockAdmins)
      const store = usePersonnelStore()

      await store.setAdmin(1)

      expect(api.addAdmin).toHaveBeenCalledWith(1)
      expect(store.admins).toEqual(mockAdmins)
    })

    it('unsetAdmin() 调用 removeAdmin 后刷新 admins', async () => {
      vi.mocked(api.removeAdmin).mockResolvedValue(undefined)
      vi.mocked(api.fetchAdmins).mockResolvedValue([])
      const store = usePersonnelStore()

      await store.unsetAdmin(1)

      expect(api.removeAdmin).toHaveBeenCalledWith(1)
      expect(store.admins).toEqual([])
    })
  })

  // ── ID 解析缓存 ──

  describe('getUserName() / getGroupName()', () => {
    it('缓存未命中时返回 QQ 号字符串', () => {
      const store = usePersonnelStore()
      expect(store.getUserName(12345)).toBe('12345')
    })

    it('缓存未命中时返回群号字符串', () => {
      const store = usePersonnelStore()
      expect(store.getGroupName(100)).toBe('100')
    })

    it('clearCache() 清空缓存后 getUserName 再次返回 ID 字符串', async () => {
      vi.mocked(api.resolvePersonnel).mockResolvedValue({
        users: { 1: { qq: 1, nickname: 'Alice' } },
        groups: {},
      })
      const store = usePersonnelStore()

      store.getUserName(1)
      await Promise.resolve() // 等待 microtask flush

      store.clearCache()
      expect(store.getUserName(1)).toBe('1')
    })
  })

  // ── loadSessionData() ──

  describe('loadSessionData()', () => {
    it('成功时更新 sessionGroups 和 sessionUsers', async () => {
      vi.mocked(api.fetchGroups).mockResolvedValue(mockPaginatedGroups)
      vi.mocked(api.fetchUsers).mockResolvedValue(mockPaginatedUsers)
      const store = usePersonnelStore()

      await store.loadSessionData()

      expect(store.sessionGroups).toEqual(mockPaginatedGroups.items)
      expect(store.sessionUsers).toEqual(mockPaginatedUsers.items)
    })

    it('API 失败时静默处理，sessionLoading 恢复为 false', async () => {
      vi.mocked(api.fetchGroups).mockRejectedValue(new Error('网络错误'))
      vi.mocked(api.fetchUsers).mockRejectedValue(new Error('网络错误'))
      const store = usePersonnelStore()

      await store.loadSessionData()

      expect(store.sessionLoading).toBe(false)
    })
  })
})
