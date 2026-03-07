/** 处理器管理 API 调用。 */

import type { ControllerInfo } from '@/types/handler'
import { get } from '@/api'

export async function fetchHandlers(): Promise<ControllerInfo[]> {
  const res = await get<{ controllers: ControllerInfo[] }>('/handlers')
  return res.data.controllers
}

