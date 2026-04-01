/**
 * 反馈模块显示工具函数与选项常量。
 */

export const statusOptions = [
  { title: '待处理', value: 'pending' },
  { title: '已处理', value: 'done' },
]

export const typeOptions = [
  { title: 'Bug', value: 'bug' },
  { title: '建议', value: 'suggestion' },
  { title: '投诉', value: 'complaint' },
  { title: '其他', value: 'other' },
]

export const sourceOptions = [
  { title: '群聊', value: 'group' },
  { title: '私聊', value: 'private' },
]

export function statusColor(status: string): string {
  const map: Record<string, string> = {
    pending: 'orange',
    done: 'green',
  }
  return map[status] ?? 'grey'
}

export function statusLabel(status: string): string {
  const map: Record<string, string> = {
    pending: '待处理',
    done: '已处理',
  }
  return map[status] ?? status
}

export function sourceLabel(source: string): string {
  const map: Record<string, string> = {
    group: '群聊',
    private: '私聊',
  }
  return map[source] ?? source
}

export function typeColor(type: string | null): string {
  const map: Record<string, string> = {
    bug: 'red',
    suggestion: 'blue',
    complaint: 'orange',
    other: 'grey',
  }
  return map[type ?? 'other'] ?? 'grey'
}
