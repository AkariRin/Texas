/** Bot-related type definitions. */

export interface BotInfo {
  userId: number
  nickname: string
  status: 'online' | 'offline'
}

export interface BotStatus {
  status: string
  wsConnected: boolean
  wsConnections: number
  handlersRegistered: number
  controllers: number
  uptimeSeconds: number
}

