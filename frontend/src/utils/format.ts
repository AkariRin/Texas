/**
 * 通用格式化工具函数
 */

/**
 * 将 ISO 时间字符串格式化为本地时间。
 * @param iso ISO 8601 时间字符串，null 时返回 '-'
 */
export function formatTime(iso: string | null | undefined): string {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleString('zh-CN')
  } catch {
    return iso
  }
}

/**
 * 将 Unix 时间戳（秒）格式化为本地时间。
 * @param ts 秒级时间戳，0 或 undefined 时返回 '-'
 */
export function formatTimestamp(ts: number | undefined): string {
  if (!ts || ts <= 0) return '-'
  try {
    return new Date(ts * 1000).toLocaleString('zh-CN')
  } catch {
    return String(ts)
  }
}

/**
 * 将数字格式化为带千位分隔符的字符串。
 * @param n 整数
 */
export function formatNumber(n: number): string {
  return n.toLocaleString()
}

/**
 * 将字节数格式化为可读字符串（B / KB / MB / GB）。
 * @param bytes 字节数
 */
export function formatBytes(bytes: number): string {
  if (!bytes || bytes < 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const size = bytes / Math.pow(1024, i)
  return `${size.toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}
