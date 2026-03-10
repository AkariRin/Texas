<template>
  <v-container fluid>
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
          variant="solo-filled"
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
          variant="solo-filled"
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
          variant="solo-filled"
          hide-details
          clearable
          style="max-width: 160px"
          @update:model-value="loadPage(1)"
        />
        <v-btn
          variant="elevated"
          color="red"
          prepend-icon="mdi-sync"
          size="small"
          @click="syncDialog = true"
        >
          数据同步
        </v-btn>
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
          <v-chip :color="relationColor(item.relation)" size="small" variant="elevated">
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
          <v-btn icon size="small" variant="elevated" @click="openDetail(item.qq)">
            <v-icon>mdi-eye</v-icon>
            <v-tooltip activator="parent" location="top">查看详情</v-tooltip>
          </v-btn>
        </template>
      </v-data-table-server>
    </v-card>

    <!-- 数据同步弹窗 -->
    <SyncDialog v-model="syncDialog" />

    <!-- 用户详情弹窗 -->
    <v-dialog
      :model-value="detailDialog"
      max-width="700"
      @update:model-value="detailDialog = $event"
    >
      <v-card v-if="detailUser" :loading="detailLoading">
        <v-card-title class="d-flex align-center ga-3 pa-4">
          <v-avatar size="56">
            <v-img :src="`https://q1.qlogo.cn/g?b=qq&nk=${detailUser.qq}&s=100`" />
          </v-avatar>
          <div>
            <div class="text-h6">{{ detailUser.nickname || '未知用户' }}</div>
            <div class="text-caption text-medium-emphasis">QQ: {{ detailUser.qq }}</div>
          </div>
          <v-spacer />
          <v-chip :color="relationColor(detailUser.relation)" variant="elevated">
            <v-icon start size="small">{{ relationIcon(detailUser.relation) }}</v-icon>
            {{ relationLabel(detailUser.relation) }}
          </v-chip>
        </v-card-title>

        <v-divider />

        <v-card-text>
          <v-row dense>
            <v-col cols="6" sm="4">
              <div class="text-caption text-medium-emphasis">所属群数</div>
              <div class="text-body-1 font-weight-medium">{{ detailUser.group_count }}</div>
            </v-col>
            <v-col cols="6" sm="4">
              <div class="text-caption text-medium-emphasis">关系等级</div>
              <div class="text-body-1 font-weight-medium">
                {{ relationLabel(detailUser.relation) }}
              </div>
            </v-col>
            <v-col cols="12" sm="4">
              <div class="text-caption text-medium-emphasis">最后同步</div>
              <div class="text-body-1 font-weight-medium">
                {{ detailUser.last_synced ? formatTime(detailUser.last_synced) : '-' }}
              </div>
            </v-col>
          </v-row>

          <!-- 所属群聊列表 -->
          <div class="text-subtitle-2 mt-4 mb-2">所属群聊</div>
          <v-table v-if="detailGroups.length" density="compact" hover>
            <thead>
              <tr>
                <th>群号</th>
                <th>群名</th>
                <th>成员数</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="g in detailGroups" :key="g.group_id">
                <td>{{ g.group_id }}</td>
                <td>{{ g.group_name }}</td>
                <td>{{ g.member_count }} / {{ g.max_member_count }}</td>
                <td>
                  <v-chip
                    :color="g.is_active ? 'success' : 'grey'"
                    size="x-small"
                    variant="elevated"
                  >
                    {{ g.is_active ? '活跃' : '已退出' }}
                  </v-chip>
                </td>
              </tr>
            </tbody>
          </v-table>
          <v-alert v-else type="info" variant="elevated" density="compact" class="mt-2">
            该用户不在任何群聊中
          </v-alert>
        </v-card-text>

        <v-card-actions>
          <v-spacer />
          <v-btn color="red" variant="elevated" @click="detailDialog = false">关闭</v-btn>
        </v-card-actions>
      </v-card>

      <!-- 加载中 -->
      <v-card v-else>
        <v-card-text class="text-center pa-8">
          <v-progress-circular indeterminate color="red" />
        </v-card-text>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { usePersonnelStore } from '@/stores/personnel'
import type { UserDetail, GroupItem } from '@/apis/personnel'
import SyncDialog from './SyncDialog.vue'

const store = usePersonnelStore()

const page = ref(1)
const pageSize = ref(20)
const filterRelation = ref<string | null>(null)
const filterQQ = ref<string | null>(null)
const filterNickname = ref<string | null>(null)

const syncDialog = ref(false)
const detailDialog = ref(false)
const detailQQ = ref(0)
const detailUser = ref<UserDetail | null>(null)
const detailGroups = ref<GroupItem[]>([])
const detailLoading = ref(false)

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

// 弹窗打开时加载用户详情
watch(detailDialog, async (open) => {
  if (open && detailQQ.value) {
    detailLoading.value = true
    detailUser.value = null
    detailGroups.value = []
    try {
      await Promise.all([store.loadUser(detailQQ.value), store.loadUserGroups(detailQQ.value)])
      detailUser.value = store.currentUser
      detailGroups.value = store.currentUserGroups
    } finally {
      detailLoading.value = false
    }
  } else {
    detailUser.value = null
    detailGroups.value = []
  }
})

onMounted(() => loadPage(1))
</script>
