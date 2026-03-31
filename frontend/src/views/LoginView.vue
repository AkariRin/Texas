<template>
  <v-app>
    <v-main class="login-bg d-flex align-center justify-center">
      <v-card class="login-card" elevation="8" rounded="xl">
        <!-- 标题 -->
        <v-card-title class="pt-8 pb-2 text-center">
          <v-icon icon="mdi-robot" size="40" color="primary" class="mb-2 d-block mx-auto" />
          <div class="text-h5 font-weight-bold">Texas</div>
          <div class="text-caption text-medium-emphasis mt-1">机器人管理面板</div>
        </v-card-title>

        <!-- 登录方式 Tab -->
        <v-tabs v-model="activeTab" class="px-4" color="primary" grow>
          <v-tab value="token">
            <v-icon start icon="mdi-key" />
            令牌
          </v-tab>
          <v-tab value="passkey">
            <v-icon start icon="mdi-fingerprint" />
            Passkey
          </v-tab>
          <v-tab value="totp">
            <v-icon start icon="mdi-shield-lock" />
            两步验证
          </v-tab>
        </v-tabs>

        <v-divider />

        <v-card-text class="px-6 pt-6 pb-4">
          <v-tabs-window v-model="activeTab">
            <!-- 令牌登录 -->
            <v-tabs-window-item value="token">
              <v-form ref="tokenFormRef" @submit.prevent="handleTokenLogin">
                <v-text-field
                  v-model="tokenInput"
                  label="访问令牌"
                  type="password"
                  variant="outlined"
                  prepend-inner-icon="mdi-lock-outline"
                  placeholder="请输入访问令牌"
                  :rules="[rules.required]"
                  :disabled="loading"
                  autocomplete="current-password"
                  class="mb-2"
                />
                <v-btn
                  type="submit"
                  color="primary"
                  variant="flat"
                  block
                  size="large"
                  :loading="loading"
                >
                  登录
                </v-btn>
              </v-form>
            </v-tabs-window-item>

            <!-- Passkey 登录 -->
            <v-tabs-window-item value="passkey">
              <div class="text-center py-4">
                <v-icon icon="mdi-fingerprint" size="56" color="primary" class="mb-4" />
                <p class="text-body-2 text-medium-emphasis mb-6">
                  使用已注册的 Passkey / 生物识别设备进行身份验证
                </p>
                <v-btn
                  color="primary"
                  variant="flat"
                  block
                  size="large"
                  prepend-icon="mdi-fingerprint"
                  :loading="loading"
                  @click="handlePasskeyLogin"
                >
                  使用 Passkey 登录
                </v-btn>
              </div>
            </v-tabs-window-item>

            <!-- TOTP 登录 -->
            <v-tabs-window-item value="totp">
              <v-form ref="totpFormRef" @submit.prevent="handleTOTPLogin">
                <p class="text-body-2 text-medium-emphasis mb-4">
                  请输入身份验证器 App 中显示的 6 位验证码
                </p>
                <v-otp-input
                  v-model="totpCode"
                  length="6"
                  variant="outlined"
                  :disabled="loading"
                  class="mb-4"
                  @finish="handleTOTPLogin"
                />
                <v-btn
                  type="submit"
                  color="primary"
                  variant="flat"
                  block
                  size="large"
                  :loading="loading"
                  :disabled="totpCode.length < 6"
                >
                  验证
                </v-btn>
              </v-form>
            </v-tabs-window-item>
          </v-tabs-window>
        </v-card-text>

        <!-- 错误提示 -->
        <v-slide-y-transition>
          <v-alert
            v-if="errorMsg"
            type="error"
            variant="tonal"
            class="mx-6 mb-4"
            closable
            density="compact"
            @click:close="errorMsg = ''"
          >
            {{ errorMsg }}
          </v-alert>
        </v-slide-y-transition>
      </v-card>
    </v-main>
  </v-app>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { loginWithToken, loginWithTOTP, webauthnLoginBegin, webauthnLoginFinish } from '@/apis/auth'

const router = useRouter()
const route = useRoute()

