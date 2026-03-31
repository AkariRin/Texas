/**
 * 鉴权相关 API 封装
 */

import http from './client'

export interface SessionInfo {
  auth_method: string
  created_at: string
  expires_at: string
}

export interface WebAuthnBeginData {
  challenge_id: string
  challenge_b64: string
  rp_id: string
  allow_credentials?: Array<{ type: string; id: string }>
  rp_name?: string
  user?: { id: string; name: string; displayName: string }
  authenticator_selection?: Record<string, string>
}

export interface WebAuthnCredentialInfo {
  credential_id_b64: string
  device_name: string
  created_at: string
  last_used_at: string
}

export interface TOTPSetupData {
  otpauth_uri: string
  secret: string
}

/** 静态令牌登录 */
export function loginWithToken(token: string) {
  return http.post<{ code: number; data: null; message: string }>('/api/auth/login', { token })
}

/** TOTP 登录 */
export function loginWithTOTP(code: string) {
  return http.post<{ code: number; data: null; message: string }>('/api/auth/totp/verify', { code })
}

/** 登出 */
export function logout() {
  return http.post('/api/auth/logout')
}

/** 获取当前 Session 信息 */
export function getSession() {
  return http.get<{ code: number; data: SessionInfo }>('/api/auth/session')
}

/** WebAuthn 登录 begin */
export function webauthnLoginBegin() {
  return http.get<{ code: number; data: WebAuthnBeginData }>('/api/auth/webauthn/login/begin')
}

/** WebAuthn 登录 finish */
export function webauthnLoginFinish(challengeId: string, credential: object) {
  return http.post('/api/auth/webauthn/login/finish', {
    challenge_id: challengeId,
    credential,
  })
}

/** WebAuthn 注册 begin */
export function webauthnRegisterBegin() {
  return http.get<{ code: number; data: WebAuthnBeginData }>('/api/auth/webauthn/register/begin')
}

/** WebAuthn 注册 finish */
export function webauthnRegisterFinish(
  challengeId: string,
  credential: object,
  deviceName: string,
) {
  return http.post('/api/auth/webauthn/register/finish', {
    challenge_id: challengeId,
    credential,
    device_name: deviceName,
  })
}

/** 获取 Passkey 列表 */
export function getWebAuthnCredentials() {
  return http.get<{ code: number; data: WebAuthnCredentialInfo[] }>(
    '/api/auth/webauthn/credentials',
  )
}

/** 删除 Passkey */
export function deleteWebAuthnCredential(credentialIdB64: string) {
  return http.delete(`/api/auth/webauthn/${encodeURIComponent(credentialIdB64)}`)
}

/** 获取 TOTP 设置 URI */
export function getTOTPSetup() {
  return http.get<{ code: number; data: TOTPSetupData }>('/api/auth/totp/setup')
}

/** 确认 TOTP 绑定 */
export function confirmTOTPSetup(code: string) {
  return http.post('/api/auth/totp/setup', { code })
}
