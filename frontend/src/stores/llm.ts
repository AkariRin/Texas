/**
 * LLM Pinia Store —— 管理 LLM 提供商与模型状态。
 */

import { ref } from 'vue'
import { defineStore } from 'pinia'
import * as api from '@/apis/llm'
import type { ProviderItem, ProviderDetail, ModelItem } from '@/apis/llm'

export const useLLMStore = defineStore('llm', () => {
  // ── 提供商列表 ──
  const providers = ref<ProviderItem[]>([])
  const providersLoading = ref(false)

  async function loadProviders() {
    providersLoading.value = true
    try {
      providers.value = await api.fetchProviders()
    } finally {
      providersLoading.value = false
    }
  }

  // ── 提供商详情 ──
  const currentProvider = ref<ProviderDetail | null>(null)

  async function loadProvider(id: string) {
    try {
      currentProvider.value = await api.fetchProvider(id)
    } catch {
      currentProvider.value = null
      throw new Error('加载提供商详情失败')
    }
  }

  async function createProvider(data: api.ProviderCreateData) {
    await api.createProvider(data)
    await loadProviders()
  }

  async function updateProvider(id: string, data: api.ProviderUpdateData) {
    await api.updateProvider(id, data)
    await loadProviders()
  }

  async function deleteProvider(id: string) {
    await api.deleteProvider(id)
    await loadProviders()
  }

  async function testProvider(id: string) {
    return await api.testProvider(id)
  }

  // ── 模型列表 ──
  const models = ref<ModelItem[]>([])
  const modelsLoading = ref(false)

  async function loadModels(providerId?: string) {
    modelsLoading.value = true
    try {
      models.value = await api.fetchModels(providerId)
    } finally {
      modelsLoading.value = false
    }
  }

  async function createModel(data: api.ModelCreateData) {
    await api.createModel(data)
    await loadModels()
  }

  async function updateModel(id: string, data: api.ModelUpdateData) {
    await api.updateModel(id, data)
    await loadModels()
  }

  async function deleteModel(id: string) {
    await api.deleteModel(id)
    await loadModels()
  }

  return {
    // 提供商
    providers,
    providersLoading,
    loadProviders,
    currentProvider,
    loadProvider,
    createProvider,
    updateProvider,
    deleteProvider,
    testProvider,
    // 模型
    models,
    modelsLoading,
    loadModels,
    createModel,
    updateModel,
    deleteModel,
  }
})