// 状态
const activeTab = ref<'token' | 'passkey' | 'totp'>('token')
const loading = ref(false)
const errorMsg = ref('')
const tokenInput = ref('')
const totpCode = ref('')

const tokenFormRef = ref()
const totpFormRef = ref()

// 表单校验规则
const rules = {
  required: (v: string) => !!v?.trim() || '此字段不能为空',
}

// 登录后跳转目标
function getRedirectTarget(): string {
  const redirect = route.query.redirect
  return typeof redirect === 'string' && redirect !== '/login' ? redirect : '/'
}

// 令牌登录
async function handleTokenLogin() {
  const form = tokenFormRef.value
  if (!form) return
  const { valid } = await form.validate()
  if (!valid) return

  loading.value = true
  errorMsg.value = ''
  try {
    await loginWithToken(tokenInput.value)
    router.push(getRedirectTarget())
  } catch (err: unknown) {
    errorMsg.value = extractError(err, '令牌错误，请检查后重试')
  } finally {
    loading.value = false
  }
}

// Passkey 登录
async function handlePasskeyLogin() {
  loading.value = true
  errorMsg.value = ''
  try {
    const { data: res } = await webauthnLoginBegin()
    const challengeId = res.data.challenge_id

    // 构造 navigator.credentials.get 参数
    const credentialRequestOptions: CredentialRequestOptions = {
      publicKey: {
        challenge: base64urlToBuffer(res.data.challenge_b64),
        rpId: res.data.rp_id,
        allowCredentials: (res.data.allow_credentials ?? []).map((c) => ({
          type: 'public-key' as const,
          id: base64urlToBuffer(c.id),
        })),
        userVerification: 'preferred',
        timeout: 60000,
      },
    }

    const credential = await navigator.credentials.get(credentialRequestOptions)
    if (!credential || credential.type !== 'public-key') {
      throw new Error('未获取到有效凭据')
    }

    const pkc = credential as PublicKeyCredential
    const response = pkc.response as AuthenticatorAssertionResponse

    await webauthnLoginFinish(challengeId, {
      id: pkc.id,
      rawId: bufferToBase64url(pkc.rawId),
      type: pkc.type,
      response: {
        clientDataJSON: bufferToBase64url(response.clientDataJSON),
        authenticatorData: bufferToBase64url(response.authenticatorData),
        signature: bufferToBase64url(response.signature),
        userHandle: response.userHandle ? bufferToBase64url(response.userHandle) : null,
      },
    })

    router.push(getRedirectTarget())
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'NotAllowedError') {
      errorMsg.value = '操作已取消或超时'
    } else {
      errorMsg.value = extractError(err, 'Passkey 验证失败，请重试')
    }
  } finally {
    loading.value = false
  }
}

// TOTP 登录
async function handleTOTPLogin() {
  if (totpCode.value.length < 6) return
  loading.value = true
  errorMsg.value = ''
  try {
    await loginWithTOTP(totpCode.value)
    router.push(getRedirectTarget())
  } catch (err: unknown) {
    errorMsg.value = extractError(err, '验证码错误，请重试')
    totpCode.value = ''
  } finally {
    loading.value = false
  }
}

// 工具函数
function extractError(err: unknown, fallback: string): string {
  if (err && typeof err === 'object' && 'response' in err) {
    const resp = (err as { response?: { data?: { message?: string } } }).response
    return resp?.data?.message ?? fallback
  }
  return fallback
}

function base64urlToBuffer(base64url: string): ArrayBuffer {
  const base64 = base64url.replace(/-/g, '+').replace(/_/g, '/')
  const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '=')
  const binary = atob(padded)
  const buffer = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) {
    buffer[i] = binary.charCodeAt(i)
  }
  return buffer.buffer
}

function bufferToBase64url(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]!)
  }
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '')
}
</script>

<style scoped>
.login-bg {
  min-height: 100vh;
  background: linear-gradient(135deg, rgb(var(--v-theme-primary), 0.08) 0%, transparent 60%);
}

.login-card {
  width: 100%;
  max-width: 420px;
}
</style>
