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
import type { FeatureItem, PermissionMatrix } from '@/apis/permission'
import {
  updateFeatureInTree,
  applyGroupFeaturePermissions,
  applyGroupSwitch as applyGroupSwitchUtil,
} from '@/utils/tree'

export const usePermissionStore = defineStore('permission', () => {
  // ── 状态 ──
  const features = ref<FeatureItem[]>([])
  const matrix = ref<PermissionMatrix | null>(null)
  const privateUsers = ref<Record<string, number[]>>({})
  const loading = ref(false)
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

  async function patchFeature(name: string, enabled?: boolean, privateMode?: string) {
    const payload: Record<string, unknown> = {}
    if (enabled !== undefined) payload.enabled = enabled
    if (privateMode !== undefined) payload.private_mode = privateMode
    await updateFeature(name, payload)
    updateFeatureInTree(features.value, name, enabled, privateMode)
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
    const users = await fetchPrivateUsers(featureName)
    privateUsers.value[featureName] = users
  }

  async function addUser(featureName: string, userQq: number) {
    await addPrivateUser(featureName, userQq)
    if (!privateUsers.value[featureName]) {
      privateUsers.value[featureName] = []
    }
    if (!privateUsers.value[featureName].includes(userQq)) {
      privateUsers.value[featureName].push(userQq)
    }
  }

  async function removeUser(featureName: string, userQq: number) {
    await removePrivateUser(featureName, userQq)
    if (privateUsers.value[featureName]) {
      privateUsers.value[featureName] = privateUsers.value[featureName].filter(
        (qq) => qq !== userQq,
      )
    }
  }

  return {
    features,
    matrix,
    privateUsers,
    loading,
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
  }
})
