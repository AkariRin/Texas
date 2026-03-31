<template>
  <v-container class="py-6" max-width="720">
    <div class="text-h5 font-weight-bold mb-1">安全设置</div>
    <div class="text-body-2 text-medium-emphasis mb-6">管理登录方式与会话安全</div>

    <!-- Session 信息 -->
    <v-card class="mb-6" variant="outlined">
      <v-card-title class="d-flex align-center ga-2 py-4">
        <v-icon icon="mdi-account-circle" color="primary" />
        当前会话
      </v-card-title>
      <v-divider />
      <v-card-text>
        <v-skeleton-loader v-if="sessionLoading" type="list-item-two-line" />
        <v-list v-else-if="sessionInfo" lines="two" density="compact" class="pa-0">
          <v-list-item>
            <template #prepend>
              <v-icon icon="mdi-login-variant" class="mr-3" />
            </template>
            <v-list-item-title>登录方式</v-list-item-title>
            <v-list-item-subtitle>{{
              authMethodLabel(sessionInfo.auth_method)
            }}</v-list-item-subtitle>
          </v-list-item>
          <v-list-item>
            <template #prepend>
              <v-icon icon="mdi-clock-outline" class="mr-3" />
            </template>
            <v-list-item-title>创建时间</v-list-item-title>
            <v-list-item-subtitle>{{ formatDate(sessionInfo.created_at) }}</v-list-item-subtitle>
          </v-list-item>
          <v-list-item>
            <template #prepend>
              <v-icon icon="mdi-clock-end" class="mr-3" />
            </template>
            <v-list-item-title>过期时间</v-list-item-title>
            <v-list-item-subtitle>{{ formatDate(sessionInfo.expires_at) }}</v-list-item-subtitle>
          </v-list-item>
        </v-list>
      </v-card-text>
      <v-card-actions class="px-4 pb-4">
        <v-btn
          color="error"
          variant="tonal"
          prepend-icon="mdi-logout"
          :loading="logoutLoading"
          @click="handleLogout"
        >
          退出登录
        </v-btn>
      </v-card-actions>
    </v-card>

    <!-- Passkey 管理 -->
    <v-card class="mb-6" variant="outlined">
      <v-card-title class="d-flex align-center justify-space-between py-4">
        <div class="d-flex align-center ga-2">
          <v-icon icon="mdi-fingerprint" color="primary" />
          Passkey 管理
        </div>
        <v-btn
          color="primary"
          variant="tonal"
          size="small"
          prepend-icon="mdi-plus"
          :loading="passkeyAdding"
          @click="handleRegisterPasskey"
        >
          添加 Passkey
        </v-btn>
      </v-card-title>
      <v-divider />
      <v-card-text class="pa-0">
        <v-skeleton-loader v-if="passkeyLoading" type="list-item-avatar@2" />
        <template v-else-if="passkeys.length > 0">
          <v-list lines="two">
            <v-list-item
              v-for="pk in passkeys"
              :key="pk.credential_id_b64"
              :subtitle="
                '添加于 ' +
                formatDate(pk.created_at) +
                '  |  最近使用 ' +
                formatDate(pk.last_used_at)
              "
            >
              <template #prepend>
                <v-avatar color="primary" variant="tonal">
                  <v-icon icon="mdi-key" />
                </v-avatar>
              </template>
              <template #title>
                {{ pk.device_name || '未命名设备' }}
              </template>
              <template #append>
                <v-btn
                  icon="mdi-delete-outline"
                  variant="text"
                  color="error"
                  size="small"
                  @click="confirmDeletePasskey(pk)"
                />
              </template>
            </v-list-item>
          </v-list>
        </template>
        <div v-else class="text-center py-8 text-medium-emphasis">
          <v-icon icon="mdi-fingerprint-off" size="40" class="mb-2" />
          <p class="text-body-2">尚未注册任何 Passkey</p>
        </div>
      </v-card-text>
    </v-card>

    <!-- 注册 Passkey 设备名对话框 -->
    <v-dialog v-model="deviceNameDialog" max-width="380" persistent>
      <v-card rounded="xl">
        <v-card-title class="pt-5 pb-2">命名此设备</v-card-title>
        <v-card-text>
          <v-text-field
            v-model="newDeviceName"
            label="设备名称"
            variant="outlined"
            placeholder="例如：MacBook Pro"
            autofocus
            :rules="[rules.required]"
            @keyup.enter="confirmAddPasskey"
          />
        </v-card-text>
        <v-card-actions class="px-4 pb-4">
          <v-spacer />
          <v-btn variant="text" @click="deviceNameDialog = false">取消</v-btn>
          <v-btn
            color="primary"
            variant="flat"
            :loading="passkeyAdding"
            :disabled="!newDeviceName.trim()"
            @click="confirmAddPasskey"
          >
            继续注册
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- TOTP 管理 -->
    <v-card variant="outlined">
      <v-card-title class="d-flex align-center ga-2 py-4">
        <v-icon icon="mdi-shield-lock" color="primary" />
        两步验证 (TOTP)
      </v-card-title>
      <v-divider />
      <v-card-text>
        <p class="text-body-2 text-medium-emphasis mb-4">
          绑定 Authenticator App（如 Google Authenticator）后，可使用 6 位验证码登录。
        </p>

        <!-- TOTP 设置流程 -->
        <v-stepper v-model="totpStep" flat>
          <v-stepper-header>
            <v-stepper-item value="1" title="生成二维码" />
            <v-divider />
            <v-stepper-item value="2" title="扫码绑定" />
            <v-divider />
            <v-stepper-item value="3" title="验证完成" />
          </v-stepper-header>

          <v-stepper-window>
            <!-- Step 1：开始 -->
            <v-stepper-window-item value="1">
              <div class="text-center py-4">
                <v-btn
                  color="primary"
                  variant="flat"
                  prepend-icon="mdi-qrcode"
                  :loading="totpLoading"
                  @click="loadTOTPSetup"
                >
                  生成绑定二维码
                </v-btn>
              </div>
            </v-stepper-window-item>

            <!-- Step 2：扫码 -->
            <v-stepper-window-item value="2">
              <div class="text-center py-2">
                <p class="text-body-2 text-medium-emphasis mb-4">
                  使用 Authenticator App 扫描下方二维码
                </p>
                <canvas ref="qrcodeCanvas" class="mx-auto mb-4 d-block rounded-lg" />
                <p class="text-caption text-medium-emphasis mb-4">
                  无法扫码？手动输入密钥：<code>{{ totpSecret }}</code>
                </p>
                <v-form ref="totpConfirmFormRef" @submit.prevent="handleTOTPConfirm">
                  <v-otp-input
                    v-model="totpConfirmCode"
                    length="6"
                    variant="outlined"
                    :disabled="totpLoading"
                    class="mb-4"
                  />
                  <div class="d-flex ga-2 justify-center">
                    <v-btn variant="text" @click="totpStep = '1'">返回</v-btn>
                    <v-btn
                      type="submit"
                      color="primary"
                      variant="flat"
                      :loading="totpLoading"
                      :disabled="totpConfirmCode.length < 6"
                    >
                      确认绑定
                    </v-btn>
                  </div>
                </v-form>
              </div>
            </v-stepper-window-item>

            <!-- Step 3：成功 -->
            <v-stepper-window-item value="3">
              <div class="text-center py-6">
                <v-icon icon="mdi-check-circle" color="success" size="56" class="mb-3" />
                <p class="text-body-1 font-weight-medium mb-1">绑定成功</p>
                <p class="text-body-2 text-medium-emphasis mb-4">
                  下次登录可使用 Authenticator App 生成的验证码
                </p>
                <v-btn variant="tonal" @click="totpStep = '1'">重新绑定</v-btn>
              </div>
            </v-stepper-window-item>
          </v-stepper-window>
        </v-stepper>
      </v-card-text>
    </v-card>

    <!-- 删除 Passkey 确认对话框 -->
    <v-dialog v-model="deleteDialog" max-width="380">
      <v-card rounded="xl">
        <v-card-title class="pt-5">删除 Passkey</v-card-title>
        <v-card-text>
          确定要删除 <strong>{{ deletingPasskey?.device_name || '此设备' }}</strong> 的 Passkey
          吗？此操作不可撤销。
        </v-card-text>
        <v-card-actions class="px-4 pb-4">
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog = false">取消</v-btn>
          <v-btn
            color="error"
            variant="flat"
            :loading="deletingLoading"
            @click="executeDeletePasskey"
          >
            删除
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 全局消息 snackbar -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color" timeout="3000" location="top">
      {{ snackbar.text }}
    </v-snackbar>
  </v-container>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import QRCode from 'qrcode'
