<template>
  <v-container fluid class="pa-6">
    <div class="d-flex align-center mb-6">
      <div>
        <h1 class="text-h4 font-weight-bold">归档管理</h1>
        <p class="text-body-2 text-medium-emphasis mt-1">查看和管理聊天记录归档</p>
      </div>
      <v-spacer></v-spacer>
      <v-btn
        variant="tonal"
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
    </div>

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
          <v-chip :color="statusColor(item.status)" size="small" variant="flat">
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
            variant="text"
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
    <ArchiveDetailDialog v-model="detailDialog" :archive="selectedArchive" />
  </v-container>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useChatStore } from '@/stores/chat'
import type { ArchiveLog } from '@/services/chat'
import ArchiveDetailDialog from './ArchiveDetailDialog.vue'

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

function formatNumber(n: number): string {
  return n.toLocaleString()
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + units[i]
}

function formatTime(iso: string | null): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN')
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

