<template>
  <PageLayout>
    <template #actions>
      <v-btn color="red" prepend-icon="mdi-plus" @click="openCreate"> 添加提供商 </v-btn>
    </template>
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

      <!-- 测试 / 操作结果 -->
      <v-snackbar v-model="snackbar" :color="snackbarColor" :timeout="4000" location="bottom">
        {{ snackbarText }}
      </v-snackbar>
    </v-card>

    <ProviderFormDialog
      v-model="formDialog"
      :provider="editingProvider"
      @saved="store.loadProviders()"
      @error="(msg) => showSnackbar(msg, 'error')"
    />
  </PageLayout>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useLLMStore } from '@/stores/llm'
import type { ProviderItem } from '@/apis/llm'
import PageLayout from '@/components/PageLayout.vue'
import ProviderFormDialog from './ProviderFormDialog.vue'

const store = useLLMStore()

const formDialog = ref(false)
const editingProvider = ref<ProviderItem | null>(null)

const deleteDialog = ref(false)
const deletingProvider = ref<ProviderItem | null>(null)
const deleteLoading = ref(false)

const snackbar = ref(false)
const snackbarText = ref('')
const snackbarColor = ref('success')

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

function showSnackbar(text: string, color: string) {
  snackbarText.value = text
  snackbarColor.value = color
  snackbar.value = true
}

onMounted(() => {
  store.loadProviders()
})
</script>