import {
  getSession,
  logout,
  getWebAuthnCredentials,
  deleteWebAuthnCredential,
  webauthnRegisterBegin,
  webauthnRegisterFinish,
  getTOTPSetup,
  confirmTOTPSetup,
} from '@/apis/auth'
import type { SessionInfo, WebAuthnCredentialInfo } from '@/apis/auth'

const router = useRouter()

// ─────────────── Session ───────────────
const sessionInfo = ref<SessionInfo | null>(null)
const sessionLoading = ref(true)
const logoutLoading = ref(false)

async function loadSession() {
  sessionLoading.value = true
  try {
    const { data: res } = await getSession()
    sessionInfo.value = res.data
  } finally {
    sessionLoading.value = false
  }
}

async function handleLogout() {
  logoutLoading.value = true
  try {
    await logout()
    router.push('/login')
  } finally {
    logoutLoading.value = false
  }
}

function authMethodLabel(method: string): string {
  const map: Record<string, string> = {
    token: '静态令牌',
    webauthn: 'Passkey / 生物识别',
    totp: '两步验证 (TOTP)',
  }
  return map[method] ?? method
}

// ─────────────── Passkey ───────────────
const passkeys = ref<WebAuthnCredentialInfo[]>([])
const passkeyLoading = ref(true)
const passkeyAdding = ref(false)
const deviceNameDialog = ref(false)
const newDeviceName = ref('')
let pendingChallengeId = ''
let pendingCredential: object | null = null

