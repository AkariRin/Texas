/** 处理器状态管理。 */

import { ref } from 'vue'
import { defineStore } from 'pinia'
import type { ControllerInfo } from '@/types/handler'
import { fetchHandlers } from '@/api/handlers'

export const useHandlersStore = defineStore('handlers', () => {
  const controllers = ref<ControllerInfo[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function loadControllers() {
    loading.value = true
    error.value = null
    try {
      controllers.value = await fetchHandlers()
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Unknown error'
    } finally {
      loading.value = false
    }
  }

  return { controllers, loading, error, loadControllers }
})

