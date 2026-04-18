<template>
  <PageLayout>
    <v-card flat>
      <!-- 工具栏 -->
      <v-card-title class="d-flex align-center flex-wrap ga-2 pt-3">
        <span class="text-h6">定时点赞任务</span>
        <v-spacer />
        <v-btn color="primary" prepend-icon="mdi-plus" variant="tonal" @click="openCreate">
          新增任务
        </v-btn>
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
        <!-- 来源群列 -->
        <template #[`item.registered_group_id`]="{ item }">
          {{ item.registered_group_id ?? '私聊' }}
        </template>

        <!-- 注册时间列 -->
        <template #[`item.registered_at`]="{ item }">
          {{ formatTime(item.registered_at) }}
        </template>

        <!-- 操作列 -->
        <template #[`item.actions`]="{ item }">
          <v-btn
            color="error"
            variant="text"
            size="small"
            icon="mdi-delete"
            :loading="cancellingQq === item.qq"
            @click="confirmCancel(item)"
          />
        </template>
      </v-data-table>
    </v-card>

    <!-- 新增任务对话框 -->
    <v-dialog v-model="createDialog" max-width="400">
      <v-card>
        <v-card-title>新增定时点赞任务</v-card-title>
        <v-card-text>
          <UserAutocomplete
            v-model="newQq"
            label="用户 QQ 号"
            variant="outlined"
            :hide-details="false"
            autofocus
          />
          <div v-if="createError" class="text-error text-caption mt-1">{{ createError }}</div>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="createDialog = false">取消</v-btn>
          <v-btn color="primary" :loading="creating" @click="submitCreate">确认</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 取消确认对话框 -->
    <v-dialog v-model="cancelDialog" max-width="360">
      <v-card>
        <v-card-title>确认取消？</v-card-title>
        <v-card-text>将取消 QQ {{ cancelTarget?.qq }} 的定时点赞任务。</v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="cancelDialog = false">返回</v-btn>
          <v-btn color="error" :loading="!!cancellingQq" @click="doCancel">确认取消</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </PageLayout>
</template>

<script setup lang="ts">
/**
 * 定时点赞任务管理页面 —— 展示/创建/取消用户定时点赞任务。
 */
import { ref, onMounted } from 'vue'

import PageLayout from '@/layouts/PageLayout.vue'
import { listTasks, createTask, cancelTask, type LikeTask } from '@/apis/like'
import UserAutocomplete from '@/components/UserAutocomplete.vue'
import { usePagination } from '@/composables/usePagination'
import { formatTime } from '@/utils/format'

// ── 列表状态 ──
const loading = ref(false)
const items = ref<LikeTask[]>([])
const total = ref(0)

const headers = [
  { title: 'QQ', key: 'qq', sortable: false },
  { title: '注册时间', key: 'registered_at', sortable: false },
  { title: '来源群', key: 'registered_group_id', sortable: false },
  { title: '操作', key: 'actions', sortable: false, align: 'end' as const },
]

async function fetchTasks(p: number, size: number) {
  loading.value = true
  try {
    const result = await listTasks({ page: p, page_size: size })
    items.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

const { page, pageSize, loadPage, onPageSizeChange } = usePagination(fetchTasks)

// ── 新增任务 ──
const createDialog = ref(false)
const newQq = ref<number | null>(null)
const createError = ref('')
const creating = ref(false)

function openCreate() {
  newQq.value = null
  createError.value = ''
  createDialog.value = true
}

async function submitCreate() {
  if (!newQq.value || newQq.value <= 0) {
    createError.value = '请输入有效的 QQ 号'
    return
  }
  createError.value = ''
  creating.value = true
  try {
    await createTask(newQq.value)
    createDialog.value = false
    await loadPage(1)
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string; message?: string } } }
    createError.value = err?.response?.data?.detail ?? err?.response?.data?.message ?? '创建失败'
  } finally {
    creating.value = false
  }
}

// ── 取消任务 ──
const cancelDialog = ref(false)
const cancelTarget = ref<LikeTask | null>(null)
const cancellingQq = ref<number | null>(null)

function confirmCancel(item: LikeTask) {
  cancelTarget.value = item
  cancelDialog.value = true
}

async function doCancel() {
  if (!cancelTarget.value) return
  cancellingQq.value = cancelTarget.value.qq
  cancelDialog.value = false
  try {
    await cancelTask(cancelTarget.value.qq)
    await loadPage(page.value)
  } finally {
    cancellingQq.value = null
  }
}

onMounted(() => loadPage(1))
</script>
