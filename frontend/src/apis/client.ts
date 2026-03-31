/**
 * 共享 HTTP 客户端 —— 统一配置 axios 实例，含错误处理拦截器。
 */

import axios from 'axios'
import router from '@/router'

const http = axios.create({
  timeout: 30000,
})

http.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // 重置登录状态缓存，避免守卫使用旧的 cached 状态
      const { resetLoginState } = await import('@/router/guards')
      resetLoginState()
      // 跳转登录页，保留来源路径用于登录后重定向
      const currentPath = router.currentRoute.value.fullPath
      if (currentPath !== '/login') {
        router.push({ path: '/login', query: { redirect: currentPath } })
      }
    }
    return Promise.reject(error)
  },
)

export default http
