<template>
  <v-container fluid>
    <PageHeader icon="mdi-shield-account" title="管理员" subtitle="管理机器人管理员权限">
      <v-btn color="red" variant="elevated" prepend-icon="mdi-plus" @click="addDialog = true">
        添加管理员
      </v-btn>
    </PageHeader>
    <v-card flat>

      <div v-if="store.adminsLoading" class="d-flex flex-wrap ga-4 pa-4">
        <v-skeleton-loader
          v-for="n in 4"
          :key="n"
          type="list-item-avatar"
          width="280"
          elevation="3"
          rounded="lg"
        />
      </div>

      <template v-else>
        <div v-if="store.admins.length === 0" class="d-flex flex-column align-center justify-center py-16 text-medium-emphasis">
          <v-icon icon="mdi-shield-off-outline" size="48" class="mb-4" />
          <div class="text-body-1">暂无管理员</div>
          <div class="text-body-2 mt-1">点击右上角「添加管理员」来设置</div>
        </div>

        <div v-else class="d-flex flex-wrap ga-4 pa-4">
          <v-card
            v-for="admin in store.admins"
            :key="admin.qq"
            elevation="3"
            rounded="lg"
            width="280"
            class="admin-card"
          >
            <div class="d-flex align-center pa-4">
              <v-avatar size="48" class="mr-4">
                <v-img :src="`https://q1.qlogo.cn/g?b=qq&nk=${admin.qq}&s=100`" />
              </v-avatar>
              <div class="flex-grow-1 overflow-hidden">
                <div class="text-subtitle-1 font-weight-bold text-truncate">
                  {{ admin.nickname || '未知用户' }}
                </div>
                <div class="text-caption text-medium-emphasis">{{ admin.qq }}</div>
              </div>
              <v-btn
                icon
                size="small"
                variant="elevated"
                color="error"
                @click="confirmRemove(admin)"
              >
                <v-icon>mdi-shield-off</v-icon>
                <v-tooltip activator="parent" location="top">移除管理员</v-tooltip>
              </v-btn>
            </div>
          </v-card>
        </div>
      </template>

      <!-- 添加管理员对话框 -->
      <v-dialog v-model="addDialog" max-width="400">
        <v-card>
          <v-card-title>添加管理员</v-card-title>
          <v-card-text>
            <v-text-field
              v-model="addQQ"
              label="QQ 号"
              variant="solo-filled"
              hide-details="auto"
              prepend-inner-icon="mdi-identifier"
              :error-messages="addError"
              @input="sanitizeDigits"
            />
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn variant="elevated" @click="addDialog = false">取消</v-btn>
            <v-btn color="red" variant="elevated" :disabled="!addQQ" @click="confirmAdd">
              确认添加
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>

      <!-- 添加管理员二次确认对话框 -->
      <v-dialog v-model="addConfirmDialog" max-width="400">
        <v-card>
          <v-card-title>二次确认</v-card-title>
          <v-card-text>
            确定要将 <strong>{{ addQQ }}</strong> 设为管理员吗？该用户将获得管理员权限。
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn variant="elevated" @click="addConfirmDialog = false">取消</v-btn>
            <v-btn color="red" variant="elevated" :loading="addLoading" @click="doAdd">
              确认
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>

      <!-- 移除确认对话框 -->
      <v-dialog v-model="removeDialog" max-width="400">
        <v-card>
          <v-card-title>确认移除管理员</v-card-title>
          <v-card-text>
            确定要移除
            <strong>{{ removeTarget?.nickname || removeTarget?.qq }}</strong> 的管理员权限吗？
            移除后，系统将根据其当前状态自动降级为好友、群友或陌生人。
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn variant="elevated" @click="removeDialog = false">取消</v-btn>
            <v-btn color="error" variant="elevated" :loading="removeLoading" @click="doRemove">
              确认移除
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>

      <!-- 提示 snackbar -->
      <v-snackbar v-model="snackbar" :color="snackColor" :timeout="3000" location="bottom">
        {{ snackText }}
      </v-snackbar>
    </v-card>
  </v-container>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { usePersonnelStore } from '@/stores/personnel'
import type { UserItem } from '@/apis/personnel'
import PageHeader from '@/components/PageHeader.vue'

const store = usePersonnelStore()

// 添加管理员
const addDialog = ref(false)
const addConfirmDialog = ref(false)
const addQQ = ref<string>('')
const addLoading = ref(false)
const addError = ref('')

// 移除管理员
const removeDialog = ref(false)
const removeTarget = ref<UserItem | null>(null)
const removeLoading = ref(false)

// 提示
const snackbar = ref(false)
const snackText = ref('')
const snackColor = ref('success')

function showSnack(text: string, color = 'success') {
  snackText.value = text
  snackColor.value = color
  snackbar.value = true
}

function sanitizeDigits() {
  addQQ.value = addQQ.value.replace(/\D/g, '')
}

function confirmAdd() {
  addError.value = ''
  const raw = addQQ.value.trim()
  if (!raw) {
    addError.value = '请输入 QQ 号'
    return
  }
  if (!/^\d+$/.test(raw)) {
    addError.value = '请输入纯数字的 QQ 号'
    return
  }
  const qq = Number(raw)
  if (!qq || !Number.isSafeInteger(qq)) {
    addError.value = '请输入有效的 QQ 号'
    return
  }
  addConfirmDialog.value = true
}

async function doAdd() {
  addError.value = ''
  const qq = Number(addQQ.value.trim())
  addLoading.value = true
  try {
    await store.setAdmin(qq)
    addConfirmDialog.value = false
    addDialog.value = false
    addQQ.value = ''
    showSnack(`已将 ${qq} 设为管理员`)
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    const msg = err?.response?.data?.detail || '操作失败'
    addError.value = msg
    addConfirmDialog.value = false
    showSnack(msg, 'error')
  } finally {
    addLoading.value = false
  }
}

function confirmRemove(admin: UserItem) {
  removeTarget.value = admin
  removeDialog.value = true
}

async function doRemove() {
  if (!removeTarget.value) return
  removeLoading.value = true
  try {
    await store.unsetAdmin(removeTarget.value.qq)
    removeDialog.value = false
    showSnack(`已移除 ${removeTarget.value.nickname || removeTarget.value.qq} 的管理员权限`)
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    const msg = err?.response?.data?.detail || '操作失败'
    showSnack(msg, 'error')
  } finally {
    removeLoading.value = false
  }
}

onMounted(() => store.loadAdmins())
</script>
