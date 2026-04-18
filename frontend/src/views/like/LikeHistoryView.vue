<template>
  <PageLayout>
    <v-card flat>
      <!-- 筛选栏 -->
      <v-card-title class="d-flex align-center flex-wrap ga-2 pt-3">
        <v-text-field
          v-model.number="filter.qq"
          label="QQ 号"
          density="compact"
          variant="solo-filled"
          hide-details
          clearable
          type="number"
          style="max-width: 160px"
          @update:model-value="debouncedLoad"
        />
        <v-select
          v-model="filter.source"
          :items="sourceOptions"
          label="来源"
          density="compact"
          variant="solo-filled"
          hide-details
          clearable
          style="max-width: 140px"
          @update:model-value="loadPage(1)"
        />
        <v-text-field
          v-model="filter.date_from"
          label="开始日期"
          density="compact"
          variant="solo-filled"
          hide-details
          clearable
          type="date"
          style="max-width: 180px"
          @update:model-value="loadPage(1)"
        />
        <v-text-field
          v-model="filter.date_to"
          label="结束日期"
          density="compact"
          variant="solo-filled"
          hide-details
          clearable
          type="date"
          style="max-width: 180px"
          @update:model-value="loadPage(1)"
        />
      </v-card-title>

      <v-skeleton-loader v-if="loading && !items.length" type="table" class="pa-2" />
      <v-data-table
        v-else
        :headers="headers"
        :items="items"
        :items-length="total"
        :loading="loading"
        :page="page"
        :items-per-page="pageSize"
        :items-per-page-options="[10, 20, 50]"
        hover
        @update:page="loadPage"
        @update:items-per-page="onPageSizeChange"
      >
        <!-- 来源列 -->
        <template #[`item.source`]="{ item }">
          <v-chip
            :color="item.source === 'scheduled' ? 'blue' : 'green'"
            size="small"
            variant="tonal"
          >
            {{ item.source === 'scheduled' ? '定时' : '手动' }}
          </v-chip>
        </template>

        <!-- 成功/失败列 -->
        <template #[`item.success`]="{ item }">
          <v-icon :color="item.success ? 'success' : 'error'" size="small">
            {{ item.success ? 'mdi-check-circle' : 'mdi-close-circle' }}
          </v-icon>
        </template>

        <!-- 时间列 -->
        <template #[`item.triggered_at`]="{ item }">
          {{ formatDate(item.triggered_at) }}
        </template>
      </v-data-table>
    </v-card>
  </PageLayout>
</template>

<script setup lang="ts">
/**
 * 点赞历史记录查询页面 —— 支持按 QQ 号、来源、日期范围筛选。
 */
import { ref, reactive, onMounted } from 'vue'

import PageLayout from '@/layouts/PageLayout.vue'
import { listHistory, type LikeHistory } from '@/apis/like'
import { usePagination } from '@/composables/usePagination'

// ── 列表状态 ──
const loading = ref(false)
const items = ref<LikeHistory[]>([])
const total = ref(0)

const filter = reactive({
  qq: null as number | null,
  source: null as 'manual' | 'scheduled' | null,
  date_from: null as string | null,
  date_to: null as string | null,
})

const sourceOptions = [
  { title: '手动', value: 'manual' },
  { title: '定时', value: 'scheduled' },
]

const headers = [
  { title: 'QQ', key: 'qq', sortable: false },
  { title: '次数', key: 'times', sortable: false },
  { title: '来源', key: 'source', sortable: false },
  { title: '成功', key: 'success', sortable: false },
  { title: '执行时间', key: 'triggered_at', sortable: false },
]

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('zh-CN', { hour12: false })
}

async function fetchHistory(p: number, size: number) {
  loading.value = true
  try {
    const result = await listHistory({
      qq: filter.qq ?? undefined,
      source: filter.source ?? undefined,
      date_from: filter.date_from ?? undefined,
      date_to: filter.date_to ?? undefined,
      page: p,
      page_size: size,
    })
    items.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

const { page, pageSize, loadPage, onPageSizeChange, debouncedLoad } = usePagination(fetchHistory)

onMounted(() => loadPage(1))
</script>
