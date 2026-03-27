/**
 * UI 交互工具函数
 */

/**
 * 创建一个防抖函数。
 * @param fn 要防抖的函数
 * @param delay 延迟毫秒数，默认 400ms
 */
export function debounce<T extends (...args: unknown[]) => void>(
  fn: T,
  delay = 400,
): (...args: Parameters<T>) => void {
  let timer: ReturnType<typeof setTimeout> | null = null
  return (...args: Parameters<T>) => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => fn(...args), delay)
  }
}
