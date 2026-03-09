<template>
  <v-dialog :model-value="modelValue" max-width="900" @update:model-value="$emit('update:modelValue', $event)">
    <v-card v-if="group">
      <v-card-title class="d-flex align-center ga-3 pa-4">
        <v-icon color="blue" size="36">mdi-account-group</v-icon>
        <div>
          <div class="text-h6">{{ group.group_name || '未知群聊' }}</div>
          <div class="text-caption text-medium-emphasis">
            群号: {{ group.group_id }} · 成员: {{ group.member_count }} / {{ group.max_member_count }}
          </div>
        </div>
        <v-spacer />
        <v-chip :color="group.is_active ? 'success' : 'grey'" variant="tonal" size="small">
          {{ group.is_active ? '活跃' : '已退出' }}
        </v-chip>
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
              variant="outlined"
              hide-details
              clearable
              prepend-inner-icon="mdi-magnify"
              @update:model-value="debouncedLoad"
            />
          </v-col>
          <v-col cols="12" sm="4">
            <v-select
              v-model="filterRole"
              :items="roleOptions"
              label="群内角色"
              density="compact"
              variant="outlined"
              hide-details
              clearable
              @update:model-value="loadMembers(1)"
            />
          </v-col>
        </v-row>
      </v-card-text>

      <!-- 成员表格 -->
      <v-data-table-server
        :headers="headers"
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
          <v-chip :color="roleColor(item.role)" size="x-small" variant="tonal">
            {{ roleLabel(item.role) }}
          </v-chip>
        </template>

        <!-- 系统关系 -->
        <template #[`item.relation`]="{ item }">
          <v-chip :color="relationColor(item.relation)" size="x-small" variant="tonal">
            {{ relationLabel(item.relation) }}
          </v-chip>
        </template>

        <!-- 入群时间 -->
        <template #[`item.join_time`]="{ item }">
          <span class="text-caption">{{ item.join_time ? formatTimestamp(item.join_time) : '-' }}</span>
        </template>
      </v-data-table-server>

      <v-card-actions>
        <v-spacer />
        <v-btn color="red" variant="text" @click="$emit('update:modelValue', false)">关闭</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { usePersonnelStore } from '@/stores/personnel'
import type { GroupItem } from '@/services/personnel'

const props = defineProps<{
  modelValue: boolean
  group: GroupItem | null
}>()

defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const store = usePersonnelStore()

const memberPage = ref(1)
const memberPageSize = ref(20)
const filterRole = ref<string | null>(null)
const filterNickname = ref<string | null>(null)

const roleOptions = [
  { title: '群主', value: 'owner' },
  { title: '管理员', value: 'admin' },
  { title: '成员', value: 'member' },
]

const headers = [
  { title: 'QQ', key: 'qq', sortable: false },
  { title: '昵称', key: 'nickname', sortable: false },
  { title: '群名片', key: 'card', sortable: false },
  { title: '群角色', key: 'role', sortable: false, align: 'center' as const },
  { title: '系统关系', key: 'relation', sortable: false, align: 'center' as const },
  { title: '头衔', key: 'title', sortable: false },
  { title: '入群时间', key: 'join_time', sortable: false },
]

watch(
  () => props.modelValue,
  (open) => {
    if (open && props.group) {
      memberPage.value = 1
      filterRole.value = null
      filterNickname.value = null
      loadMembers(1)
    }
  },
)

let debounceTimer: ReturnType<typeof setTimeout> | null = null
function debouncedLoad() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => loadMembers(1), 400)
}

function loadMembers(p: number) {
  if (!props.group) return
  memberPage.value = p
  store.loadGroupMembers(props.group.group_id, {
    page: p,
    page_size: memberPageSize.value,
    role: filterRole.value,
    nickname: filterNickname.value,
  })
}

function onMemberPageSizeChange(size: number) {
  memberPageSize.value = size
  loadMembers(1)
}

function roleColor(r: string) {
  const map: Record<string, string> = { owner: 'amber', admin: 'blue', member: 'grey' }
  return map[r] ?? 'grey'
}

function roleLabel(r: string) {
  const map: Record<string, string> = { owner: '群主', admin: '管理员', member: '成员' }
  return map[r] ?? r
}

function relationColor(r: string) {
  const map: Record<string, string> = { stranger: 'grey', group_member: 'blue', friend: 'green', admin: 'red' }
  return map[r] ?? 'grey'
}

function relationLabel(r: string) {
  const map: Record<string, string> = { stranger: '陌生人', group_member: '群友', friend: '好友', admin: '管理员' }
  return map[r] ?? r
}

function formatTimestamp(ts: number) {
  if (!ts) return '-'
  try {
    return new Date(ts * 1000).toLocaleString('zh-CN')
  } catch {
    return String(ts)
  }
}
</script>

