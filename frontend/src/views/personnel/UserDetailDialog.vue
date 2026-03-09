<template>
  <v-dialog :model-value="modelValue" max-width="700" @update:model-value="$emit('update:modelValue', $event)">
    <v-card v-if="user" :loading="loading">
      <v-card-title class="d-flex align-center ga-3 pa-4">
        <v-avatar size="56">
          <v-img :src="`https://q1.qlogo.cn/g?b=qq&nk=${user.qq}&s=100`" />
        </v-avatar>
        <div>
          <div class="text-h6">{{ user.nickname || '未知用户' }}</div>
          <div class="text-caption text-medium-emphasis">QQ: {{ user.qq }}</div>
        </div>
        <v-spacer />
        <v-chip :color="relationColor(user.relation)" variant="tonal">
          <v-icon start size="small">{{ relationIcon(user.relation) }}</v-icon>
          {{ relationLabel(user.relation) }}
        </v-chip>
      </v-card-title>

      <v-divider />

      <v-card-text>
        <v-row dense>
          <v-col cols="6" sm="4">
            <div class="text-caption text-medium-emphasis">所属群数</div>
            <div class="text-body-1 font-weight-medium">{{ user.group_count }}</div>
          </v-col>
          <v-col cols="6" sm="4">
            <div class="text-caption text-medium-emphasis">关系等级</div>
            <div class="text-body-1 font-weight-medium">{{ relationLabel(user.relation) }}</div>
          </v-col>
          <v-col cols="12" sm="4">
            <div class="text-caption text-medium-emphasis">最后同步</div>
            <div class="text-body-1 font-weight-medium">
              {{ user.last_synced ? formatTime(user.last_synced) : '-' }}
            </div>
          </v-col>
        </v-row>

        <!-- 所属群聊列表 -->
        <div class="text-subtitle-2 mt-4 mb-2">所属群聊</div>
        <v-table v-if="groups.length" density="compact" hover>
          <thead>
            <tr>
              <th>群号</th>
              <th>群名</th>
              <th>成员数</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="g in groups" :key="g.group_id">
              <td>{{ g.group_id }}</td>
              <td>{{ g.group_name }}</td>
              <td>{{ g.member_count }} / {{ g.max_member_count }}</td>
              <td>
                <v-chip :color="g.is_active ? 'success' : 'grey'" size="x-small" variant="tonal">
                  {{ g.is_active ? '活跃' : '已退出' }}
                </v-chip>
              </td>
            </tr>
          </tbody>
        </v-table>
        <v-alert v-else type="info" variant="tonal" density="compact" class="mt-2">
          该用户不在任何群聊中
        </v-alert>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn color="red" variant="text" @click="$emit('update:modelValue', false)">关闭</v-btn>
      </v-card-actions>
    </v-card>

    <!-- 加载中 -->
    <v-card v-else>
      <v-card-text class="text-center pa-8">
        <v-progress-circular indeterminate color="red" />
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { usePersonnelStore } from '@/stores/personnel'
import type { UserDetail, GroupItem } from '@/services/personnel'

const props = defineProps<{
  modelValue: boolean
  qq: number
}>()

defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const store = usePersonnelStore()
const user = ref<UserDetail | null>(null)
const groups = ref<GroupItem[]>([])
const loading = ref(false)

watch(
  () => props.modelValue,
  async (open) => {
    if (open && props.qq) {
      loading.value = true
      try {
        await Promise.all([store.loadUser(props.qq), store.loadUserGroups(props.qq)])
        user.value = store.currentUser
        groups.value = store.currentUserGroups
      } finally {
        loading.value = false
      }
    } else {
      user.value = null
      groups.value = []
    }
  },
)

function relationColor(r: string) {
  const map: Record<string, string> = { stranger: 'grey', group_member: 'blue', friend: 'green', admin: 'red' }
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
  const map: Record<string, string> = { stranger: '陌生人', group_member: '群友', friend: '好友', admin: '管理员' }
  return map[r] ?? r
}

function formatTime(iso: string) {
  try {
    return new Date(iso).toLocaleString('zh-CN')
  } catch {
    return iso
  }
}
</script>

