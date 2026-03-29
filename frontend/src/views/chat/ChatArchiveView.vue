<template>
  <PageLayout>
    <template #actions>
      <v-btn
        variant="elevated"
        color="primary"
        prepend-icon="mdi-refresh"
        :loading="store.archivesLoading"
        class="mr-2"
        @click="loadPage(1)"
      >
        刷新
      </v-btn>
      <v-btn
        variant="elevated"
        color="primary"
        prepend-icon="mdi-archive-arrow-up"
        :loading="archiving"
        @click="onTriggerArchive"
      >
        手动归档
      </v-btn>
    </template>

    <!-- 归档任务触发结果 -->
    <v-alert
      v-if="archiveResult"
      :type="archiveResult.type"
      closable
      class="mb-4"
      @click:close="archiveResult = null"
    >
      {{ archiveResult.message }}
    </v-alert>

    <!-- 归档列表 -->
    <v-card rounded="lg" elevation="2">
      <v-data-table
        :headers="headers"
        :items="store.archives.items"
        :loading="store.archivesLoading"
        :items-per-page="store.archives.page_size"
        hide-default-footer
        hover
      >
        <!-- 状态列 -->
        <template #item.status="{ item }">
          <v-chip :color="statusColor(item.status)" size="small" variant="elevated">
            {{ item.status }}
          </v-chip>
        </template>

        <!-- 行数列 -->
        <template #item.total_rows="{ item }">
          {{ formatNumber(item.total_rows) }}
        </template>

        <!-- 大小列 -->
        <template #item.compressed_bytes="{ item }">
          <span v-if="item.compressed_bytes > 0">
            {{ formatBytes(item.compressed_bytes) }}
            <span class="text-caption text-medium-emphasis ml-1" v-if="item.original_bytes > 0">
              ({{ (item.original_bytes / item.compressed_bytes).toFixed(1) }}:1)
            </span>
          </span>
          <span v-else>-</span>
        </template>

        <!-- 时间列 -->
        <template #item.created_at="{ item }">
          {{ formatTime(item.created_at) }}
        </template>

        <template #item.completed_at="{ item }">
          {{ formatTime(item.completed_at) }}
        </template>

        <!-- 操作列 -->
        <template #item.actions="{ item }">
          <v-btn
            icon="mdi-information-outline"
            size="small"
            variant="elevated"
            @click="showDetail(item)"
          ></v-btn>
        </template>

        <!-- 空状态 -->
        <template #no-data>
          <div class="text-center pa-8 text-medium-emphasis">
            <v-icon size="48" color="grey-lighten-1">mdi-archive-off-outline</v-icon>
            <p class="mt-2">暂无归档记录</p>
          </div>
        </template>
      </v-data-table>

      <!-- 分页 -->
      <v-divider></v-divider>
      <div class="d-flex align-center justify-end pa-2" v-if="store.archives.pages > 1">
        <v-pagination
          v-model="currentPage"
          :length="store.archives.pages"
          density="compact"
          total-visible="5"
          @update:model-value="loadPage"
        ></v-pagination>
      </div>
    </v-card>

    <!-- 详情弹窗 -->
    <v-dialog v-model="detailDialog" max-width="600" persistent>
      <v-card rounded="lg">
        <v-card-title class="d-flex align-center">
          <v-icon class="mr-2">mdi-archive</v-icon>
          归档详情
          <v-spacer></v-spacer>
          <v-btn
            icon="mdi-close"
            variant="elevated"
            size="small"
            @click="detailDialog = false"
          ></v-btn>
        </v-card-title>
        <v-divider></v-divider>
        <v-card-text v-if="selectedArchive">
          <v-list density="compact" class="bg-transparent">
            <v-list-item>
              <v-list-item-title class="text-medium-emphasis">分区名称</v-list-item-title>
              <v-list-item-subtitle class="font-weight-medium">{{
                selectedArchive.partition_name
              }}</v-list-item-subtitle>
            </v-list-item>
            <v-list-item>
              <v-list-item-title class="text-medium-emphasis">归档周期</v-list-item-title>
              <v-list-item-subtitle
                >{{ selectedArchive.period_start }} 至
                {{ selectedArchive.period_end }}</v-list-item-subtitle
              >
            </v-list-item>
            <v-list-item>
              <v-list-item-title class="text-medium-emphasis">状态</v-list-item-title>
              <v-list-item-subtitle>
                <v-chip
                  :color="statusColor(selectedArchive.status)"
                  size="small"
                  variant="elevated"
                >
                  {{ selectedArchive.status }}
                </v-chip>
              </v-list-item-subtitle>
            </v-list-item>
            <v-list-item>
              <v-list-item-title class="text-medium-emphasis">总行数</v-list-item-title>
              <v-list-item-subtitle>{{
                formatNumber(selectedArchive.total_rows)
              }}</v-list-item-subtitle>
            </v-list-item>
            <v-list-item>
              <v-list-item-title class="text-medium-emphasis">原始大小</v-list-item-title>
              <v-list-item-subtitle>{{
                formatBytes(selectedArchive.original_bytes)
              }}</v-list-item-subtitle>
            </v-list-item>
            <v-list-item>
              <v-list-item-title class="text-medium-emphasis">压缩后大小</v-list-item-title>
              <v-list-item-subtitle>{{
                formatBytes(selectedArchive.compressed_bytes)
              }}</v-list-item-subtitle>
            </v-list-item>
            <v-list-item
              v-if="selectedArchive.original_bytes > 0 && selectedArchive.compressed_bytes > 0"
            >
              <v-list-item-title class="text-medium-emphasis">压缩率</v-list-item-title>
              <v-list-item-subtitle>
                {{
                  (selectedArchive.original_bytes / selectedArchive.compressed_bytes).toFixed(1)
                }}:1
              </v-list-item-subtitle>
            </v-list-item>
            <v-list-item>
              <v-list-item-title class="text-medium-emphasis">S3 路径</v-list-item-title>
              <v-list-item-subtitle class="text-caption" style="word-break: break-all">
                s3://{{ selectedArchive.s3_bucket }}/{{ selectedArchive.s3_key }}
              </v-list-item-subtitle>
            </v-list-item>
            <v-list-item>
              <v-list-item-title class="text-medium-emphasis">创建时间</v-list-item-title>
              <v-list-item-subtitle>{{
                formatTime(selectedArchive.created_at)
              }}</v-list-item-subtitle>
            </v-list-item>
            <v-list-item v-if="selectedArchive.completed_at">
              <v-list-item-title class="text-medium-emphasis">完成时间</v-list-item-title>
              <v-list-item-subtitle>{{
                formatTime(selectedArchive.completed_at)
              }}</v-list-item-subtitle>
            </v-list-item>
            <v-list-item v-if="selectedArchive.error_message">
              <v-list-item-title class="text-medium-emphasis text-error"
                >错误信息</v-list-item-title
              >
              <v-list-item-subtitle class="text-error">{{
                selectedArchive.error_message
              }}</v-list-item-subtitle>
            </v-list-item>
          </v-list>
        </v-card-text>
      </v-card>
    </v-dialog>
  </PageLayout>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useChatStore } from '@/stores/chat'
