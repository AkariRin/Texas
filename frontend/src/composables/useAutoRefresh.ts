/** 自动刷新组合式函数 —— 周期性调用指定函数。 */

import { onMounted, onUnmounted } from 'vue'

export function useAutoRefresh(fn: () => Promise<void> | void, intervalMs: number = 10000) {
  let timer: ReturnType<typeof setInterval> | null = null

  onMounted(() => {
    fn()
    timer = setInterval(fn, intervalMs)
  })

  onUnmounted(() => {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  })
}

