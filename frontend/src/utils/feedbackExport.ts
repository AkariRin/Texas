/**
 * 用户反馈导出工具 —— 支持完整模式和仅需求模式的 Markdown 导出。
 */

import type { Feedback } from '@/apis/feedback'

export type ExportMode = 'full' | 'requirements-only'

/**
 * 主导出函数，根据模式调用对应生成函数
 */
export function exportToMarkdown(feedbacks: Feedback[], mode: ExportMode): void {
  const content =
    mode === 'full' ? generateFullMarkdown(feedbacks) : generateRequirementsOnlyMarkdown(feedbacks)

  const timestamp = new Date().toISOString().slice(0, 10)
  const filename = `feedback-export-${mode}-${timestamp}.md`

  downloadMarkdown(content, filename)
}

/**
 * 生成完整模式 Markdown
 */
export function generateFullMarkdown(feedbacks: Feedback[]): string {
  const lines: string[] = [
    '# 用户反馈导出（完整模式）',
    '',
    `导出时间：${new Date().toLocaleString('zh-CN')}`,
    `总计：${feedbacks.length} 条`,
    '',
    '---',
    '',
  ]

  feedbacks.forEach((fb, index) => {
    lines.push(`## ${index + 1}. 反馈 #${fb.id}`, '')
    lines.push(`- **提交者 ID**: ${fb.user_id}`)
    lines.push(`- **类型**: ${fb.feedback_type || '未分类'}`)
    lines.push(`- **来源**: ${fb.source}`)
    lines.push(`- **状态**: ${fb.status}`)
    lines.push(`- **提交时间**: ${fb.created_at}`)
    if (fb.processed_at) {
      lines.push(`- **处理时间**: ${fb.processed_at}`)
    }
    lines.push('', '**内容**:', '', fb.content, '')
    if (fb.admin_reply) {
      lines.push('**管理员回复**:', '', fb.admin_reply, '')
    }
    lines.push('---', '')
  })

  return lines.join('\n')
}

/**
 * 生成仅需求模式 Markdown（按类型分组）
 */
export function generateRequirementsOnlyMarkdown(feedbacks: Feedback[]): string {
  const lines: string[] = [
    '# 用户反馈导出（仅需求模式）',
    '',
    `导出时间：${new Date().toLocaleString('zh-CN')}`,
    `总计：${feedbacks.length} 条`,
    '',
    '---',
    '',
  ]

  const grouped = groupByType(feedbacks)
  const typeOrder = ['Bug', '建议', '投诉', '其他']

  typeOrder.forEach((type) => {
    const items = grouped[type]
    if (!items || items.length === 0) return

    lines.push(`## ${type}`, '')
    items.forEach((fb, index) => {
      lines.push(`${index + 1}. ${fb.content}`, '')
    })
    lines.push('---', '')
  })

  return lines.join('\n')
}

/**
 * 按类型分组反馈
 */
function groupByType(feedbacks: Feedback[]): Record<string, Feedback[]> {
  const groups: Record<string, Feedback[]> = {
    Bug: [],
    建议: [],
    投诉: [],
    其他: [],
  }

  feedbacks.forEach((fb) => {
    const type = fb.feedback_type || '其他'
    if (type in groups) {
      groups[type]?.push(fb)
    } else {
      groups['其他']?.push(fb)
    }
  })

  return groups
}

/**
 * 触发浏览器下载 Markdown 文件
 */
export function downloadMarkdown(content: string, filename: string): void {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
