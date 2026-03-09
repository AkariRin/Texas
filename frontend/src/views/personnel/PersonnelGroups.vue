<template>
  <v-container fluid>
    <v-card flat>
      <v-card-title class="d-flex align-center flex-wrap ga-2">
        <v-icon start>mdi-forum</v-icon>
        <span>群聊列表</span>
        <v-spacer />
        <v-text-field
          v-model="filterName"
          label="群名搜索"
          density="compact"
          variant="outlined"
          hide-details
          clearable
          prepend-inner-icon="mdi-magnify"
          style="max-width: 220px"
          @update:model-value="debouncedLoad"
        />
        <v-select
          v-model="filterActive"
          :items="activeOptions"
          label="状态"
          density="compact"
          variant="outlined"
          hide-details
          clearable
          style="max-width: 140px"
          @update:model-value="loadPage(1)"
        />
      </v-card-title>

      <v-data-table-server
        :headers="headers"
        :items="store.groups.items"
        :items-length="store.groups.total"
        :loading="store.groupsLoading"
        :page="page"
        :items-per-page="pageSize"
        :items-per-page-options="[10, 20, 50]"
        hover
        @update:page="loadPage"
        @update:items-per-page="onPageSizeChange"
      >
        <!-- 群号列 -->
        <template #[`item.group_id`]="{ item }">
          <div class="d-flex align-center ga-2">
            <v-avatar size="32">
              <v-img :src="`https://p.qlogo.cn/gh/${item.group_id}/${item.group_id}/100`" />
            </v-avatar>
            <span class="font-weight-medium">{{ item.group_id }}</span>
          </div>
        </template>

        <!-- 成员数 -->
        <template #[`item.member_count`]="{ item }">
          <span>{{ item.member_count }} / {{ item.max_member_count }}</span>
        </template>

        <!-- 状态 -->
        <template #[`item.is_active`]="{ item }">
          <v-chip :color="item.is_active ? 'success' : 'grey'" size="small" variant="tonal">
            <v-icon start size="x-small">{{ item.is_active ? 'mdi-check-circle' : 'mdi-close-circle' }}</v-icon>
            {{ item.is_active ? '活跃' : '已退出' }}
          </v-chip>
        </template>

        <!-- 最后同步 -->
        <template #[`item.last_synced`]="{ item }">
          <span class="text-caption text-medium-emphasis">
            {{ item.last_synced ? formatTime(item.last_synced) : '-' }}
          </span>
        </template>

        <!-- 操作列 -->
        <template #[`item.actions`]="{ item }">
          <v-btn icon size="small" variant="text" @click="openMembers(item)">
            <v-icon>mdi-account-multiple</v-icon>
            <v-tooltip activator="parent" location="top">查看成员</v-tooltip>
          </v-btn>
        </template>
      </v-data-table-server>
    </v-card>

    <!-- 群成员弹窗 -->
    <group-detail-dialog v-model="memberDialog" :group="selectedGroup" />
  </v-container>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { usePersonnelStore } from '@/stores/personnel'
import GroupDetailDialog from './GroupDetailDialog.vue'
import type { GroupItem } from '@/services/personnel'

const store = usePersonnelStore()

const page = ref(1)
const pageSize = ref(20)
const filterName = ref<string | null>(null)
const filterActive = ref<boolean | null>(null)

const memberDialog = ref(false)
const selectedGroup = ref<GroupItem | null>(null)

const activeOptions = [
  { title: '活跃', value: true },
  { title: '已退出', value: false },
]

const headers = [
  { title: '群号', key: 'group_id', sortable: false },
  { title: '群名', key: 'group_name', sortable: false },
  { title: '成员数', key: 'member_count', sortable: false, align: 'center' as const },
  { title: '状态', key: 'is_active', sortable: false, align: 'center' as const },
  { title: '最后同步', key: 'last_synced', sortable: false },
  { title: '操作', key: 'actions', sortable: false, align: 'center' as const },
]

function formatTime(iso: string) {
  try {
    return new Date(iso).toLocaleString('zh-CN')
  } catch {
    return iso
  }
}

let debounceTimer: ReturnType<typeof setTimeout> | null = null
function debouncedLoad() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => loadPage(1), 400)
}

function loadPage(p: number) {
  page.value = p
  store.loadGroups({
    page: p,
    page_size: pageSize.value,
    group_name: filterName.value,
    is_active: filterActive.value,
  })
}

function onPageSizeChange(size: number) {
  pageSize.value = size
  loadPage(1)
}

function openMembers(group: GroupItem) {
  selectedGroup.value = group
  memberDialog.value = true
}

onMounted(() => loadPage(1))
</script>

