/** Bot 状态 API 调用。 */

import type { BotStatus } from '@/types/bot'
import { get } from '@/api'

export async function fetchBotStatus(): Promise<BotStatus> {
  const res = await get<BotStatus>('/status')
  return res.data
}

