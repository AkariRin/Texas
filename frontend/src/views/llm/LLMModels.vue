<template>
  <v-container fluid>
    <v-card flat>
      <v-card-title class="d-flex align-center flex-wrap ga-2">
        <v-icon start>mdi-brain</v-icon>
        <span>LLM 模型</span>
        <v-spacer />
        <v-select
          v-model="filterProvider"
          :items="providerOptions"
          label="提供商筛选"
          density="compact"
          variant="outlined"
          hide-details
          clearable
          style="max-width: 200px"
          @update:model-value="loadPage"
        />
        <v-btn color="red" prepend-icon="mdi-plus" @click="openCreate">
          添加模型
        </v-btn>
      </v-card-title>

      <v-data-table
        :headers="headers"
        :items="store.models"
        :loading="store.modelsLoading"
        hover
      >
        <!-- 模型名称列 -->
        <template #[`item.model_name`]="{ item }">
          <div>
            <span class="font-weight-medium">{{ item.model_name }}</span>
            <div v-if="item.display_name" class="text-caption text-medium-emphasis">
              {{ item.display_name }}
            </div>
          </div>
        </template>

        <!-- 价格列 -->
        <template #[`item.price`]="{ item }">
          <div class="text-caption">
            <div>入: ${{ item.input_price.toFixed(2) }}/M</div>
            <div>出: ${{ item.output_price.toFixed(2) }}/M</div>
          </div>
        </template>

        <!-- 温度列 -->
        <template #[`item.temperature`]="{ item }">
          <v-chip size="small" variant="tonal">{{ item.temperature.toFixed(1) }}</v-chip>
        </template>

        <!-- 流式列 -->
        <template #[`item.force_stream`]="{ item }">
          <v-icon :color="item.force_stream ? 'success' : 'grey'" size="small">
            {{ item.force_stream ? 'mdi-check-circle' : 'mdi-close-circle' }}
          </v-icon>
        </template>

        <!-- 启用状态 -->
        <template #[`item.is_enabled`]="{ item }">
          <v-chip
            :color="item.is_enabled ? 'success' : 'grey'"
            size="x-small"
            variant="tonal"
          >
            {{ item.is_enabled ? '启用' : '禁用' }}
          </v-chip>
        </template>

        <!-- 操作列 -->
        <template #[`item.actions`]="{ item }">
          <v-btn icon size="small" variant="text" @click="openEdit(item)">
            <v-icon>mdi-pencil</v-icon>
            <v-tooltip activator="parent" location="top">编辑</v-tooltip>
          </v-btn>
          <v-btn icon size="small" variant="text" color="error" @click="confirmDelete(item)">
            <v-icon>mdi-delete</v-icon>
            <v-tooltip activator="parent" location="top">删除</v-tooltip>
          </v-btn>
        </template>
      </v-data-table>

      <!-- 创建/编辑对话框 -->
      <model-form
        v-model="formDialog"
        :model-item="editingModel"
        :providers="store.providers"
        @saved="onSaved"
      />

      <!-- 删除确认 -->
      <v-dialog v-model="deleteDialog" max-width="400">
        <v-card>
          <v-card-title>确认删除</v-card-title>
          <v-card-text>
            确定要删除模型 <strong>{{ deletingModel?.model_name }}</strong> 吗？
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn @click="deleteDialog = false">取消</v-btn>
            <v-btn color="error" :loading="deleteLoading" @click="doDelete">删除</v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>
    </v-card>
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useLLMStore } from '@/stores/llm'
import type { ModelItem } from '@/services/llm'
import ModelForm from './ModelForm.vue'

const store = useLLMStore()

const filterProvider = ref<string | null>(null)
const formDialog = ref(false)
const editingModel = ref<ModelItem | null>(null)
const deleteDialog = ref(false)
const deletingModel = ref<ModelItem | null>(null)
const deleteLoading = ref(false)

const providerOptions = computed(() =>
  store.providers.map((p) => ({ title: p.name, value: p.id })),
)

const headers = [
  { title: '模型名称', key: 'model_name', sortable: false },
  { title: '提供商', key: 'provider_name', sortable: false },
  { title: '价格 (USD/M tokens)', key: 'price', sortable: false },
  { title: '温度', key: 'temperature', sortable: false },
  { title: '最大 Token', key: 'max_tokens', sortable: false },
  { title: '强制流式', key: 'force_stream', sortable: false },
  { title: '状态', key: 'is_enabled', sortable: false },
  { title: '操作', key: 'actions', sortable: false, align: 'end' as const },
]

function loadPage() {
  store.loadModels(filterProvider.value ?? undefined)
}

function openCreate() {
  editingModel.value = null
  formDialog.value = true
}

function openEdit(model: ModelItem) {
  editingModel.value = model
  formDialog.value = true
}

function confirmDelete(model: ModelItem) {
  deletingModel.value = model
  deleteDialog.value = true
}

async function doDelete() {
  if (!deletingModel.value) return
  deleteLoading.value = true
  try {
    await store.deleteModel(deletingModel.value.id)
  } finally {
    deleteLoading.value = false
    deleteDialog.value = false
  }
}

function onSaved() {
  loadPage()
}

onMounted(() => {
  store.loadProviders()
  loadPage()
})
</script>
