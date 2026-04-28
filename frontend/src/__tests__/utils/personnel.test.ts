import { describe, it, expect } from 'vitest'
import {
  relationColor,
  relationLabel,
  relationIcon,
  roleColor,
  roleLabel,
  activeColor,
  activeLabel,
  roleOptions,
} from '@/utils/personnel'

describe('relationColor', () => {
  it.each([
    ['stranger', 'grey'],
    ['group_member', 'blue'],
    ['friend', 'green'],
    ['admin', 'red'],
  ])('%s 返回 %s', (input, expected) => {
    expect(relationColor(input)).toBe(expected)
  })

  it('未知关系返回 grey', () => {
    expect(relationColor('unknown')).toBe('grey')
  })
})

describe('relationLabel', () => {
  it.each([
    ['stranger', '陌生人'],
    ['group_member', '群友'],
    ['friend', '好友'],
    ['admin', '管理员'],
  ])('%s 返回 %s', (input, expected) => {
    expect(relationLabel(input)).toBe(expected)
  })

  it('未知关系原样返回', () => {
    expect(relationLabel('xyz')).toBe('xyz')
  })
})

describe('relationIcon', () => {
  it('stranger 返回 mdi-account-outline', () => {
    expect(relationIcon('stranger')).toBe('mdi-account-outline')
  })

  it('未知关系返回默认图标', () => {
    expect(relationIcon('unknown')).toBe('mdi-account')
  })
})

describe('roleColor', () => {
  it.each([
    ['owner', 'amber'],
    ['admin', 'green'],
    ['member', 'grey'],
  ])('%s 返回 %s', (input, expected) => {
    expect(roleColor(input)).toBe(expected)
  })

  it('undefined 返回 grey', () => {
    expect(roleColor(undefined)).toBe('grey')
  })
})

describe('roleLabel', () => {
  it.each([
    ['owner', '群主'],
    ['admin', '管理员'],
    ['member', '成员'],
  ])('%s 返回 %s', (input, expected) => {
    expect(roleLabel(input)).toBe(expected)
  })

  it('undefined 返回空字符串', () => {
    expect(roleLabel(undefined)).toBe('')
  })
})

describe('activeColor / activeLabel', () => {
  it('true 返回 success / 活跃', () => {
    expect(activeColor(true)).toBe('success')
    expect(activeLabel(true)).toBe('活跃')
  })

  it('false 返回 grey / 已退出', () => {
    expect(activeColor(false)).toBe('grey')
    expect(activeLabel(false)).toBe('已退出')
  })
})

describe('roleOptions', () => {
  it('含 3 项且字段完整', () => {
    expect(roleOptions).toHaveLength(3)
    for (const o of roleOptions) {
      expect(o).toHaveProperty('title')
      expect(o).toHaveProperty('value')
    }
  })
})
