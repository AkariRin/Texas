<template>
  <v-container fluid>
    <PageHeader icon="mdi-server-network" title="提供商" subtitle="管理 LLM 服务提供商配置">
      <v-btn color="red" prepend-icon="mdi-plus" @click="openCreate"> 添加提供商 </v-btn>
    </PageHeader>
    <v-card flat>

      <v-row v-if="store.providersLoading" class="pa-4" dense>
        <v-col v-for="n in 4" :key="n" cols="12" sm="6" md="4" lg="3">
          <v-skeleton-loader type="card" elevation="2" />
        </v-col>
      </v-row>

      <v-card-text
        v-else-if="store.providers.length === 0"
        class="text-center py-8 text-medium-emphasis"
      >
        暂无提供商，点击右上角添加
      </v-card-text>

      <v-row v-else class="pa-4" dense>
        <v-col
          v-for="provider in store.providers"
          :key="provider.id"
          cols="12"
          sm="6"
          md="4"
          lg="3"
        >
          <v-card variant="elevated" class="h-100">
            <v-card-title class="d-flex align-center">
              <span class="text-truncate">{{ provider.name }}</span>
            </v-card-title>

            <v-card-text>
              <div class="text-caption text-medium-emphasis mb-1">API 地址</div>
              <div class="text-body-2 text-truncate mb-3">{{ provider.api_base }}</div>

              <div class="text-caption text-medium-emphasis mb-1">API Key</div>
              <div class="text-body-2 mb-3 font-weight-medium">{{ provider.api_key_masked }}</div>

              <div class="d-flex ga-3 mb-3">
                <div>
                  <div class="text-caption text-medium-emphasis">最大重试</div>
                  <div class="text-body-2">{{ provider.max_retries }} 次</div>
                </div>
                <div>
                  <div class="text-caption text-medium-emphasis">超时</div>
                  <div class="text-body-2">{{ provider.timeout }} 秒</div>
                </div>
                <div>
                  <div class="text-caption text-medium-emphasis">重试间隔</div>
                  <div class="text-body-2">{{ provider.retry_interval }} 秒</div>
                </div>
              </div>

              <v-chip size="small" variant="elevated" color="blue">
                <v-icon start size="x-small">mdi-brain</v-icon>
                {{ provider.model_count }} 个模型
              </v-chip>
            </v-card-text>

            <v-card-actions>
              <v-btn size="small" variant="elevated" color="blue" @click="doTest(provider)">
                <v-icon start>mdi-connection</v-icon>
                测试
              </v-btn>
              <v-btn size="small" variant="elevated" @click="openEdit(provider)">
                <v-icon start>mdi-pencil</v-icon>
                编辑
              </v-btn>
              <v-spacer />
              <v-btn size="small" variant="elevated" color="error" @click="confirmDelete(provider)">
                <v-icon>mdi-delete</v-icon>
              </v-btn>
            </v-card-actions>
          </v-card>
        </v-col>
      </v-row>

      <!-- 创建/编辑对话框 -->
      <v-dialog :model-value="formDialog" max-width="520" @update:model-value="formDialog = $event">
        <v-card>
          <v-card-title>
            {{ isEdit ? '编辑提供商' : '添加提供商' }}
          </v-card-title>

          <v-card-text>
            <v-form ref="formRef" @submit.prevent="submitForm">
              <v-text-field
                v-model="form.name"
                label="提供商名称"
                :rules="[rules.required]"
                variant="solo-filled"
                density="compact"
                class="mb-3"
                placeholder="如 OpenAI、DeepSeek"
              />
              <v-text-field
                v-model="form.api_base"
                label="API 基础地址"
                :rules="[rules.required]"
                variant="solo-filled"
                density="compact"
                class="mb-3"
                placeholder="https://api.openai.com/v1"
              />
              <v-text-field
                v-model="form.api_key"
                :label="isEdit ? 'API Key (留空则不修改)' : 'API Key'"
                :rules="isEdit ? [] : [rules.required]"
                variant="solo-filled"
                density="compact"
                class="mb-3"
                :type="showKey ? 'text' : 'password'"
                :append-inner-icon="showKey ? 'mdi-eye-off' : 'mdi-eye'"
                @click:append-inner="showKey = !showKey"
                placeholder="sk-..."
              />
              <v-row dense class="mb-3">
                <v-col cols="4">
                  <v-text-field
                    v-model.number="form.max_retries"
                    label="最大重试"
                    type="number"
                    variant="solo-filled"
                    density="compact"
                    :rules="[rules.nonNegativeInt]"
                    suffix="次"
                    min="0"
                    max="10"
                  />
                </v-col>
                <v-col cols="4">
                  <v-text-field
                    v-model.number="form.timeout"
                    label="超时"
                    type="number"
                    variant="solo-filled"
                    density="compact"
                    :rules="[rules.positiveInt]"
                    suffix="秒"
                    min="1"
                    max="600"
                  />
                </v-col>
                <v-col cols="4">
                  <v-text-field
                    v-model.number="form.retry_interval"
                    label="重试间隔"
                    type="number"
                    variant="solo-filled"
                    density="compact"
                    :rules="[rules.nonNegativeInt]"
                    suffix="秒"
                    min="0"
                    max="60"
                  />
                </v-col>
              </v-row>
            </v-form>
          </v-card-text>

          <v-card-actions>
            <v-spacer />
            <v-btn @click="formDialog = false">取消</v-btn>
            <v-btn color="red" :loading="saving" @click="submitForm">
              {{ isEdit ? '保存' : '创建' }}
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>

      <!-- 删除确认 -->
      <v-dialog v-model="deleteDialog" max-width="400">
        <v-card>
          <v-card-title>确认删除</v-card-title>
          <v-card-text>
            确定要删除提供商 <strong>{{ deletingProvider?.name }}</strong> 吗？
            该操作将同时删除其下所有模型。
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn @click="deleteDialog = false">取消</v-btn>
            <v-btn color="error" :loading="deleteLoading" @click="doDelete">删除</v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>

      <!-- 测试结果 -->
      <v-snackbar v-model="snackbar" :color="snackbarColor" :timeout="4000" location="bottom">
        {{ snackbarText }}
      </v-snackbar>
    </v-card>
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useLLMStore } from '@/stores/llm'
import type { ProviderItem } from '@/apis/llm'
import PageHeader from '@/components/PageHeader.vue'