async function loadPasskeys() {
  passkeyLoading.value = true
  try {
    const { data: res } = await getWebAuthnCredentials()
    passkeys.value = res.data
  } finally {
    passkeyLoading.value = false
  }
}

async function handleRegisterPasskey() {
  passkeyAdding.value = true
  try {
    const { data: res } = await webauthnRegisterBegin()
    const challengeId = res.data.challenge_id

    const user = res.data.user ?? { id: '', name: 'admin', displayName: 'Admin' }
    const options: CredentialCreationOptions = {
      publicKey: {
        challenge: base64urlToBuffer(res.data.challenge_b64),
        rp: { id: res.data.rp_id, name: res.data.rp_name ?? 'Texas' },
        user: {
          id: base64urlToBuffer(user.id || btoa('admin')),
          name: user.name,
          displayName: user.displayName,
        },
        pubKeyCredParams: [
          { alg: -7, type: 'public-key' },
          { alg: -257, type: 'public-key' },
        ],
        authenticatorSelection: {
          userVerification: 'preferred',
          residentKey: 'preferred',
        },
        timeout: 60000,
      },
    }

    const credential = await navigator.credentials.create(options)
    if (!credential || credential.type !== 'public-key') {
      throw new Error('未获取到有效凭据')
    }

    const pkc = credential as PublicKeyCredential
    const response = pkc.response as AuthenticatorAttestationResponse

    pendingChallengeId = challengeId
    pendingCredential = {
      id: pkc.id,
      rawId: bufferToBase64url(pkc.rawId),
      type: pkc.type,
      response: {
        clientDataJSON: bufferToBase64url(response.clientDataJSON),
        attestationObject: bufferToBase64url(response.attestationObject),
      },
    }

    newDeviceName.value = ''
    deviceNameDialog.value = true
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'NotAllowedError') {
      showSnackbar('操作已取消', 'warning')
    } else {
      showSnackbar('Passkey 注册失败，请重试', 'error')
    }
  } finally {
    passkeyAdding.value = false
  }
}

async function confirmAddPasskey() {
  if (!newDeviceName.value.trim() || !pendingCredential) return
  passkeyAdding.value = true
  try {
    await webauthnRegisterFinish(pendingChallengeId, pendingCredential, newDeviceName.value.trim())
    deviceNameDialog.value = false
    showSnackbar('Passkey 注册成功', 'success')
    await loadPasskeys()
  } catch {
    showSnackbar('注册失败，请重试', 'error')
  } finally {
    passkeyAdding.value = false
    pendingCredential = null
  }
}

// 删除 Passkey
const deleteDialog = ref(false)
const deletingPasskey = ref<WebAuthnCredentialInfo | null>(null)
const deletingLoading = ref(false)

function confirmDeletePasskey(pk: WebAuthnCredentialInfo) {
  deletingPasskey.value = pk
  deleteDialog.value = true
}

async function executeDeletePasskey() {
  if (!deletingPasskey.value) return
  deletingLoading.value = true
  try {
    await deleteWebAuthnCredential(deletingPasskey.value.credential_id_b64)
    deleteDialog.value = false
    showSnackbar('已删除 Passkey', 'success')
    await loadPasskeys()
  } catch {
    showSnackbar('删除失败，请重试', 'error')
  } finally {
    deletingLoading.value = false
  }
}

// ─────────────── TOTP ───────────────
const totpStep = ref('1')
const totpLoading = ref(false)
const totpSecret = ref('')
const totpConfirmCode = ref('')
const qrcodeCanvas = ref<HTMLCanvasElement | null>(null)
const totpConfirmFormRef = ref()

async function loadTOTPSetup() {
  totpLoading.value = true
  try {
    const { data: res } = await getTOTPSetup()
    totpSecret.value = res.data.secret
    totpStep.value = '2'
    await nextTick()
    if (qrcodeCanvas.value) {
      await QRCode.toCanvas(qrcodeCanvas.value, res.data.otpauth_uri, { width: 200 })
    }
  } catch {
    showSnackbar('获取 TOTP 设置失败', 'error')
  } finally {
    totpLoading.value = false
  }
}

async function handleTOTPConfirm() {
  if (totpConfirmCode.value.length < 6) return
  totpLoading.value = true
  try {
    await confirmTOTPSetup(totpConfirmCode.value)
    totpStep.value = '3'
    showSnackbar('TOTP 绑定成功', 'success')
  } catch {
    showSnackbar('验证码错误，请重试', 'error')
    totpConfirmCode.value = ''
  } finally {
    totpLoading.value = false
  }
}

// ─────────────── 工具 ───────────────
const rules = {
  required: (v: string) => !!v?.trim() || '此字段不能为空',
}

const snackbar = ref({ show: false, text: '', color: 'success' })

function showSnackbar(text: string, color: string) {
  snackbar.value = { show: true, text, color }
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
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

// ─────────────── 初始化 ───────────────
onMounted(() => {
  loadSession()
  loadPasskeys()
})
</script>
