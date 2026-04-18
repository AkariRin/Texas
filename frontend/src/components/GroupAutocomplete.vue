<!-- frontend/src/components/GroupAutocomplete.vue -->
<script setup lang="ts">
/**
 * 群聊选择器 —— 支持按群号/群名称混合搜索的 Vuetify autocomplete 组件。
 */
import { ref, computed, watch } from 'vue'
import { usePersonnelStore } from '@/stores/personnel'
import { fetchGroups, fetchGroup } from '@/apis/personnel'
import type { GroupItem } from '@/apis/personnel'
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
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: null,
  label: '群聊',
  density: 'compact',
  variant: 'solo-filled',
  hideDetails: true,
  clearable: true,
  rules: () => [],
})

const emit = defineEmits<{
  'update:modelValue': [value: number | null]
}>()

const store = usePersonnelStore()
const suggestions = ref<GroupItem[]>([])
const loading = ref(false)
let debounceTimer: ReturnType<typeof setTimeout> | null = null
let justSelected = false

/** 通过 group_id 快速查找 GroupItem，用于 #item slot 渲染 */
const suggestionMap = computed<Map<number, GroupItem>>(() => {
  const map = new Map<number, GroupItem>()
  for (const g of suggestions.value) {
    map.set(g.group_id, g)
  }
  return map
})

// 当 modelValue 预填充时，确保对应 item 在 suggestions 中（display 正确渲染）
watch(
  () => props.modelValue,
  async (id) => {
    if (id === null) return
    if (suggestions.value.some((g) => g.group_id === id)) return
    const local = store.sessionGroups.find((g) => g.group_id === id)
    if (local) {
      if (!suggestions.value.some((g) => g.group_id === local.group_id)) {
        suggestions.value = [local, ...suggestions.value]
      }
      return
    }
    try {
      const group = await fetchGroup(id)
      if (!suggestions.value.some((g) => g.group_id === group.group_id)) {
        suggestions.value = [group, ...suggestions.value]
      }
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
  const localResults = store.sessionGroups.filter(
    (g) => g.group_name.toLowerCase().includes(qLower) || String(g.group_id).includes(q),
  )
  suggestions.value = localResults.slice(0, 10)

  // Phase 2: 本地不足 5 条时走 API
  if (debounceTimer !== null) {
    clearTimeout(debounceTimer)
    debounceTimer = null
  }
  if (localResults.length < 5) {
    debounceTimer = setTimeout(async () => {
      loading.value = true
      try {
        const numericId = /^\d+$/.test(q) ? Number(q) : null
        if (numericId !== null) {
          // 纯数字：精确查询单条群组
          const exactGroup = await fetchGroup(numericId).catch(() => null)
          if (exactGroup && !suggestions.value.some((g) => g.group_id === exactGroup.group_id)) {
            suggestions.value = [...suggestions.value, exactGroup].slice(0, 10)
          }
        } else {
          // 文字：按群名模糊搜索
          const result = await fetchGroups({ group_name: q, page_size: 10 })
          const existingIds = new Set(suggestions.value.map((g) => g.group_id))
          const newItems = result.items.filter((g) => !existingIds.has(g.group_id))
          suggestions.value = [...suggestions.value, ...newItems].slice(0, 10)
        }
      } catch {
        // 静默失败，本地结果仍可用
      } finally {
        loading.value = false
      }
    }, 300)
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
    item-value="group_id"
    :item-title="(item: GroupItem) => `${item.group_name}（${item.group_id}）`"
    no-filter
    @update:model-value="onSelect"
    @update:search="onSearch"
  >
    <template #item="{ props: itemProps }">
      <!-- itemProps.value 即 group_id -->
      <v-list-item v-bind="itemProps" :title="undefined">
        <template
          v-if="suggestionMap.get(itemProps.value as number) as GroupItem | undefined"
          #prepend
        >
          <v-avatar size="40" class="mr-2">
            <v-img
              :src="`https://p.qlogo.cn/gh/${itemProps.value}/${itemProps.value}/40`"
              :alt="(suggestionMap.get(itemProps.value as number) as GroupItem).group_name"
            >
              <template #error>
                <v-icon>mdi-account-group</v-icon>
              </template>
            </v-img>
          </v-avatar>
        </template>
        <v-list-item-title>
          <span class="font-weight-medium">
            {{
              (suggestionMap.get(itemProps.value as number) as GroupItem | undefined)?.group_name ??
              itemProps.title
            }}
          </span>
          <span class="text-medium-emphasis text-body-2 ml-1">（{{ itemProps.value }}）</span>
        </v-list-item-title>
      </v-list-item>
    </template>
  </v-autocomplete>
</template>
