<template>
  <PageLayout>
    <v-card flat>
      <v-card-title class="d-flex align-center flex-wrap ga-2">
        <v-text-field
          v-model="filterName"
          label="群名搜索"
          density="compact"
          variant="solo-filled"
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
          variant="solo-filled"
          hide-details
          clearable
          style="max-width: 140px"
          @update:model-value="loadPage(1)"
        />
        <v-btn variant="elevated" color="red" prepend-icon="mdi-sync" @click="syncDialog = true">
          数据同步
        </v-btn>
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
          <v-chip :color="item.is_active ? 'success' : 'grey'" size="small" variant="elevated">
            <v-icon start size="x-small">{{
              item.is_active ? 'mdi-check-circle' : 'mdi-close-circle'
            }}</v-icon>
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

    <!-- 数据同步弹窗 -->
    <SyncDialog v-model="syncDialog" />

    <!-- 群成员弹窗 -->
    <v-dialog
      :model-value="memberDialog"
      max-width="900"
      @update:model-value="memberDialog = $event"
    >
      <v-card v-if="selectedGroup">
        <v-card-title class="d-flex align-center ga-3 pa-4">
          <v-icon color="blue" size="36">mdi-account-group</v-icon>
          <div>
            <div class="text-h6">{{ selectedGroup.group_name || '未知群聊' }}</div>
            <div class="text-caption text-medium-emphasis">
              群号: {{ selectedGroup.group_id }} &middot; 成员: {{ selectedGroup.member_count }} /
              {{ selectedGroup.max_member_count }}
            </div>
          </div>
          <v-spacer />
          <v-chip
            :color="selectedGroup.is_active ? 'success' : 'grey'"
            variant="elevated"
            size="small"
          >
            {{ selectedGroup.is_active ? '活跃' : '已退出' }}
          </v-chip>
        </v-card-title>

        <v-divider />

        <!-- 成员筛选 -->
        <v-card-text class="pb-0">
          <v-row dense>
            <v-col cols="12" sm="5">
              <v-text-field
                v-model="memberFilterNickname"
                label="搜索昵称 / 群名片"
                density="compact"
                variant="solo-filled"
                hide-details
                clearable
                prepend-inner-icon="mdi-magnify"
                @update:model-value="debouncedMemberLoad"
              />
            </v-col>
            <v-col cols="12" sm="4">
              <v-select
                v-model="memberFilterRole"
                :items="roleOptions"
                label="群内角色"
                density="compact"
                variant="solo-filled"
                hide-details
                clearable
                @update:model-value="loadMembers(1)"
              />
            </v-col>
          </v-row>
        </v-card-text>

        <!-- 成员表格 -->
        <v-data-table-server
          :headers="memberHeaders"
          :items="store.groupMembers.items"
          :items-length="store.groupMembers.total"
          :loading="store.membersLoading"
          :page="memberPage"
          :items-per-page="memberPageSize"
          :items-per-page-options="[10, 20, 50]"
          density="compact"
          hover
          @update:page="loadMembers"
          @update:items-per-page="onMemberPageSizeChange"
        >
          <!-- QQ 头像 -->
          <template #[`item.qq`]="{ item }">
            <div class="d-flex align-center ga-2">
              <v-avatar size="28">
                <v-img :src="`https://q1.qlogo.cn/g?b=qq&nk=${item.qq}&s=40`" />
              </v-avatar>
              <span>{{ item.qq }}</span>
            </div>
          </template>

          <!-- 群内角色 -->
          <template #[`item.role`]="{ item }">
            <v-chip :color="roleColor(item.role)" size="x-small" variant="elevated">
              {{ roleLabel(item.role) }}
            </v-chip>
          </template>

          <!-- 系统关系 -->
          <template #[`item.relation`]="{ item }">
            <v-chip :color="relationColor(item.relation)" size="x-small" variant="elevated">
              {{ relationLabel(item.relation) }}
            </v-chip>
          </template>

          <!-- 入群时间 -->
          <template #[`item.join_time`]="{ item }">
            <span class="text-caption">{{
              item.join_time ? formatTimestamp(item.join_time) : '-'
            }}</span>
          </template>
        </v-data-table-server>

        <v-card-actions>
          <v-spacer />
          <v-btn color="red" variant="elevated" @click="memberDialog = false">关闭</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </PageLayout>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { usePersonnelStore } from '@/stores/personnel'
import type { GroupItem } from '@/apis/personnel'
import SyncDialog from './SyncDialog.vue'
import PageLayout from '@/components/PageLayout.vue'
import { formatTime, formatTimestamp } from '@/utils/format'
import { relationColor, relationLabel, roleColor, roleLabel } from '@/utils/personnel'
import { debounce } from '@/utils/ui'

const store = usePersonnelStore()

const page = ref(1)
const pageSize = ref(20)
const filterName = ref<string | null>(null)
const filterActive = ref<boolean | null>(null)

const syncDialog = ref(false)
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

// ── 群成员弹窗状态 ──

const memberPage = ref(1)
const memberPageSize = ref(20)
const memberFilterRole = ref<string | null>(null)
const memberFilterNickname = ref<string | null>(null)

const roleOptions = [
  { title: '群主', value: 'owner' },
  { title: '管理员', value: 'admin' },
  { title: '成员', value: 'member' },
]

const memberHeaders = [
  { title: 'QQ', key: 'qq', sortable: false },
  { title: '昵称', key: 'nickname', sortable: false },
  { title: '群名片', key: 'card', sortable: false },
  { title: '群角色', key: 'role', sortable: false, align: 'center' as const },
  { title: '系统关系', key: 'relation', sortable: false, align: 'center' as const },
  { title: '头衔', key: 'title', sortable: false },
  { title: '入群时间', key: 'join_time', sortable: false },
]

watch(memberDialog, (open) => {
  if (open && selectedGroup.value) {
    memberPage.value = 1
    memberFilterRole.value = null
    memberFilterNickname.value = null
    loadMembers(1)
  }
})

// ── 辅助函数 ──

// ── 群列表操作 ──

const debouncedLoad = debounce(() => loadPage(1))

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

// ── 成员列表操作 ──

const debouncedMemberLoad = debounce(() => loadMembers(1))

function loadMembers(p: number) {
  if (!selectedGroup.value) return
  memberPage.value = p
  store.loadGroupMembers(selectedGroup.value.group_id, {
    page: p,
    page_size: memberPageSize.value,
    role: memberFilterRole.value,
    nickname: memberFilterNickname.value,
  })
}

function onMemberPageSizeChange(size: number) {
  memberPageSize.value = size
  loadMembers(1)
}

onMounted(() => loadPage(1))
</script>
