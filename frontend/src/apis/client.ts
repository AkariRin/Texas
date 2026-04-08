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
    const status = error?.response?.status
    if (status === 401) {
      console.error('[HTTP 401] 未授权，请检查访问权限配置', error.config?.url)
    } else if (status === 403) {
      console.error('[HTTP 403] 无权限访问该资源', error.config?.url)
    }
    return Promise.reject(error)
  },
)

export default http
