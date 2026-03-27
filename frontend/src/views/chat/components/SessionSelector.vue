<template>
  <div class="group-selector d-flex flex-column" style="height: 100%">
    <!-- 搜索栏 -->
    <div class="pa-2">
      <v-text-field
        v-model="searchQuery"
        density="compact"
        variant="solo-filled"
        placeholder="搜索群聊 / 用户..."
        prepend-inner-icon="mdi-magnify"
        hide-details
        clearable
      ></v-text-field>
    </div>

    <!-- 标签切换 -->
    <v-tabs v-model="tab" density="compact" grow color="primary">
      <v-tab value="groups">
        <v-icon start>mdi-account-group</v-icon>
        群聊
      </v-tab>
      <v-tab value="private">
        <v-icon start>mdi-account</v-icon>
        私聊
      </v-tab>
    </v-tabs>

    <v-divider></v-divider>

    <!-- 列表 -->
    <v-list
      density="compact"
      nav
      class="flex-grow-1 overflow-y-auto selector-list"
      style="min-height: 0"
    >
      <template v-if="tab === 'groups'">
        <v-list-item
          v-for="group in filteredGroups"
          :key="group.group_id"
          :active="activeType === 'group' && activeId === group.group_id"
          rounded="lg"
          @click="emit('select', 'group', group.group_id, group.group_name)"
        >
          <template #prepend>
            <v-avatar size="32">
              <v-img :src="`https://p.qlogo.cn/gh/${group.group_id}/${group.group_id}/100`">
                <template #error>
                  <v-icon>mdi-account-group</v-icon>
                </template>
              </v-img>
            </v-avatar>
          </template>
          <v-list-item-title class="text-body-2">{{ group.group_name }}</v-list-item-title>
          <v-list-item-subtitle class="text-caption">
            {{ group.group_id }} &middot; {{ group.member_count }} 人
          </v-list-item-subtitle>
        </v-list-item>
        <v-list-item v-if="filteredGroups.length === 0">
          <v-list-item-title class="text-medium-emphasis text-center text-caption">
            {{ searchQuery ? '无匹配结果' : '暂无群聊数据' }}
          </v-list-item-title>
        </v-list-item>
      </template>

      <template v-else>
        <v-list-item
          v-for="user in filteredUsers"
          :key="user.qq"
          :active="activeType === 'private' && activeId === user.qq"
          rounded="lg"
          @click="emit('select', 'private', user.qq, user.nickname)"
        >
          <template #prepend>
            <v-avatar size="32">
              <v-img :src="`https://q1.qlogo.cn/g?b=qq&nk=${user.qq}&s=100`">
                <template #error>
                  <v-icon>mdi-account</v-icon>
                </template>
              </v-img>
            </v-avatar>
          </template>
          <v-list-item-title class="text-body-2">{{ user.nickname }}</v-list-item-title>
          <v-list-item-subtitle class="text-caption">{{ user.qq }}</v-list-item-subtitle>
        </v-list-item>
        <v-list-item v-if="filteredUsers.length === 0">
          <v-list-item-title class="text-medium-emphasis text-center text-caption">
            {{ searchQuery ? '无匹配结果' : '暂无私聊数据' }}
          </v-list-item-title>
        </v-list-item>
      </template>
    </v-list>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { fetchGroups, fetchUsers } from '@/apis/personnel'
import type { GroupItem, UserItem } from '@/apis/personnel'

defineProps<{
  activeType: 'group' | 'private' | null
  activeId: number | null
}>()

const emit = defineEmits<{
  select: [type: 'group' | 'private', id: number, name: string]
}>()

const searchQuery = ref('')
const tab = ref('groups')
const groups = ref<GroupItem[]>([])
const users = ref<UserItem[]>([])

const filteredGroups = computed(() => {
  if (!searchQuery.value) return groups.value
  const q = searchQuery.value.toLowerCase()
  return groups.value.filter(
    (g) => g.group_name.toLowerCase().includes(q) || String(g.group_id).includes(q),
  )
})

const filteredUsers = computed(() => {
  if (!searchQuery.value) return users.value
  const q = searchQuery.value.toLowerCase()
  return users.value.filter(
    (u) => u.nickname.toLowerCase().includes(q) || String(u.qq).includes(q),
  )
})

async function loadData() {
  try {
    const [groupResult, userResult] = await Promise.all([
      fetchGroups({ page: 1, page_size: 100 }),
      fetchUsers({ page: 1, page_size: 100, relation: 'friend' }),
    ])
    groups.value = groupResult.items
    users.value = userResult.items
  } catch {
    // 静默失败
  }
}

onMounted(loadData)
</script>

<style scoped>
.group-selector :deep(.v-tabs) {
  flex: none;
}

.group-selector :deep(.v-tabs .v-window) {
  display: none;
}

.selector-list {
  padding-top: 4px !important;
  padding-bottom: 0 !important;
}
</style>
