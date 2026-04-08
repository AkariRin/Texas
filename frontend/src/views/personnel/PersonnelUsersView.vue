<template>
  <PageLayout>
    <v-card flat>
      <v-card-title class="d-flex align-center flex-wrap ga-2">
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
        <v-btn variant="elevated" color="red" prepend-icon="mdi-sync" @click="syncDialog = true">
          数据同步
        </v-btn>
      </v-card-title>

      <v-skeleton-loader
        v-if="store.usersLoading && !store.users.items.length"
        type="table"
        class="pa-2"
      />
      <v-data-table-server
        v-else
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
          <v-btn icon size="small" variant="text" @click="openDetail(item.qq)">
            <v-icon>mdi-eye</v-icon>
            <v-tooltip activator="parent" location="top">查看详情</v-tooltip>
          </v-btn>
        </template>
      </v-data-table-server>
    </v-card>

    <!-- 数据同步弹窗 -->
    <SyncDialog v-model="syncDialog" />

    <!-- 用户详情弹窗 -->
    <UserInfoCard v-model="detailDialog" :qq="detailQQ" @open-group="openGroup" />

    <!-- 群信息弹窗（从用户详情钻取） -->
    <GroupInfoCard
      v-model="groupDialog"
      :group-id="groupIdToOpen"
      @open-user="openMemberFromGroup"
    />

    <!-- 群成员详情弹窗（从群信息钻取） -->
    <UserInfoCard
      v-model="memberFromGroupDialog"
      :qq="memberFromGroupQQ"
      :group-id="memberGroupId"
    />
  </PageLayout>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { usePersonnelStore } from '@/stores/personnel'
import SyncDialog from './SyncDialog.vue'
import PageLayout from '@/layouts/PageLayout.vue'
import UserInfoCard from '@/components/UserInfoCard.vue'
import GroupInfoCard from '@/components/GroupInfoCard.vue'
import { formatTime } from '@/utils/format'
import { relationColor, relationLabel, relationIcon } from '@/utils/personnel'
import { debounce } from '@/utils/ui'

const store = usePersonnelStore()

const page = ref(1)
const pageSize = ref(20)
const filterRelation = ref<string | null>(null)
const filterQQ = ref<string | null>(null)
const filterNickname = ref<string | null>(null)

const syncDialog = ref(false)

// 用户详情弹窗
const detailDialog = ref(false)
const detailQQ = ref<number | null>(null)

// 群信息弹窗（从用户详情钻取）
const groupDialog = ref(false)
const groupIdToOpen = ref<number | null>(null)

// 群成员弹窗（从群信息钻取）
const memberFromGroupDialog = ref(false)
const memberFromGroupQQ = ref<number | null>(null)
const memberGroupId = ref<number | null>(null)

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

const debouncedLoad = debounce(() => loadPage(1))

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

function openGroup(groupId: number) {
  groupIdToOpen.value = groupId
  groupDialog.value = true
}

function openMemberFromGroup(qq: number, groupId: number) {
  memberFromGroupQQ.value = qq
  memberGroupId.value = groupId
  memberFromGroupDialog.value = true
}

onMounted(() => loadPage(1))
</script>
