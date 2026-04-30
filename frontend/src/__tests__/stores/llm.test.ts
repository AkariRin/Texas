import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useLLMStore } from '@/stores/llm'

// mock 整个 API 模块
vi.mock('@/apis/llm', () => ({
  fetchProviders: vi.fn(),
  fetchProvider: vi.fn(),
  deleteProvider: vi.fn(),
  fetchModels: vi.fn(),
  createProvider: vi.fn(),
  updateProvider: vi.fn(),
  testProvider: vi.fn(),
  createModel: vi.fn(),
  updateModel: vi.fn(),
  deleteModel: vi.fn(),
}))

import * as llmApi from '@/apis/llm'

const mockProvider = {
  id: 'p1',
  name: 'OpenAI',
  api_base: 'https://api.openai.com/v1',
  api_key_masked: 'sk-****',
  max_retries: 3,
  timeout: 30,
  retry_interval: 1,
  is_enabled: true,
  model_count: 2,
}

const mockProviderDetail = {
  ...mockProvider,
  models: [],
}

const mockModel = {
  id: 'm1',
  provider_id: 'p1',
  provider_name: 'OpenAI',
  model_name: 'gpt-4o',
  display_name: 'GPT-4o',
  input_price: 0.005,
  output_price: 0.015,
  temperature: 0.7,
  max_tokens: 4096,
  force_stream: false,
  extra_params: {},
}

describe('useLLMStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  // ── 测试组 1：初始状态 ──

  describe('初始状态', () => {
    it('providers 初始为空数组', () => {
      const store = useLLMStore()
      expect(store.providers).toEqual([])
    })

    it('providersLoading 初始为 false', () => {
      const store = useLLMStore()
      expect(store.providersLoading).toBe(false)
    })

    it('currentProvider 初始为 null', () => {
      const store = useLLMStore()
      expect(store.currentProvider).toBeNull()
    })

    it('models 初始为空数组', () => {
      const store = useLLMStore()
      expect(store.models).toEqual([])
    })

    it('modelsLoading 初始为 false', () => {
      const store = useLLMStore()
      expect(store.modelsLoading).toBe(false)
    })
  })

  // ── 测试组 2：loadProviders() ──

  describe('loadProviders()', () => {
    it('成功时将 API 返回值赋给 providers', async () => {
      vi.mocked(llmApi.fetchProviders).mockResolvedValue([mockProvider])
      const store = useLLMStore()

      await store.loadProviders()

      expect(store.providers).toEqual([mockProvider])
    })

    it('加载过程中 providersLoading 为 true，结束后为 false', async () => {
      let resolveProviders!: (value: (typeof mockProvider)[]) => void
      vi.mocked(llmApi.fetchProviders).mockReturnValue(
        new Promise<(typeof mockProvider)[]>((resolve) => {
          resolveProviders = resolve
        }),
      )
      const store = useLLMStore()

      const loadingStates: boolean[] = []
      const loadPromise = store.loadProviders()

      // 调用开始后，loading 应为 true
      loadingStates.push(store.providersLoading)

      // 解析 Promise，让加载完成
      resolveProviders([mockProvider])
      await loadPromise

      // 完成后 loading 应为 false
      loadingStates.push(store.providersLoading)

      expect(loadingStates[0]).toBe(true)
      expect(loadingStates[1]).toBe(false)
    })

    it('API 抛出异常时 providersLoading 仍恢复为 false', async () => {
      vi.mocked(llmApi.fetchProviders).mockRejectedValue(new Error('网络错误'))
      const store = useLLMStore()

      await expect(store.loadProviders()).rejects.toThrow()
      expect(store.providersLoading).toBe(false)
    })
  })

  // ── 测试组 3：loadProvider() 失败 ──

  describe('loadProvider() 失败', () => {
    it('API 抛出异常时 currentProvider 被设为 null', async () => {
      vi.mocked(llmApi.fetchProvider).mockRejectedValue(new Error('404'))
      const store = useLLMStore()
      // 先设置一个非 null 值，确认失败后会清空
      store.currentProvider = mockProviderDetail

      await expect(store.loadProvider('p1')).rejects.toThrow()
      expect(store.currentProvider).toBeNull()
    })

    it('失败时重新抛出 "加载提供商详情失败" 错误', async () => {
      vi.mocked(llmApi.fetchProvider).mockRejectedValue(new Error('服务器错误'))
      const store = useLLMStore()

      await expect(store.loadProvider('p1')).rejects.toThrow('加载提供商详情失败')
    })

    it('成功时 currentProvider 被更新为 API 返回值', async () => {
      vi.mocked(llmApi.fetchProvider).mockResolvedValue(mockProviderDetail)
      const store = useLLMStore()

      await store.loadProvider('p1')

      expect(store.currentProvider).toEqual(mockProviderDetail)
    })
  })

  // ── 测试组 4：loadModels() ──

  describe('loadModels()', () => {
    it('成功时 models 被更新为 API 返回值', async () => {
      vi.mocked(llmApi.fetchModels).mockResolvedValue([mockModel])
      const store = useLLMStore()

      await store.loadModels()

      expect(store.models).toEqual([mockModel])
    })

    it('modelsLoading 加载时为 true，结束后为 false', async () => {
      let resolveModels!: (value: (typeof mockModel)[]) => void
      vi.mocked(llmApi.fetchModels).mockReturnValue(
        new Promise<(typeof mockModel)[]>((resolve) => {
          resolveModels = resolve
        }),
      )
      const store = useLLMStore()

      const loadPromise = store.loadModels()

      // 调用开始后，loading 应为 true
      const loadingDuringFetch = store.modelsLoading

      resolveModels([mockModel])
      await loadPromise

      expect(loadingDuringFetch).toBe(true)
      expect(store.modelsLoading).toBe(false)
    })

    it('传入 providerId 时 fetchModels 收到正确参数', async () => {
      vi.mocked(llmApi.fetchModels).mockResolvedValue([mockModel])
      const store = useLLMStore()

      await store.loadModels('p1')

      expect(llmApi.fetchModels).toHaveBeenCalledWith('p1')
    })

    it('不传 providerId 时 fetchModels 以 undefined 调用', async () => {
      vi.mocked(llmApi.fetchModels).mockResolvedValue([])
      const store = useLLMStore()

      await store.loadModels()

      expect(llmApi.fetchModels).toHaveBeenCalledWith(undefined)
    })

    it('API 抛出异常时 modelsLoading 仍恢复为 false', async () => {
      vi.mocked(llmApi.fetchModels).mockRejectedValue(new Error('网络错误'))
      const store = useLLMStore()

      await expect(store.loadModels()).rejects.toThrow()
      expect(store.modelsLoading).toBe(false)
    })
  })
})
