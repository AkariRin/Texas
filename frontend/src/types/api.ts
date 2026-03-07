/** API response type definitions. */

export interface ApiResponse<T = unknown> {
  code: number
  data: T
  message: string
}

