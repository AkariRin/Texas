/**
 * 共享 HTTP 客户端 —— 统一配置 axios 实例，含错误处理拦截器。
 */

import axios from 'axios'

const http = axios.create({
  timeout: 30000,
})

http.interceptors.response.use(
  (response) => response,
  (error) => {
    const status: number | undefined = error.response?.status
    const message: string = error.response?.data?.message ?? error.message ?? '请求失败'

    if (status === 401) {
      console.error('[API] 未授权，请检查登录状态')
    } else if (status === 403) {
      console.error('[API] 权限不足')
    } else if (status && status >= 500) {
      console.error(`[API] 服务器错误 (${status}): ${message}`)
    } else {
      console.error(`[API] 请求失败: ${message}`)
    }

    return Promise.reject(error)
  },
)

export default http
