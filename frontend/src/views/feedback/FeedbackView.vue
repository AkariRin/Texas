<template>
  <PageLayout>
    <v-card flat>
      <v-card-title class="d-flex align-center flex-wrap ga-2">
        <!-- 筛选器 -->
        <v-select
          v-model="filterStatus"
          :items="statusOptions"
          label="状态"
          density="compact"
          variant="solo-filled"
          hide-details
          clearable
          style="max-width: 150px"
          @update:model-value="loadPage(1)"
        />
        <v-select
          v-model="filterType"
          :items="typeOptions"
          label="类型"
          density="compact"
          variant="solo-filled"
          hide-details
          clearable
          style="max-width: 150px"
          @update:model-value="loadPage(1)"
        />
        <v-select
          v-model="filterSource"
          :items="sourceOptions"
          label="来源"
          density="compact"
          variant="solo-filled"
          hide-details
          clearable
          style="max-width: 150px"
          @update:model-value="loadPage(1)"
        />
        <v-text-field
          v-model="searchKeyword"
          label="搜索内容"
          density="compact"
          variant="solo-filled"
          hide-details
          clearable
          prepend-inner-icon="mdi-magnify"
          style="max-width: 250px"
          @update:model-value="debouncedLoad"
        />
        <v-spacer />
        <v-btn
          variant="elevated"
          color="primary"
          prepend-icon="mdi-download"
          :disabled="!selected.length"
          @click="exportDialog = true"
        >
          导出选中
        </v-btn>
      </v-card-title>

      <v-skeleton-loader v-if="loading && !items.length" type="table" class="pa-2" />
      <v-data-table
        v-else
        v-model="selected"
        :headers="headers"
        :items="items"
        :items-length="total"
        :loading="loading"
        :page="page"
        :items-per-page="pageSize"
        :items-per-page-options="[10, 20, 50]"
        show-select
        hover
        @update:page="loadPage"
        @update:items-per-page="onPageSizeChange"
      >
        <!-- ID 列：前8位 -->
        <template #[`item.id`]="{ item }">
          <span class="text-caption font-weight-medium">{{ item.id.slice(0, 8) }}</span>
        </template>

        <!-- 类型列 -->
        <template #[`item.feedback_type`]="{ item }">
          <v-chip :color="typeColor(item.feedback_type)" size="small" variant="elevated">
            {{ item.feedback_type || '未分类' }}
          </v-chip>
        </template>

        <!-- 状态列 -->
        <template #[`item.status`]="{ item }">
          <v-chip :color="statusColor(item.status)" size="small" variant="elevated">
            {{ statusLabel(item.status) }}
          </v-chip>
        </template>

        <!-- 提交者列 -->
        <template #[`item.user_id`]="{ item }">
          <div class="d-flex align-center ga-2">
            <v-avatar size="24">
              <v-img :src="`https://q1.qlogo.cn/g?b=qq&nk=${item.user_id}&s=40`" />
            </v-avatar>
            <span class="text-caption">
              {{ personnelStore.getUserName(item.user_id) }}（{{ item.user_id }}）
            </span>
          </div>
        </template>

        <!-- 来源列 -->
        <template #[`item.source`]="{ item }">
          <span class="text-caption">{{ sourceLabel(item.source) }}</span>
        </template>

        <!-- 提交时间列 -->
        <template #[`item.created_at`]="{ item }">
          <span class="text-caption text-medium-emphasis">{{ formatTime(item.created_at) }}</span>
        </template>

        <!-- 操作列 -->
        <template #[`item.actions`]="{ item }">
          <v-btn icon size="small" variant="text" @click="openDetail(item)">
            <v-icon>mdi-eye</v-icon>
            <v-tooltip activator="parent" location="top">查看详情</v-tooltip>
          </v-btn>
        </template>
      </v-data-table>
    </v-card>

    <FeedbackDetailDrawer
      v-model="detailDrawer"
      :feedback="currentFeedback"
      @saved="loadPage(page)"
    />

    <FeedbackExportDialog v-model="exportDialog" :selected="selected" />
  </PageLayout>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import * as feedbackApi from '@/apis/feedback'
import type { Feedback } from '@/apis/feedback'
import PageLayout from '@/layouts/PageLayout.vue'
import { formatTime } from '@/utils/format'
import { usePagination } from '@/composables/usePagination'
import {
  statusOptions,
  typeOptions,
  sourceOptions,
  statusColor,
  statusLabel,
  sourceLabel,
  typeColor,
} from '@/utils/feedback'
import FeedbackDetailDrawer from '@/components/feedback/FeedbackDetailDrawer.vue'
import FeedbackExportDialog from '@/components/feedback/FeedbackExportDialog.vue'
import { usePersonnelStore } from '@/stores/personnel'

const personnelStore = usePersonnelStore()

const loading = ref(false)
const items = ref<Feedback[]>([])
const total = ref(0)
const selected = ref<Feedback[]>([])

const filterStatus = ref<string | null>(null)
const filterType = ref<string | null>(null)
const filterSource = ref<string | null>(null)
const searchKeyword = ref<string | null>(null)

const detailDrawer = ref(false)
const currentFeedback = ref<Feedback | null>(null)

const exportDialog = ref(false)

const headers = [
  { title: 'ID', key: 'id', sortable: false },
  { title: '类型', key: 'feedback_type', sortable: false },
  { title: '状态', key: 'status', sortable: false },
  { title: '提交者', key: 'user_id', sortable: false },
  { title: '来源', key: 'source', sortable: false },
  { title: '提交时间', key: 'created_at', sortable: false },
  { title: '操作', key: 'actions', sortable: false, align: 'center' as const },
]

async function fetchFeedbacks(p: number, size: number) {
  loading.value = true
  try {
    const result = await feedbackApi.list({
      page: p,
      page_size: size,
      status: filterStatus.value,
      feedback_type: filterType.value,
      source: filterSource.value,
      search: searchKeyword.value,
    })
    items.value = result.items
    total.value = result.total
    // 预取用户和群昵称，减少渲染闪烁
    const userIds = [...new Set(result.items.map((f) => f.user_id))]
    const groupIds = [
      ...new Set(result.items.map((f) => f.group_id).filter((id): id is number => id != null)),
    ]
    personnelStore.prefetchIds(userIds, groupIds)
  } catch {
    items.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

const { page, pageSize, loadPage, onPageSizeChange, debouncedLoad } = usePagination(fetchFeedbacks)

function openDetail(feedback: Feedback) {
  currentFeedback.value = feedback
  detailDrawer.value = true
}

onMounted(() => loadPage(1))
</script>