import type { ArchiveLog } from '@/apis/chat'
import PageLayout from '@/components/PageLayout.vue'
import { formatTime, formatBytes, formatNumber } from '@/utils/format'

const store = useChatStore()

const currentPage = ref(1)
const archiving = ref(false)
const archiveResult = ref<{ type: 'success' | 'error'; message: string } | null>(null)
const detailDialog = ref(false)
const selectedArchive = ref<ArchiveLog | null>(null)

const headers = [
  { title: '分区', key: 'partition_name', sortable: false },
  { title: '周期', key: 'period_start', sortable: false },
  { title: '状态', key: 'status', sortable: false },
  { title: '行数', key: 'total_rows', sortable: false },
  { title: '压缩后大小', key: 'compressed_bytes', sortable: false },
  { title: '创建时间', key: 'created_at', sortable: false },
  { title: '完成时间', key: 'completed_at', sortable: false },
  { title: '操作', key: 'actions', sortable: false, width: 80 },
]

function statusColor(status: string): string {
  const colors: Record<string, string> = {
    pending: 'grey',
    exporting: 'blue',
    uploading: 'indigo',
    uploaded: 'teal',
    partition_dropped: 'cyan',
    completed: 'green',
    failed: 'red',
  }
  return colors[status] ?? 'grey'
}

function showDetail(archive: ArchiveLog) {
  selectedArchive.value = archive
  detailDialog.value = true
}

async function loadPage(page: number) {
  currentPage.value = page
  await store.loadArchives(page, 20)
}

async function onTriggerArchive() {
  archiving.value = true
  archiveResult.value = null
  try {
    const result = await store.doTriggerArchive()
    archiveResult.value = {
      type: 'success',
      message: `归档任务已提交，任务 ID: ${result.task_id}`,
    }
    // 刷新列表
    setTimeout(() => loadPage(1), 2000)
  } catch {
    archiveResult.value = {
      type: 'error',
      message: '归档任务提交失败',
    }
  } finally {
    archiving.value = false
  }
}

onMounted(() => {
  loadPage(1)
})
</script>
