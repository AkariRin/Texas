/**
 * 路由守卫 —— 未登录时跳转到 /login，保留来源路径。
 */

import type { Router } from 'vue-router'
import { getSession } from '@/apis/auth'

/** 简单登录状态缓存（避免每次导航都请求 API）*/
let _isLoggedIn: boolean | null = null

export function resetLoginState() {
  _isLoggedIn = null
}

async function checkLogin(): Promise<boolean> {
  if (_isLoggedIn !== null) return _isLoggedIn
  try {
    await getSession()
    _isLoggedIn = true
    return true
  } catch {
    _isLoggedIn = false
    return false
  }
}

export function installGuards(router: Router) {
  router.beforeEach(async (to, _from, next) => {
    // /login 页不需要守卫
    if (to.path === '/login') {
      next()
      return
    }

    // 检查 requiresAuth meta（默认所有页面均需要鉴权）
    const requiresAuth = to.meta.requiresAuth !== false

    if (requiresAuth) {
      const loggedIn = await checkLogin()
      if (!loggedIn) {
        next({ path: '/login', query: { redirect: to.fullPath } })
        return
      }
    }

    next()
  })
}
