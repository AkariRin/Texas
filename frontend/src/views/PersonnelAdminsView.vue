<template>
  <v-container fluid>
    <v-card flat>
      <v-card-title class="d-flex align-center ga-2">
        <v-icon start>mdi-shield-account</v-icon>
        <span>管理员列表</span>
        <v-spacer />
        <v-btn color="red" variant="tonal" prepend-icon="mdi-plus" @click="addDialog = true">
          添加管理员
        </v-btn>
      </v-card-title>

      <v-card-text v-if="store.adminsLoading" class="text-center pa-8">
        <v-progress-circular indeterminate color="red" />
      </v-card-text>

      <template v-else>
        <v-alert v-if="store.admins.length === 0" type="info" variant="tonal" class="ma-4">
          暂无管理员，点击右上角"添加管理员"来设置
        </v-alert>

        <v-list v-else lines="two">
          <v-list-item v-for="admin in store.admins" :key="admin.qq">
            <template #prepend>
              <v-avatar size="40">
                <v-img :src="`https://q1.qlogo.cn/g?b=qq&nk=${admin.qq}&s=40`" />
              </v-avatar>
            </template>

            <v-list-item-title class="font-weight-medium">
              {{ admin.nickname || '未知用户' }}
            </v-list-item-title>
            <v-list-item-subtitle> QQ: {{ admin.qq }} </v-list-item-subtitle>

            <template #append>
              <v-btn icon size="small" variant="text" color="error" @click="confirmRemove(admin)">
                <v-icon>mdi-shield-off</v-icon>
                <v-tooltip activator="parent" location="top">移除管理员</v-tooltip>
              </v-btn>
            </template>
          </v-list-item>
        </v-list>
      </template>

      <!-- 添加管理员对话框 -->
      <v-dialog v-model="addDialog" max-width="400">
        <v-card>
          <v-card-title>添加管理员</v-card-title>
          <v-card-text>
            <v-text-field
              v-model="addQQ"
              label="QQ 号"
              type="number"
              variant="outlined"
              hide-details="auto"
              prepend-inner-icon="mdi-identifier"
              :error-messages="addError"
            />
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn variant="text" @click="addDialog = false">取消</v-btn>
            <v-btn
              color="red"
              variant="tonal"
              :loading="addLoading"
              :disabled="!addQQ"
              @click="doAdd"
            >
              确认添加
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
            <v-btn variant="text" @click="removeDialog = false">取消</v-btn>
            <v-btn color="error" variant="tonal" :loading="removeLoading" @click="doRemove">
              确认移除
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>

      <!-- 提示 snackbar -->
      <v-snackbar v-model="snackbar" :color="snackColor" :timeout="3000" location="top">
        {{ snackText }}
      </v-snackbar>
    </v-card>
  </v-container>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { usePersonnelStore } from '@/stores/personnel'
import type { UserItem } from '@/apis/personnel'

const store = usePersonnelStore()

// 添加管理员
const addDialog = ref(false)
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

async function doAdd() {
  addError.value = ''
  const qq = Number(addQQ.value)
  if (!qq || isNaN(qq)) {
    addError.value = '请输入有效的 QQ 号'
    return
  }
  addLoading.value = true
  try {
    await store.setAdmin(qq)
    addDialog.value = false
    addQQ.value = ''
    showSnack(`已将 ${qq} 设为管理员`)
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    const msg = err?.response?.data?.detail || '操作失败'
    addError.value = msg
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
