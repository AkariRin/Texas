<!-- frontend/src/components/UserAutocomplete.vue -->
<script setup lang="ts">
/**
 * 用户选择器 —— 支持按 QQ 号/昵称混合搜索的 Vuetify autocomplete 组件。
 */
import { ref, computed, watch } from 'vue'
import { usePersonnelStore } from '@/stores/personnel'
import { fetchUsers, fetchUser } from '@/apis/personnel'
import type { UserItem } from '@/apis/personnel'
import type { Density } from 'vuetify/lib/composables/density.js'

type FieldVariant =
  | 'outlined'
  | 'plain'
  | 'solo-filled'
  | 'filled'
  | 'solo'
  | 'solo-inverted'
  | 'underlined'

interface Props {
  modelValue: number | null
  label?: string
  density?: Density
  variant?: FieldVariant
  hideDetails?: boolean | 'auto'
  clearable?: boolean
  rules?: ((v: unknown) => boolean | string)[]
  autofocus?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: null,
  label: '用户',
  density: 'compact',
  variant: 'solo-filled',
  hideDetails: true,
  clearable: true,
  rules: () => [],
  autofocus: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: number | null]
}>()

const store = usePersonnelStore()
const suggestions = ref<UserItem[]>([])
const loading = ref(false)
let debounceTimer: ReturnType<typeof setTimeout> | null = null
let justSelected = false
let requestSeq = 0
let watchSeq = 0

/** 通过 qq 快速查找 UserItem，用于 #item slot 渲染 */
const suggestionMap = computed<Map<number, UserItem>>(() => {
  const map = new Map<number, UserItem>()
  for (const u of suggestions.value) {
    map.set(u.qq, u)
  }
  return map
})

// 当 modelValue 预填充时，确保对应 item 在 suggestions 中（display 正确渲染）
watch(
  () => props.modelValue,
  async (qq) => {
    if (qq === null) return
    if (suggestions.value.some((u) => u.qq === qq)) return
    const local = store.sessionUsers.find((u) => u.qq === qq)
    if (local) {
      suggestions.value = [local, ...suggestions.value]
      return
    }
    const seq = ++watchSeq
    try {
      const user = await fetchUser(qq)
      if (watchSeq !== seq) return
      suggestions.value = [user, ...suggestions.value]
    } catch {
      // 静默失败，Vuetify 会 fallback 显示原始数字
    }
  },
  { immediate: true },
)

function onSearch(input: string | undefined | null) {
  // 刚选中条目时 Vuetify 会触发一次 update:search，跳过
  if (justSelected) {
    justSelected = false
    return
  }

  const q = (input ?? '').trim()
  if (!q) {
    suggestions.value = []
    if (debounceTimer !== null) {
      clearTimeout(debounceTimer)
      debounceTimer = null
    }
    return
  }

  const qLower = q.toLowerCase()

  // Phase 1: 本地即时过滤
  const localResults = store.sessionUsers.filter(
    (u) => u.nickname.toLowerCase().includes(qLower) || String(u.qq).includes(q),
  )
  suggestions.value = localResults.slice(0, 10)

  // Phase 2: 本地不足 5 条时走 API
  if (debounceTimer !== null) {
    clearTimeout(debounceTimer)
    debounceTimer = null
  }
  if (localResults.length < 5) {
    const seq = ++requestSeq
    debounceTimer = setTimeout(async () => {
      loading.value = true
      try {
        const isNumeric = /^\d+$/.test(q)
        if (isNumeric) {
          // 纯数字：QQ 精确查询
          const result = await fetchUsers({ qq: Number(q), page_size: 10 }).catch(() => null)
          if (requestSeq !== seq) return
          if (result) {
            const existingQqs = new Set(suggestions.value.map((u) => u.qq))
            const newItems = result.items.filter((u) => !existingQqs.has(u.qq))
            suggestions.value = [...suggestions.value, ...newItems].slice(0, 10)
          }
        } else {
          // 文字：按昵称模糊搜索
          const result = await fetchUsers({ nickname: q, page_size: 10 })
          if (requestSeq !== seq) return
          const existingQqs = new Set(suggestions.value.map((u) => u.qq))
          const newItems = result.items.filter((u) => !existingQqs.has(u.qq))
          suggestions.value = [...suggestions.value, ...newItems].slice(0, 10)
        }
      } catch {
        // 静默失败，本地结果仍可用
      } finally {
        if (requestSeq === seq) loading.value = false
      }
    }, 300)
  } else {
    loading.value = false
  }
}

function onSelect(value: unknown) {
  justSelected = true
  const normalized = typeof value === 'number' ? value : null
  emit('update:modelValue', normalized)
}
</script>

<template>
  <v-autocomplete
    :model-value="modelValue"
    :items="suggestions"
    :loading="loading"
    :label="label"
    :density="density"
    :variant="variant"
    :hide-details="hideDetails"
    :clearable="clearable"
    :rules="rules"
    :autofocus="autofocus"
    item-value="qq"
    :item-title="(item: UserItem) => `${item.nickname}（${item.qq}）`"
    no-filter
    @update:model-value="onSelect"
    @update:search="onSearch"
  >
    <template #item="{ props: itemProps }">
      <!-- itemProps.value 即 qq -->
      <v-list-item v-bind="itemProps" :title="undefined">
        <template
          v-if="suggestionMap.get(itemProps.value as number) as UserItem | undefined"
          #prepend
        >
          <v-avatar size="40" class="mr-2">
            <v-img
              :src="`https://q1.qlogo.cn/g?b=qq&nk=${itemProps.value}&s=40`"
              :alt="(suggestionMap.get(itemProps.value as number) as UserItem).nickname"
            >
              <template #error>
                <v-icon>mdi-account-circle</v-icon>
              </template>
            </v-img>
          </v-avatar>
        </template>
        <v-list-item-title>
          <span class="font-weight-medium">
            {{
              (suggestionMap.get(itemProps.value as number) as UserItem | undefined)?.nickname ??
              itemProps.title
            }}
          </span>
          <span class="text-medium-emphasis text-body-2 ml-1">（{{ itemProps.value }}）</span>
        </v-list-item-title>
      </v-list-item>
    </template>
  </v-autocomplete>
</template>
