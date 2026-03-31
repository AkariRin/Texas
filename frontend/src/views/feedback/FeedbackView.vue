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

      <v-data-table
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
            <span class="text-caption">{{ item.user_id }}</span>
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

    <!-- 详情抽屉 -->
    <v-navigation-drawer v-model="detailDrawer" location="right" temporary width="500">
      <v-card v-if="currentFeedback" flat>
        <v-card-title class="d-flex align-center ga-2 pa-4">
          <v-icon>mdi-message-text</v-icon>
          <span>反馈详情</span>
          <v-spacer />
          <v-btn icon size="small" variant="text" @click="detailDrawer = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>

        <v-divider />

        <v-card-text class="pa-4">
          <v-row dense>
            <v-col cols="12">
              <div class="text-caption text-medium-emphasis">反馈 ID</div>
              <div class="text-body-2 font-weight-medium">{{ currentFeedback.id }}</div>
            </v-col>
            <v-col cols="6">
              <div class="text-caption text-medium-emphasis">提交者</div>
              <div class="d-flex align-center ga-2 mt-1">
                <v-avatar size="24">
                  <v-img :src="`https://q1.qlogo.cn/g?b=qq&nk=${currentFeedback.user_id}&s=40`" />
                </v-avatar>
                <span class="text-body-2">{{ currentFeedback.user_id }}</span>
              </div>
            </v-col>
            <v-col cols="6">
              <div class="text-caption text-medium-emphasis">来源</div>
              <div class="text-body-2 font-weight-medium">
                {{ sourceLabel(currentFeedback.source) }}
              </div>
            </v-col>
            <v-col cols="6">
              <div class="text-caption text-medium-emphasis">类型</div>
              <v-chip
                :color="typeColor(currentFeedback.feedback_type)"
                size="small"
                variant="elevated"
              >
                {{ currentFeedback.feedback_type || '未分类' }}
              </v-chip>
            </v-col>
            <v-col cols="6">
              <div class="text-caption text-medium-emphasis">状态</div>
              <v-chip :color="statusColor(currentFeedback.status)" size="small" variant="elevated">
                {{ statusLabel(currentFeedback.status) }}
              </v-chip>
            </v-col>
            <v-col cols="12">
              <div class="text-caption text-medium-emphasis">提交时间</div>
              <div class="text-body-2">{{ formatTime(currentFeedback.created_at) }}</div>
            </v-col>
            <v-col v-if="currentFeedback.processed_at" cols="12">
              <div class="text-caption text-medium-emphasis">处理时间</div>
              <div class="text-body-2">{{ formatTime(currentFeedback.processed_at) }}</div>
            </v-col>
          </v-row>

          <v-divider class="my-4" />

          <div class="text-subtitle-2 mb-2">反馈内容</div>
          <v-card variant="elevated" class="pa-3 mb-4">
            <div class="text-body-2">{{ currentFeedback.content }}</div>
          </v-card>

          <div v-if="currentFeedback.admin_reply" class="mb-4">
            <div class="text-subtitle-2 mb-2">管理员回复</div>
            <v-card variant="elevated" color="blue-lighten-5" class="pa-3">
              <div class="text-body-2">{{ currentFeedback.admin_reply }}</div>
            </v-card>
          </div>

          <v-divider class="my-4" />

          <div class="text-subtitle-2 mb-2">管理操作</div>
          <v-select
            v-model="editStatus"
            :items="statusOptions"
            label="状态"
            density="compact"
            variant="outlined"
            class="mb-3"
          />
          <v-textarea
            v-model="editReply"
            label="管理员回复"
            density="compact"
            variant="outlined"
            rows="4"
            class="mb-3"
          />
          <v-btn
            block
            variant="elevated"
            color="primary"
            :loading="updateLoading"
            @click="saveAndNotify"
          >
            保存并通知用户
          </v-btn>
        </v-card-text>
      </v-card>
    </v-navigation-drawer>

    <!-- 导出对话框 -->
    <v-dialog v-model="exportDialog" max-width="500">
      <v-card>
        <v-card-title class="pa-4">导出反馈</v-card-title>
        <v-divider />
        <v-card-text class="pa-4">
          <div class="text-body-2 mb-3">已选择 {{ selected.length }} 条反馈</div>
          <v-radio-group v-model="exportMode" density="compact">
            <v-radio label="完整模式（包含所有信息）" value="full" />
            <v-radio label="仅需求模式（按类型分组）" value="requirements-only" />
          </v-radio-group>
        </v-card-text>
        <v-card-actions class="pa-4">
          <v-spacer />
          <v-btn variant="elevated" @click="exportDialog = false">取消</v-btn>
          <v-btn variant="elevated" color="primary" @click="doExport">下载 Markdown</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </PageLayout>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import * as feedbackApi from '@/apis/feedback'
