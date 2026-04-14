<template>
  <v-dialog
    :model-value="modelValue"
    max-width="900"
    scrollable
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <v-card>
      <!-- 加载中头部骨架 -->
      <v-card-title v-if="headerLoading" class="pa-4">
        <v-skeleton-loader type="list-item-avatar-two-line" />
      </v-card-title>

      <!-- 群信息头部 -->
      <v-card-title v-else-if="groupInfo" class="d-flex align-center ga-3 pa-4">
        <v-avatar size="48" rounded="lg">
          <v-img :src="`https://p.qlogo.cn/gh/${groupInfo.group_id}/${groupInfo.group_id}/100`">
            <template #error>
              <v-icon size="32">mdi-account-group</v-icon>
            </template>
          </v-img>
        </v-avatar>
        <div>
          <div class="text-h6">{{ groupInfo.group_name || '未知群聊' }}</div>
          <div class="text-caption text-medium-emphasis">
            群号: {{ groupInfo.group_id }} &middot; 成员: {{ groupInfo.member_count }} /
            {{ groupInfo.max_member_count }}
          </div>
        </div>
        <v-spacer />
        <v-chip :color="activeColor(groupInfo.is_active)" variant="elevated" size="small">
          {{ activeLabel(groupInfo.is_active) }}
        </v-chip>
        <v-btn
          icon="mdi-close"
          size="small"
          variant="text"
          @click="$emit('update:modelValue', false)"
        />
      </v-card-title>

      <v-divider />

      <!-- 成员筛选 -->
      <v-card-text class="pb-0">
        <v-row dense>
          <v-col cols="12" sm="5">
            <v-text-field
              v-model="filterNickname"
              label="搜索昵称 / 群名片"
              density="compact"
              variant="solo-filled"
              hide-details
              clearable
              prepend-inner-icon="mdi-magnify"
              @update:model-value="debouncedLoadMembers"
            />
          </v-col>
          <v-col cols="12" sm="4">
            <v-select
              v-model="filterRole"
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
        @update:items-per-page="onPageSizeChange"
      >
        <!-- QQ 头像 -->
        <template #[`item.qq`]="{ item }">
          <div class="d-flex align-center ga-2">
            <v-avatar size="28">
              <v-img :src="`https://q1.qlogo.cn/g?b=qq&nk=${item.qq}&s=40`" />
            </v-avatar>
            <span class="cursor-pointer text-primary" @click="onMemberClick(item.qq)">
              {{ item.qq }}
            </span>
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
          <span class="text-caption">
            {{ item.join_time ? formatTimestamp(item.join_time) : '-' }}
          </span>
        </template>

        <!-- 昵称（可点击） -->
        <template #[`item.nickname`]="{ item }">
          <span class="cursor-pointer text-primary" @click="onMemberClick(item.qq)">
            {{ item.nickname }}
          </span>
        </template>
      </v-data-table-server>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
/**
 * 群聊信息卡片组件 —— 展示群基本信息及可筛选分页的成员列表。
 *
 * 成员行点击触发 open-user 事件，父组件可据此打开 UserInfoCard 群成员变体实现钻取。
 * 注意：成员数据复用 personnelStore.groupMembers 共享状态，依赖模态弹窗保证同时只有一个实例。
 */
import { ref, watch } from 'vue'
import { usePersonnelStore } from '@/stores/personnel'
import type { GroupItem } from '@/apis/personnel'
import { formatTimestamp } from '@/utils/format'
import {
  activeColor,
  activeLabel,
  relationColor,
  relationLabel,
  roleColor,
  roleLabel,
  roleOptions,
} from '@/utils/personnel'
import { debounce } from '@/utils/ui'

const props = defineProps<{
  modelValue: boolean
  groupId: number | null
  group?: GroupItem | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'open-user': [qq: number, groupId: number]
}>()

const store = usePersonnelStore()

const headerLoading = ref(false)
const groupInfo = ref<GroupItem | null>(null)

const memberPage = ref(1)
const memberPageSize = ref(20)
const filterRole = ref<string | null>(null)
const filterNickname = ref<string | null>(null)

const memberHeaders = [
  { title: 'QQ', key: 'qq', sortable: false },
  { title: '昵称', key: 'nickname', sortable: false },
  { title: '群名片', key: 'card', sortable: false },
  { title: '群角色', key: 'role', sortable: false, align: 'center' as const },
  { title: '系统关系', key: 'relation', sortable: false, align: 'center' as const },
  { title: '头衔', key: 'title', sortable: false },
  { title: '入群时间', key: 'join_time', sortable: false },
]

const debouncedLoadMembers = debounce(() => loadMembers(1))

watch(
  () => [props.modelValue, props.groupId] as const,
  async ([open, groupId]) => {
    if (!open || !groupId) {
      groupInfo.value = null
      return
    }

    // 重置分页和筛选
    memberPage.value = 1
    memberPageSize.value = 20
    filterRole.value = null
    filterNickname.value = null

    // 加载群头部信息
    if (props.group) {
      groupInfo.value = props.group
    } else {
      headerLoading.value = true
      try {
        groupInfo.value = await store.fetchGroupDetail(groupId)
      } finally {
        headerLoading.value = false
      }
    }

    loadMembers(1)
  },
  { immediate: false },
)

// 当 group prop 更新时同步到 groupInfo（父组件可能在打开后更新）
watch(
  () => props.group,
  (g) => {
    if (g && props.modelValue) groupInfo.value = g
  },
)

function loadMembers(page: number) {
  if (!props.groupId) return
  memberPage.value = page
  store.loadGroupMembers(props.groupId, {
    page,
    page_size: memberPageSize.value,
    role: filterRole.value,
    nickname: filterNickname.value,
  })
}

function onPageSizeChange(size: number) {
  memberPageSize.value = size
  loadMembers(1)
}

function onMemberClick(qq: number) {
  if (props.groupId) emit('open-user', qq, props.groupId)
}
</script>
