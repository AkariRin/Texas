/**
 * 共享 HTTP 客户端 —— 统一配置 axios 实例，含错误处理拦截器。
 */

import axios from 'axios'

const http = axios.create({
  timeout: 30000,
})

http.interceptors.response.use(
  (response) => response,
  (error) => Promise.reject(error),
)

export default http
