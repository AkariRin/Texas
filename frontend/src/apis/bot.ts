import http from '@/apis/client'

export interface BotInfo {
  nickname: string | null
  user_id: number | null
  avatar_url: string | null
}

export interface BotVersionInfo {
  app_name: string
  app_version: string
  protocol_version: string
}

export interface OnlineClient {
  app_id: number
  app_name: string
  device_name: string
  device_kind: string
}

export interface BotProfile {
  nickname: string | null
  user_id: number | null
  avatar_url: string | null
  online: boolean
  version: BotVersionInfo
  online_clients: OnlineClient[]
}

export interface BotProfileUpdate {
  nickname?: string
  personal_note?: string
}

export function getBotInfo() {
  return http.get<{ code: number; data: BotInfo }>('/api/bot/info')
}

export function getBotProfile() {
  return http.get<{ code: number; data: BotProfile }>('/api/bot/profile')
}

export function updateBotProfile(data: BotProfileUpdate) {
  return http.put<{ code: number; data: Record<string, never> }>('/api/bot/profile', data)
}
