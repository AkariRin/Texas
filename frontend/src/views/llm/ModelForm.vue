<template>
  <v-dialog :model-value="modelValue" max-width="600" @update:model-value="$emit('update:modelValue', $event)">
    <v-card>
      <v-card-title>
        {{ isEdit ? '编辑模型' : '添加模型' }}
      </v-card-title>

      <v-card-text>
        <v-form ref="formRef" @submit.prevent="submit">
          <!-- 提供商选择（仅创建时） -->
          <v-select
            v-if="!isEdit"
            v-model="form.provider_id"
            :items="providerOptions"
            label="所属提供商"
            :rules="[rules.required]"
            variant="outlined"
            density="compact"
            class="mb-3"
          />

          <v-text-field
            v-model="form.model_name"
            label="模型标识"
            :rules="[rules.required]"
            :disabled="isEdit"
            variant="outlined"
            density="compact"
            class="mb-3"
            placeholder="如 gpt-4o, deepseek-chat"
          />

          <v-text-field
            v-model="form.display_name"
            label="展示名称 (可选)"
            variant="outlined"
            density="compact"
            class="mb-3"
            placeholder="如 GPT-4o"
          />

          <v-row dense class="mb-3">
            <v-col cols="6">
              <v-text-field
                v-model.number="form.input_price"
                label="输入价格 (¥/M tokens)"
                variant="outlined"
                density="compact"
                type="number"
                step="0.01"
                min="0"
              />
            </v-col>
            <v-col cols="6">
              <v-text-field
                v-model.number="form.output_price"
                label="输出价格 (¥/M tokens)"
                variant="outlined"
                density="compact"
                type="number"
                step="0.01"
                min="0"
              />
            </v-col>
          </v-row>

          <!-- 温度滑块 -->
          <div class="text-body-2 mb-1">温度: {{ form.temperature.toFixed(1) }}</div>
          <v-slider
            v-model="form.temperature"
            :min="0"
            :max="2"
            :step="0.1"
            color="red"
            thumb-label
            class="mb-3"
          />

          <v-text-field
            v-model.number="form.max_tokens"
            label="最大输出 Token (可选)"
            variant="outlined"
            density="compact"
            class="mb-3"
            type="number"
            min="1"
            clearable
          />

          <v-switch
            v-model="form.force_stream"
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
        <v-btn @click="$emit('update:modelValue', false)">取消</v-btn>
        <v-btn color="red" :loading="saving" @click="submit">
          {{ isEdit ? '保存' : '创建' }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useLLMStore } from '@/stores/llm'
import type { ModelItem, ProviderItem } from '@/services/llm'

const props = defineProps<{
  modelValue: boolean
  modelItem: ModelItem | null
  providers: ProviderItem[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  saved: []
}>()

const store = useLLMStore()

const isEdit = computed(() => !!props.modelItem)
const saving = ref(false)
const formRef = ref()
const jsonError = ref('')

const providerOptions = computed(() =>
  props.providers.map((p) => ({ title: p.name, value: p.id })),
)

const form = ref({
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

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      jsonError.value = ''
      if (props.modelItem) {
        form.value = {
          provider_id: props.modelItem.provider_id,
          model_name: props.modelItem.model_name,
          display_name: props.modelItem.display_name ?? '',
          input_price: props.modelItem.input_price,
          output_price: props.modelItem.output_price,
          temperature: props.modelItem.temperature,
          max_tokens: props.modelItem.max_tokens,
          force_stream: props.modelItem.force_stream,
        }
        extraParamsStr.value = JSON.stringify(props.modelItem.extra_params || {}, null, 2)
      } else {
        form.value = {
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
  },
)

async function submit() {
  const result = await formRef.value?.validate()
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

  saving.value = true
  try {
    if (isEdit.value && props.modelItem) {
      await store.updateModel(props.modelItem.id, {
        display_name: form.value.display_name || null,
        input_price: form.value.input_price,
        output_price: form.value.output_price,
        temperature: form.value.temperature,
        max_tokens: form.value.max_tokens,
        force_stream: form.value.force_stream,
        extra_params: extraParams,
      })
    } else {
      await store.createModel({
        provider_id: form.value.provider_id,
        model_name: form.value.model_name,
        display_name: form.value.display_name || null,
        input_price: form.value.input_price,
        output_price: form.value.output_price,
        temperature: form.value.temperature,
        max_tokens: form.value.max_tokens,
        force_stream: form.value.force_stream,
        extra_params: extraParams,
      })
    }
    emit('saved')
    emit('update:modelValue', false)
  } finally {
    saving.value = false
  }
}
</script>

