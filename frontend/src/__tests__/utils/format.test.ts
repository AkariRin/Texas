import { describe, it, expect } from 'vitest'
import { formatTime, formatTimestamp, formatNumber, formatBytes } from '@/utils/format'

describe('formatTime', () => {
  it('null 输入返回 -', () => {
    expect(formatTime(null)).toBe('-')
  })

  it('undefined 输入返回 -', () => {
    expect(formatTime(undefined)).toBe('-')
  })

  it('空字符串返回 -', () => {
    expect(formatTime('')).toBe('-')
  })

  it('有效 ISO 字符串返回本地时间字符串', () => {
    const result = formatTime('2024-01-15T10:30:00.000Z')
    expect(typeof result).toBe('string')
    expect(result).not.toBe('-')
    expect(result.length).toBeGreaterThan(0)
  })
})

describe('formatTimestamp', () => {
  it('0 返回 -', () => {
    expect(formatTimestamp(0)).toBe('-')
  })

  it('undefined 返回 -', () => {
    expect(formatTimestamp(undefined)).toBe('-')
  })

  it('负数返回 -', () => {
    expect(formatTimestamp(-1)).toBe('-')
  })

  it('正数时间戳返回本地时间字符串', () => {
    const result = formatTimestamp(1705312200)
    expect(typeof result).toBe('string')
    expect(result).not.toBe('-')
  })
})

describe('formatNumber', () => {
  it('小数字不加分隔符', () => {
    expect(formatNumber(100)).toBe('100')
  })

  it('大数字加千位分隔符', () => {
    const result = formatNumber(1000000)
    // toLocaleString 在 jsdom 环境分隔符可能因 ICU 而异，用正则检查数字格式
    expect(result).toMatch(/1[\s,.]?000[\s,.]?000/)
  })

  it('0 返回 0', () => {
    expect(formatNumber(0)).toBe('0')
  })
})

describe('formatBytes', () => {
  it('0 返回 0 B', () => {
    expect(formatBytes(0)).toBe('0 B')
  })

  it('负数返回 0 B', () => {
    expect(formatBytes(-1)).toBe('0 B')
  })

  it('字节范围', () => {
    expect(formatBytes(500)).toBe('500 B')
  })

  it('KB 范围', () => {
    expect(formatBytes(1024)).toBe('1.0 KB')
  })

  it('MB 范围', () => {
    expect(formatBytes(1024 * 1024)).toBe('1.0 MB')
  })

  it('GB 范围', () => {
    expect(formatBytes(1024 * 1024 * 1024)).toBe('1.0 GB')
  })
})