const store = useLLMStore()

const formDialog = ref(false)
const editingProvider = ref<ProviderItem | null>(null)

const deleteDialog = ref(false)
const deletingProvider = ref<ProviderItem | null>(null)
const deleteLoading = ref(false)

const snackbar = ref(false)
const snackbarText = ref('')
const snackbarColor = ref('success')

// ── 表单状态 ──

const isEdit = computed(() => !!editingProvider.value)
const showKey = ref(false)
const saving = ref(false)
const formRef = ref()

const form = ref({
  name: '',
  api_base: '',
  api_key: '',
  max_retries: 2,
  timeout: 60,
  retry_interval: 1,
})

const rules = {
  required: (v: string) => !!v || '此字段不能为空',
  nonNegativeInt: (v: number) => (Number.isInteger(v) && v >= 0) || '请输入非负整数',
  positiveInt: (v: number) => (Number.isInteger(v) && v >= 1) || '请输入正整数',
}

watch(formDialog, (open) => {
  if (open) {
    if (editingProvider.value) {
      form.value = {
        name: editingProvider.value.name,
        api_base: editingProvider.value.api_base,
        api_key: '',
        max_retries: editingProvider.value.max_retries,
        timeout: editingProvider.value.timeout,
        retry_interval: editingProvider.value.retry_interval,
      }
    } else {
      form.value = {
        name: '',
        api_base: '',
        api_key: '',
        max_retries: 2,
        timeout: 60,
        retry_interval: 1,
      }
    }
    showKey.value = false
  }
})

// ── 操作 ──

function openCreate() {
  editingProvider.value = null
  formDialog.value = true
}

function openEdit(provider: ProviderItem) {
  editingProvider.value = provider
  formDialog.value = true
}

function confirmDelete(provider: ProviderItem) {
  deletingProvider.value = provider
  deleteDialog.value = true
}

async function doDelete() {
  if (!deletingProvider.value) return
  deleteLoading.value = true
  try {
    await store.deleteProvider(deletingProvider.value.id)
    showSnackbar('提供商已删除', 'success')
  } catch {
    showSnackbar('删除失败', 'error')
  } finally {
    deleteLoading.value = false
    deleteDialog.value = false
  }
}

async function doTest(provider: ProviderItem) {
  showSnackbar('正在测试连通性...', 'info')
  try {
    const result = await store.testProvider(provider.id)
    if (result.success) {
      showSnackbar(`连接成功: ${result.message}`, 'success')
    } else {
      showSnackbar(`连接失败: ${result.message}`, 'error')
    }
  } catch {
    showSnackbar('测试请求失败', 'error')
  }
}

async function submitForm() {
  const result = await formRef.value?.validate()
  const valid = result?.valid
  if (!valid) return

  saving.value = true
  try {
    if (isEdit.value && editingProvider.value) {
      const payload: Record<string, unknown> = {}
      if (form.value.name !== editingProvider.value.name) payload.name = form.value.name
      if (form.value.api_base !== editingProvider.value.api_base)
        payload.api_base = form.value.api_base
      if (form.value.api_key) payload.api_key = form.value.api_key
      if (form.value.max_retries !== editingProvider.value.max_retries)
        payload.max_retries = form.value.max_retries
      if (form.value.timeout !== editingProvider.value.timeout) payload.timeout = form.value.timeout
      if (form.value.retry_interval !== editingProvider.value.retry_interval)
        payload.retry_interval = form.value.retry_interval
      await store.updateProvider(editingProvider.value.id, payload)
    } else {
      await store.createProvider({
        name: form.value.name,
        api_base: form.value.api_base,
        api_key: form.value.api_key,
        max_retries: form.value.max_retries,
        timeout: form.value.timeout,
        retry_interval: form.value.retry_interval,
      })
    }
    store.loadProviders()
    formDialog.value = false
  } finally {
    saving.value = false
  }
}

function showSnackbar(text: string, color: string) {
  snackbarText.value = text
  snackbarColor.value = color
  snackbar.value = true
}

onMounted(() => {
  store.loadProviders()
})
</script>
