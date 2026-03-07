/** 统计数据 API 调用（第 5 阶段的占位实现）。 */

import { get } from '@/api'

export interface StatsData {
  messageCount: { today: number; total: number }
  activeGroups: number
  activeUsers: number
}

export async function fetchStats(): Promise<StatsData> {
  const res = await get<StatsData>('/stats')
  return res.data
}

