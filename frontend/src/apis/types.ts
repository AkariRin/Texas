/**
 * API 公共类型 —— 跨模块共享的请求/响应类型定义。
 */

/** 统一 API 响应包装 */
export interface ApiResponse<T> {
  code: number
  data: T
  message: string
}

/** 分页查询结果 */
export interface PaginatedResult<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}
