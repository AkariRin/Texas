import { describe, it, expect } from 'vitest'
import {
  statusColor,
  statusLabel,
  sourceLabel,
  typeColor,
  statusOptions,
  typeOptions,
  sourceOptions,
} from '@/utils/feedback'

describe('statusColor', () => {
  it('pending 返回 orange', () => {
    expect(statusColor('pending')).toBe('orange')
  })

  it('done 返回 green', () => {
    expect(statusColor('done')).toBe('green')
  })

  it('未知状态返回 grey', () => {
    expect(statusColor('unknown')).toBe('grey')
  })
})

describe('statusLabel', () => {
  it('pending 返回 待处理', () => {
    expect(statusLabel('pending')).toBe('待处理')
  })

  it('done 返回 已处理', () => {
    expect(statusLabel('done')).toBe('已处理')
  })

  it('未知状态原样返回', () => {
    expect(statusLabel('other')).toBe('other')
  })
})

describe('sourceLabel', () => {
  it('group 返回 群聊', () => {
    expect(sourceLabel('group')).toBe('群聊')
  })

  it('private 返回 私聊', () => {
    expect(sourceLabel('private')).toBe('私聊')
  })

  it('未知来源原样返回', () => {
    expect(sourceLabel('web')).toBe('web')
  })
})

describe('typeColor', () => {
  it('bug 返回 red', () => {
    expect(typeColor('bug')).toBe('red')
  })

  it('suggestion 返回 blue', () => {
    expect(typeColor('suggestion')).toBe('blue')
  })

  it('complaint 返回 orange', () => {
    expect(typeColor('complaint')).toBe('orange')
  })

  it('other 返回 grey', () => {
    expect(typeColor('other')).toBe('grey')
  })

  it('null 返回 grey', () => {
    expect(typeColor(null)).toBe('grey')
  })
})

describe('选项常量结构', () => {
  it('statusOptions 每项含 title 和 value', () => {
    for (const o of statusOptions) {
      expect(o).toHaveProperty('title')
      expect(o).toHaveProperty('value')
    }
  })

  it('typeOptions 包含 4 项', () => {
    expect(typeOptions).toHaveLength(4)
  })

  it('sourceOptions 包含 2 项', () => {
    expect(sourceOptions).toHaveLength(2)
  })
})
