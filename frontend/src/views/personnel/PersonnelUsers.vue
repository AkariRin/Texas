<template>
  <v-card flat>
    <v-card-title class="d-flex align-center flex-wrap ga-2">
      <v-icon start>mdi-account-group</v-icon>
      <span>用户列表</span>
      <v-spacer />
      <!-- 筛选栏 -->
      <v-text-field
        v-model="filterNickname"
        label="昵称搜索"
        density="compact"
        variant="outlined"
        hide-details
        clearable
        prepend-inner-icon="mdi-magnify"
        style="max-width: 200px"
        @update:model-value="debouncedLoad"
      />
      <v-text-field
        v-model="filterQQ"
        label="QQ 号"
        density="compact"
        variant="outlined"
        hide-details
        clearable
        prepend-inner-icon="mdi-identifier"
        style="max-width: 180px"
        @update:model-value="debouncedLoad"
      />
      <v-select
        v-model="filterRelation"
        :items="relationOptions"
        label="关系等级"
        density="compact"
        variant="outlined"
        hide-details
        clearable
        style="max-width: 160px"
        @update:model-value="loadPage(1)"
      />
    </v-card-title>

    <v-data-table-server
      :headers="headers"
      :items="store.users.items"
      :items-length="store.users.total"
      :loading="store.usersLoading"
      :page="page"
      :items-per-page="pageSize"
      :items-per-page-options="[10, 20, 50]"
      hover
      @update:page="loadPage"
      @update:items-per-page="onPageSizeChange"
    >
      <!-- QQ 号列：头像 + QQ -->
      <template #[`item.qq`]="{ item }">
        <div class="d-flex align-center ga-2">
          <v-avatar size="32">
            <v-img :src="`https://q1.qlogo.cn/g?b=qq&nk=${item.qq}&s=40`" />
          </v-avatar>
          <span class="font-weight-medium">{{ item.qq }}</span>
        </div>
      </template>

      <!-- 关系等级列 -->
      <template #[`item.relation`]="{ item }">
        <v-chip :color="relationColor(item.relation)" size="small" variant="tonal">
          <v-icon start size="x-small">{{ relationIcon(item.relation) }}</v-icon>
          {{ relationLabel(item.relation) }}
        </v-chip>
      </template>

      <!-- 最后同步时间 -->
      <template #[`item.last_synced`]="{ item }">
        <span class="text-caption text-medium-emphasis">
          {{ item.last_synced ? formatTime(item.last_synced) : '-' }}
        </span>
      </template>

      <!-- 操作列 -->
      <template #[`item.actions`]="{ item }">
        <v-btn icon size="small" variant="text" @click="openDetail(item.qq)">
          <v-icon>mdi-eye</v-icon>
          <v-tooltip activator="parent" location="top">查看详情</v-tooltip>
        </v-btn>
      </template>
    </v-data-table-server>
  </v-card>

  <!-- 用户详情弹窗 -->
  <user-detail-dialog v-model="detailDialog" :qq="detailQQ" />
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { usePersonnelStore } from '@/stores/personnel'
import UserDetailDialog from './UserDetailDialog.vue'

const store = usePersonnelStore()

const page = ref(1)
const pageSize = ref(20)
const filterRelation = ref<string | null>(null)
const filterQQ = ref<string | null>(null)
const filterNickname = ref<string | null>(null)

const detailDialog = ref(false)
const detailQQ = ref(0)

const relationOptions = [
  { title: '陌生人', value: 'stranger' },
  { title: '群友', value: 'group_member' },
  { title: '好友', value: 'friend' },
  { title: '管理员', value: 'admin' },
]

const headers = [
  { title: 'QQ', key: 'qq', sortable: false },
  { title: '昵称', key: 'nickname', sortable: false },
  { title: '关系等级', key: 'relation', sortable: false },
  { title: '所属群数', key: 'group_count', sortable: false, align: 'center' as const },
  { title: '最后同步', key: 'last_synced', sortable: false },
  { title: '操作', key: 'actions', sortable: false, align: 'center' as const },
]

function relationColor(r: string) {
  const map: Record<string, string> = {
    stranger: 'grey',
    group_member: 'blue',
    friend: 'green',
    admin: 'red',
  }
  return map[r] ?? 'grey'
}

function relationIcon(r: string) {
  const map: Record<string, string> = {
    stranger: 'mdi-account-outline',
    group_member: 'mdi-account-multiple',
    friend: 'mdi-account-heart',
    admin: 'mdi-shield-account',
  }
  return map[r] ?? 'mdi-account'
}

function relationLabel(r: string) {
  const map: Record<string, string> = {
    stranger: '陌生人',
    group_member: '群友',
    friend: '好友',
    admin: '管理员',
  }
  return map[r] ?? r
}

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
  store.loadUsers({
    page: p,
    page_size: pageSize.value,
    relation: filterRelation.value,
    qq: filterQQ.value ? Number(filterQQ.value) : null,
    nickname: filterNickname.value,
  })
}

function onPageSizeChange(size: number) {
  pageSize.value = size
  loadPage(1)
}

function openDetail(qq: number) {
  detailQQ.value = qq
  detailDialog.value = true
}

onMounted(() => loadPage(1))
</script>

