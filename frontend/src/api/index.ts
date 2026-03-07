/** 后端 API 调用的 HTTP 客户端封装。 */

import type { ApiResponse } from '@/types/api'

const API_BASE = '/api/v1'

class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!response.ok) {
    throw new ApiError(`HTTP ${response.status}: ${response.statusText}`, response.status)
  }
  return response.json() as Promise<T>
}

export async function get<T>(url: string): Promise<ApiResponse<T>> {
  return request<ApiResponse<T>>(url)
}

export async function post<T>(url: string, body?: unknown): Promise<ApiResponse<T>> {
  return request<ApiResponse<T>>(url, {
    method: 'POST',
    body: body ? JSON.stringify(body) : undefined,
  })
}

export async function put<T>(url: string, body?: unknown): Promise<ApiResponse<T>> {
  return request<ApiResponse<T>>(url, {
    method: 'PUT',
    body: body ? JSON.stringify(body) : undefined,
  })
}

export { ApiError }

