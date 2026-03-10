/**
 * LLM API 服务层 —— 封装 /api/v1/llm 所有后端接口调用。
 */

import axios from 'axios'

// ── 类型定义 ──

export interface ProviderItem {
  id: string
  name: string
  api_base: string
  api_key_masked: string
  max_retries: number
  timeout: number
  retry_interval: number
  is_enabled: boolean
  model_count: number
}

export interface ProviderDetail extends ProviderItem {
  models: ModelItem[]
}

export interface ProviderCreateData {
  name: string
  api_base: string
  api_key: string
  max_retries?: number
  timeout?: number
  retry_interval?: number
}

export interface ProviderUpdateData {
  name?: string
  api_base?: string
  api_key?: string
  max_retries?: number
  timeout?: number
  retry_interval?: number
}

export interface ModelItem {
  id: string
  provider_id: string
  provider_name: string
  model_name: string
  display_name: string | null
  input_price: number
  output_price: number
  temperature: number
  max_tokens: number | null
  force_stream: boolean
  extra_params: Record<string, unknown>
  is_enabled: boolean
}

export interface ModelCreateData {
  provider_id: string
  model_name: string
  display_name?: string | null
  input_price?: number
  output_price?: number
  temperature?: number
  max_tokens?: number | null
  force_stream?: boolean
  extra_params?: Record<string, unknown>
  is_enabled?: boolean
}

export interface ModelUpdateData {
  display_name?: string | null
  input_price?: number
  output_price?: number
  temperature?: number
  max_tokens?: number | null
  force_stream?: boolean
  extra_params?: Record<string, unknown>
  is_enabled?: boolean
}

export interface ChatMessage {
  role: string
  content: string
}

export interface ChatUsage {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
}

export interface ChatResponse {
  content: string
  model: string
  usage: ChatUsage
}

export interface TestResult {
  success: boolean
  message: string
  model?: string | null
}

interface ApiResponse<T> {
  code: number
  data: T
  message: string
}

// ── API 调用 ──

const BASE = '/api/v1/llm'

// ── 提供商 ──

export async function fetchProviders(): Promise<ProviderItem[]> {
  const { data } = await axios.get<ApiResponse<ProviderItem[]>>(`${BASE}/providers`)
  return data.data
}

export async function fetchProvider(id: string): Promise<ProviderDetail> {
  const { data } = await axios.get<ApiResponse<ProviderDetail>>(`${BASE}/providers/${id}`)
  return data.data
}

export async function createProvider(payload: ProviderCreateData): Promise<ProviderItem> {
  const { data } = await axios.post<ApiResponse<ProviderItem>>(`${BASE}/providers`, payload)
  return data.data
}

export async function updateProvider(
  id: string,
  payload: ProviderUpdateData,
): Promise<ProviderItem> {
  const { data } = await axios.post<ApiResponse<ProviderItem>>(
    `${BASE}/providers/${id}`,
    payload,
  )
  return data.data
}

export async function deleteProvider(id: string): Promise<void> {
  await axios.post<ApiResponse<null>>(`${BASE}/providers/${id}/delete`)
}

export async function testProvider(id: string): Promise<TestResult> {
  const { data } = await axios.post<ApiResponse<TestResult>>(`${BASE}/providers/${id}/test`)
  return data.data
}

// ── 模型 ──

export async function fetchModels(providerId?: string): Promise<ModelItem[]> {
  const params: Record<string, string> = {}
  if (providerId) params.provider_id = providerId
  const { data } = await axios.get<ApiResponse<ModelItem[]>>(`${BASE}/models`, { params })
  return data.data
}

export async function fetchModel(id: string): Promise<ModelItem> {
  const { data } = await axios.get<ApiResponse<ModelItem>>(`${BASE}/models/${id}`)
  return data.data
}

export async function createModel(payload: ModelCreateData): Promise<ModelItem> {
  const { data } = await axios.post<ApiResponse<ModelItem>>(`${BASE}/models`, payload)
  return data.data
}

export async function updateModel(id: string, payload: ModelUpdateData): Promise<ModelItem> {
  const { data } = await axios.post<ApiResponse<ModelItem>>(`${BASE}/models/${id}`, payload)
  return data.data
}

export async function deleteModel(id: string): Promise<void> {
  await axios.post<ApiResponse<null>>(`${BASE}/models/${id}/delete`)
}

// ── Chat (非流式) ──

export async function chat(
  modelId: string,
  messages: ChatMessage[],
  options?: { temperature?: number; max_tokens?: number },
): Promise<ChatResponse> {
  const { data } = await axios.post<ApiResponse<ChatResponse>>(`${BASE}/chat`, {
    model_id: modelId,
    messages,
    stream: false,
    ...options,
  })
  return data.data
}

// ── Chat (流式 SSE) ──

export async function chatStream(
  modelId: string,
  messages: ChatMessage[],
  onChunk: (text: string) => void,
  onDone: () => void,
  onError?: (err: string) => void,
  options?: { temperature?: number; max_tokens?: number },
): Promise<void> {
  const response = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model_id: modelId,
      messages,
      stream: true,
      ...options,
    }),
  })

  if (!response.ok) {
    const text = await response.text()
    onError?.(text)
    return
  }

  const reader = response.body?.getReader()
  if (!reader) {
    onError?.('No readable stream')
    return
  }

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed || !trimmed.startsWith('data: ')) continue
      const payload = trimmed.slice(6)
      if (payload === '[DONE]') {
        onDone()
        return
      }
      try {
        const parsed = JSON.parse(payload)
        if (parsed.error) {
          onError?.(parsed.error)
          return
        }
        if (parsed.content) {
          onChunk(parsed.content)
        }
      } catch {
        // skip malformed JSON
      }
    }
  }
  onDone()
}

