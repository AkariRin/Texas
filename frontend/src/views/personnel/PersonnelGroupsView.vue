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

      <v-skeleton-loader
        v-if="store.groupsLoading && !store.groups.items.length"
        type="table"
        class="pa-2"
      />
      <v-data-table-server
        v-else
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
          <v-chip :color="activeColor(item.is_active)" size="small" variant="elevated">
            <v-icon start size="x-small">{{
              item.is_active ? 'mdi-check-circle' : 'mdi-close-circle'
            }}</v-icon>
            {{ activeLabel(item.is_active) }}
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
    <GroupInfoCard
      v-model="memberDialog"
      :group-id="selectedGroupId"
      :group="selectedGroup"
      @open-user="openMemberDetail"
    />

    <!-- 成员详情弹窗（从群成员列表钻取） -->
    <UserInfoCard v-model="memberDetailDialog" :qq="memberDetailQQ" :group-id="selectedGroupId" />
  </PageLayout>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { usePersonnelStore } from '@/stores/personnel'
import type { GroupItem } from '@/apis/personnel'
import SyncDialog from './SyncDialog.vue'
import PageLayout from '@/layouts/PageLayout.vue'
import GroupInfoCard from '@/components/GroupInfoCard.vue'
import UserInfoCard from '@/components/UserInfoCard.vue'
import { formatTime } from '@/utils/format'
import { activeColor, activeLabel } from '@/utils/personnel'
import { usePagination } from '@/composables/usePagination'

const store = usePersonnelStore()

const filterName = ref<string | null>(null)
const filterActive = ref<boolean | null>(null)

const syncDialog = ref(false)

// 群成员弹窗
const memberDialog = ref(false)
const selectedGroup = ref<GroupItem | null>(null)
const selectedGroupId = ref<number | null>(null)

// 成员详情弹窗（从群成员列表钻取）
const memberDetailDialog = ref(false)
const memberDetailQQ = ref<number | null>(null)

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

const { page, pageSize, loadPage, onPageSizeChange, debouncedLoad } = usePagination((p, size) =>
  store.loadGroups({
    page: p,
    page_size: size,
    group_name: filterName.value,
    is_active: filterActive.value,
  }),
)

function openMembers(group: GroupItem) {
  selectedGroup.value = group
  selectedGroupId.value = group.group_id
  memberDialog.value = true
}

function openMemberDetail(qq: number, groupId: number) {
  memberDetailQQ.value = qq
  selectedGroupId.value = groupId
  memberDetailDialog.value = true
}

onMounted(() => loadPage(1))
</script>