import type { Feedback } from '@/apis/feedback'
import { exportToMarkdown, type ExportMode } from '@/utils/feedbackExport'
import PageLayout from '@/components/PageLayout.vue'
import { formatTime } from '@/utils/format'
import { debounce } from '@/utils/ui'

const page = ref(1)
const pageSize = ref(20)
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
const editStatus = ref('')
const editReply = ref('')
const updateLoading = ref(false)

const exportDialog = ref(false)
const exportMode = ref<ExportMode>('full')

const statusOptions = [
  { title: '待处理', value: 'pending' },
  { title: '已处理', value: 'done' },
]

const typeOptions = [
  { title: 'Bug', value: 'bug' },
  { title: '建议', value: 'suggestion' },
  { title: '投诉', value: 'complaint' },
  { title: '其他', value: 'other' },
]

const sourceOptions = [
  { title: '群聊', value: 'group' },
  { title: '私聊', value: 'private' },
]

const headers = [
  { title: 'ID', key: 'id', sortable: false },
  { title: '类型', key: 'feedback_type', sortable: false },
  { title: '状态', key: 'status', sortable: false },
  { title: '提交者', key: 'user_id', sortable: false },
  { title: '来源', key: 'source', sortable: false },
  { title: '提交时间', key: 'created_at', sortable: false },
  { title: '操作', key: 'actions', sortable: false, align: 'center' as const },
]

const debouncedLoad = debounce(() => loadPage(1))

async function loadPage(p: number) {
  page.value = p
  loading.value = true
  try {
    const result = await feedbackApi.list({
      page: p,
      page_size: pageSize.value,
      status: filterStatus.value,
      feedback_type: filterType.value,
      source: filterSource.value,
      search: searchKeyword.value,
    })
    items.value = result.items
    total.value = result.total
  } catch {
    items.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function onPageSizeChange(size: number) {
  pageSize.value = size
  loadPage(1)
}

function openDetail(feedback: Feedback) {
  currentFeedback.value = feedback
  editStatus.value = feedback.status
  editReply.value = feedback.admin_reply || ''
  detailDrawer.value = true
}

async function saveAndNotify() {
  if (!currentFeedback.value) return
  updateLoading.value = true
  try {
    await feedbackApi.updateStatus(currentFeedback.value.id, {
      status: editStatus.value,
      admin_reply: editReply.value || null,
    })
    detailDrawer.value = false
    loadPage(page.value)
  } catch {
    // 更新失败时保持抽屉打开，用户可重试
  } finally {
    updateLoading.value = false
  }
}

function doExport() {
  exportToMarkdown(selected.value, exportMode.value)
  exportDialog.value = false
}

function statusColor(status: string): string {
  const map: Record<string, string> = {
    pending: 'orange',
    done: 'green',
  }
  return map[status] || 'grey'
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    pending: '待处理',
    done: '已处理',
  }
  return map[status] || status
}

function sourceLabel(source: string): string {
  const map: Record<string, string> = {
    group: '群聊',
    private: '私聊',
  }
  return map[source] || source
}

function typeColor(type: string | null): string {
  const map: Record<string, string> = {
    bug: 'red',
    suggestion: 'blue',
    complaint: 'orange',
    other: 'grey',
  }
  return map[type || 'other'] || 'grey'
}

onMounted(() => loadPage(1))
</script>
