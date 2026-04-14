/**
 * 权限管理 Pinia Store。
 */

import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import {
  fetchFeatures,
  fetchPermissionMatrix,
  fetchPrivateUsers,
  updateFeature,
  setGroupFeatures,
  setGroupSwitch,
  addPrivateUser,
  removePrivateUser,
} from '@/apis/permission'
import type { FeatureItem, PermissionMatrix, PrivatePermission } from '@/apis/permission'
import {
  updateFeatureInTree,
  applyGroupFeaturePermissions,
  applyGroupSwitch as applyGroupSwitchUtil,
} from '@/utils/tree'

export const usePermissionStore = defineStore('permission', () => {
  // ── 状态 ──
  const features = ref<FeatureItem[]>([])
  const matrix = ref<PermissionMatrix | null>(null)
  const privateUsers = ref<Record<string, PrivatePermission[]>>({})
  const loading = ref(false)
  const privateUsersLoading = ref(false)
  const error = ref<string | null>(null)

  // ── 计算属性 ──
  const controllerFeatures = computed(() =>
    features.value.filter((f) => f.parent === null && f.is_active),
  )

  /** 矩阵中所有功能名（controller + method 两级），用于统计 */
  const allMatrixFeatureNames = computed((): string[] => {
    if (!matrix.value) return []
    const names: string[] = []
    for (const ctrl of matrix.value.features) {
      names.push(ctrl.name)
      for (const child of ctrl.children) {
        names.push(child.name)
      }
    }
    return names
  })

  /** 计算某群已启用的功能数量 */
  function groupEnabledCount(permissions: Record<string, boolean>): number {
    return allMatrixFeatureNames.value.filter((name) => permissions[name] !== false).length
  }

  /** 矩阵中所有功能总数（controller + method） */
  const totalMatrixFeatureCount = computed((): number => allMatrixFeatureNames.value.length)

  // ── Actions ──

  async function loadFeatures() {
    loading.value = true
    error.value = null
    try {
      features.value = await fetchFeatures()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '加载功能列表失败'
    } finally {
      loading.value = false
    }
  }

  async function loadMatrix() {
    loading.value = true
    error.value = null
    try {
      matrix.value = await fetchPermissionMatrix()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '加载权限矩阵失败'
    } finally {
      loading.value = false
    }
  }

  async function patchFeature(name: string, enabled?: boolean) {
    const payload: Record<string, unknown> = {}
    if (enabled !== undefined) payload.enabled = enabled
    try {
      await updateFeature(name, payload)
      updateFeatureInTree(features.value, name, enabled)
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '更新功能配置失败'
      throw e
    }
  }

  async function saveGroupFeatures(
    groupId: number,
    items: { feature_name: string; enabled: boolean }[],
  ) {
    await setGroupFeatures(groupId, { features: items })
    if (matrix.value) applyGroupFeaturePermissions(matrix.value.groups, groupId, items)
  }

  async function toggleGroupSwitch(groupId: number, enabled: boolean) {
    await setGroupSwitch(groupId, enabled)
    if (matrix.value) applyGroupSwitchUtil(matrix.value.groups, groupId, enabled)
  }

  async function loadPrivateUsers(featureName: string) {
    privateUsersLoading.value = true
    try {
      const users = await fetchPrivateUsers(featureName)
      privateUsers.value[featureName] = users
    } finally {
      privateUsersLoading.value = false
    }
  }

  async function addUser(featureName: string, userQq: number, enabled: boolean = true) {
    try {
      await addPrivateUser(featureName, userQq, enabled)
      if (!privateUsers.value[featureName]) {
        privateUsers.value[featureName] = []
      }
      const list = privateUsers.value[featureName]!
      const existing = list.findIndex((p) => p.user_qq === userQq)
      if (existing >= 0) {
        list[existing]!.enabled = enabled
      } else {
        list.push({ user_qq: userQq, enabled })
      }
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '添加用户失败'
      throw e
    }
  }

  async function removeUser(featureName: string, userQq: number) {
    try {
      await removePrivateUser(featureName, userQq)
      if (privateUsers.value[featureName]) {
        privateUsers.value[featureName] = privateUsers.value[featureName].filter(
          (p) => p.user_qq !== userQq,
        )
      }
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '移除用户失败'
      throw e
    }
  }

  async function togglePrivateUser(featureName: string, userQq: number, enabled: boolean) {
    try {
      await addPrivateUser(featureName, userQq, enabled)
      const list = privateUsers.value[featureName]
      if (list) {
        const existing = list.findIndex((p) => p.user_qq === userQq)
        if (existing >= 0) {
          list[existing]!.enabled = enabled
        }
      }
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '更新用户权限失败'
      throw e
    }
  }

  return {
    features,
    matrix,
    privateUsers,
    loading,
    privateUsersLoading,
    error,
    controllerFeatures,
    allMatrixFeatureNames,
    totalMatrixFeatureCount,
    groupEnabledCount,
    loadFeatures,
    loadMatrix,
    patchFeature,
    saveGroupFeatures,
    toggleGroupSwitch,
    loadPrivateUsers,
    addUser,
    removeUser,
    togglePrivateUser,
  }
})
