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
        <v-btn color="red" prepend-icon="mdi-plus" @click="openCreate"> 添加模型 </v-btn>
      </v-card-title>

      <v-data-table :headers="headers" :items="store.models" :loading="store.modelsLoading" hover>
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
            <div>入: &#xFFE5;{{ item.input_price.toFixed(2) }}/M</div>
            <div>出: &#xFFE5;{{ item.output_price.toFixed(2) }}/M</div>
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
      <v-dialog :model-value="formDialog" max-width="600" @update:model-value="formDialog = $event">
        <v-card>
          <v-card-title>
            {{ isEditModel ? '编辑模型' : '添加模型' }}
          </v-card-title>

          <v-card-text>
            <v-form ref="modelFormRef" @submit.prevent="submitModelForm">
              <!-- 提供商选择（仅创建时） -->
              <v-select
                v-if="!isEditModel"
                v-model="modelForm.provider_id"
                :items="providerOptions"
                label="所属提供商"
                :rules="[rules.required]"
                variant="outlined"
                density="compact"
                class="mb-3"
              />

              <v-text-field
                v-model="modelForm.model_name"
                label="模型标识"
                :rules="[rules.required]"
                :disabled="isEditModel"
                variant="outlined"
                density="compact"
                class="mb-3"
                placeholder="如 gpt-4o, deepseek-chat"
              />

              <v-text-field
                v-model="modelForm.display_name"
                label="展示名称 (可选)"
                variant="outlined"
                density="compact"
                class="mb-3"
                placeholder="如 GPT-4o"
              />

              <v-row dense class="mb-3">
                <v-col cols="6">
                  <v-text-field
                    v-model.number="modelForm.input_price"
                    label="输入价格 (&#xFFE5;/M tokens)"
                    variant="outlined"
                    density="compact"
                    type="number"
                    step="0.01"
                    min="0"
                  />
                </v-col>
                <v-col cols="6">
                  <v-text-field
                    v-model.number="modelForm.output_price"
                    label="输出价格 (&#xFFE5;/M tokens)"
                    variant="outlined"
                    density="compact"
                    type="number"
                    step="0.01"
                    min="0"
                  />
                </v-col>
              </v-row>

              <!-- 温度滑块 -->
              <div class="text-body-2 mb-1">温度: {{ modelForm.temperature.toFixed(1) }}</div>
              <v-slider
                v-model="modelForm.temperature"
                :min="0"
                :max="2"
                :step="0.1"
                color="red"
                thumb-label
                class="mb-3"
              />

              <v-text-field
                v-model.number="modelForm.max_tokens"
                label="最大输出 Token (可选)"
                variant="outlined"
                density="compact"
                class="mb-3"
                type="number"
                min="1"
                clearable
              />

              <v-switch
                v-model="modelForm.force_stream"
                label="强制流式输出"
                color="red"
                density="compact"
                hide-details
                class="mb-3"
              />

              <!-- 额外参数 JSON 编辑器 -->
              <v-textarea
                v-model="extraParamsStr"
                label="额外参数 (JSON)"
                variant="outlined"
                density="compact"
                rows="3"
                :error-messages="jsonError"
                class="mb-3"
                placeholder='{"top_p": 0.9, "frequency_penalty": 0.5}'
              />
            </v-form>
          </v-card-text>

          <v-card-actions>
            <v-spacer />
            <v-btn @click="formDialog = false">取消</v-btn>
            <v-btn color="red" :loading="modelSaving" @click="submitModelForm">
              {{ isEditModel ? '保存' : '创建' }}
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>

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
import { ref, computed, watch, onMounted } from 'vue'
import { useLLMStore } from '@/stores/llm'
import type { ModelItem } from '@/apis/llm'

const store = useLLMStore()

const filterProvider = ref<string | null>(null)
const formDialog = ref(false)
const editingModel = ref<ModelItem | null>(null)
const deleteDialog = ref(false)
const deletingModel = ref<ModelItem | null>(null)
const deleteLoading = ref(false)

const providerOptions = computed(() => store.providers.map((p) => ({ title: p.name, value: p.id })))

const headers = [
  { title: '模型名称', key: 'model_name', sortable: false },
  { title: '提供商', key: 'provider_name', sortable: false },
  { title: '价格 (CNY/M tokens)', key: 'price', sortable: false },
  { title: '温度', key: 'temperature', sortable: false },
  { title: '最大 Token', key: 'max_tokens', sortable: false },
  { title: '强制流式', key: 'force_stream', sortable: false },
  { title: '操作', key: 'actions', sortable: false, align: 'end' as const },
]

// ── 模型表单状态 ──

const isEditModel = computed(() => !!editingModel.value)
const modelSaving = ref(false)
const modelFormRef = ref()
const jsonError = ref('')

const modelForm = ref({
  provider_id: '',
  model_name: '',
  display_name: '',
  input_price: 0,
  output_price: 0,
  temperature: 0.7,
  max_tokens: null as number | null,
  force_stream: false,
})

const extraParamsStr = ref('{}')

const rules = {
  required: (v: string) => !!v || '此字段不能为空',
}

watch(formDialog, (open) => {
  if (open) {
    jsonError.value = ''
    if (editingModel.value) {
      modelForm.value = {
        provider_id: editingModel.value.provider_id,
        model_name: editingModel.value.model_name,
        display_name: editingModel.value.display_name ?? '',
        input_price: editingModel.value.input_price,
        output_price: editingModel.value.output_price,
        temperature: editingModel.value.temperature,
        max_tokens: editingModel.value.max_tokens,
        force_stream: editingModel.value.force_stream,
      }
      extraParamsStr.value = JSON.stringify(editingModel.value.extra_params || {}, null, 2)
    } else {
      modelForm.value = {
        provider_id: '',
        model_name: '',
        display_name: '',
        input_price: 0,
        output_price: 0,
        temperature: 0.7,
        max_tokens: null,
        force_stream: false,
      }
      extraParamsStr.value = '{}'
    }
  }
})

// ── 操作 ──

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

async function submitModelForm() {
  const result = await modelFormRef.value?.validate()
  const valid = result?.valid
  if (!valid) return

  // 校验 JSON
  let extraParams: Record<string, unknown> = {}
  try {
    extraParams = JSON.parse(extraParamsStr.value || '{}')
    jsonError.value = ''
  } catch {
    jsonError.value = '无效的 JSON 格式'
    return
  }

  modelSaving.value = true
  try {
    if (isEditModel.value && editingModel.value) {
      await store.updateModel(editingModel.value.id, {
        display_name: modelForm.value.display_name || null,
        input_price: modelForm.value.input_price,
        output_price: modelForm.value.output_price,
        temperature: modelForm.value.temperature,
        max_tokens: modelForm.value.max_tokens,
        force_stream: modelForm.value.force_stream,
        extra_params: extraParams,
      })
    } else {
      await store.createModel({
        provider_id: modelForm.value.provider_id,
        model_name: modelForm.value.model_name,
        display_name: modelForm.value.display_name || null,
        input_price: modelForm.value.input_price,
        output_price: modelForm.value.output_price,
        temperature: modelForm.value.temperature,
        max_tokens: modelForm.value.max_tokens,
        force_stream: modelForm.value.force_stream,
        extra_params: extraParams,
      })
    }
    loadPage()
    formDialog.value = false
  } finally {
    modelSaving.value = false
  }
}

onMounted(() => {
  store.loadProviders()
  loadPage()
})
</script>
