<template>
  <v-dialog
    :model-value="modelValue"
    max-width="700"
    scrollable
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <!-- 加载中骨架 -->
    <v-card v-if="loading">
      <v-card-text class="pa-4">
        <v-skeleton-loader type="list-item-avatar-three-line, divider, article, table-row" />
      </v-card-text>
    </v-card>

    <!-- 群成员变体 -->
    <v-card v-else-if="isGroupVariant" rounded="lg">
      <v-card-title class="d-flex align-center">
        <v-icon class="mr-2" size="small">mdi-account-details</v-icon>
        群成员详情
        <v-spacer />
        <v-btn
          icon="mdi-close"
          size="small"
          variant="text"
          @click="$emit('update:modelValue', false)"
        />
      </v-card-title>
      <v-divider />
      <v-card-text class="pa-0">
        <!-- 未找到 -->
        <div
          v-if="!memberData"
          class="d-flex flex-column align-center justify-center pa-8 text-medium-emphasis"
        >
          <v-icon size="48" color="grey-lighten-1">mdi-account-off-outline</v-icon>
          <p class="mt-2 text-body-2">未找到该成员信息</p>
        </div>

        <!-- 成员信息 -->
        <template v-else>
          <div class="d-flex align-center ga-4 pa-4">
            <v-avatar size="64">
              <v-img :src="`https://q1.qlogo.cn/g?b=qq&nk=${memberData.qq}&s=100`">
                <template #error>
                  <v-icon size="40">mdi-account-circle</v-icon>
                </template>
              </v-img>
            </v-avatar>
            <div>
              <div class="text-h6">{{ memberData.card || memberData.nickname }}</div>
              <div v-if="memberData.card" class="text-body-2 text-medium-emphasis">
                昵称: {{ memberData.nickname }}
              </div>
              <div class="d-flex align-center ga-2 mt-1">
                <v-chip size="small" variant="elevated" :color="roleColor(memberData.role)">
                  {{ roleLabel(memberData.role) }}
                </v-chip>
                <v-chip size="small" variant="outlined" color="grey">
                  {{ relationLabel(memberData.relation) }}
                </v-chip>
              </div>
            </div>
          </div>
          <v-divider />
          <v-table density="compact">
            <tbody>
              <tr>
                <td class="text-caption font-weight-bold" style="width: 120px">QQ 号</td>
                <td class="text-caption">{{ memberData.qq }}</td>
              </tr>
              <tr>
                <td class="text-caption font-weight-bold">群名片</td>
                <td class="text-caption">{{ memberData.card || '-' }}</td>
              </tr>
              <tr>
                <td class="text-caption font-weight-bold">昵称</td>
                <td class="text-caption">{{ memberData.nickname }}</td>
              </tr>
              <tr>
                <td class="text-caption font-weight-bold">群角色</td>
                <td class="text-caption">{{ roleLabel(memberData.role) }}</td>
              </tr>
              <tr>
                <td class="text-caption font-weight-bold">关系</td>
                <td class="text-caption">{{ relationLabel(memberData.relation) }}</td>
              </tr>
              <tr>
                <td class="text-caption font-weight-bold">专属头衔</td>
                <td class="text-caption">{{ memberData.title || '-' }}</td>
              </tr>
              <tr>
                <td class="text-caption font-weight-bold">入群时间</td>
                <td class="text-caption">{{ formatTimestamp(memberData.join_time) }}</td>
              </tr>
              <tr>
                <td class="text-caption font-weight-bold">最后活跃</td>
                <td class="text-caption">{{ formatTimestamp(memberData.last_active_time) }}</td>
              </tr>
            </tbody>
          </v-table>
        </template>
      </v-card-text>
    </v-card>

    <!-- 普通用户变体 -->
    <v-card v-else rounded="lg">
      <v-card-title class="d-flex align-center ga-3 pa-4">
        <v-avatar v-if="userData" size="56">
          <v-img :src="`https://q1.qlogo.cn/g?b=qq&nk=${userData.qq}&s=100`" />
        </v-avatar>
        <div v-if="userData">
          <div class="text-h6">{{ userData.nickname || '未知用户' }}</div>
          <div class="text-caption text-medium-emphasis">QQ: {{ userData.qq }}</div>
        </div>
        <v-spacer />
        <v-chip v-if="userData" :color="relationColor(userData.relation)" variant="elevated">
          <v-icon start size="small">{{ relationIcon(userData.relation) }}</v-icon>
          {{ relationLabel(userData.relation) }}
        </v-chip>
        <v-btn
          icon="mdi-close"
          size="small"
          variant="text"
          @click="$emit('update:modelValue', false)"
        />
      </v-card-title>

      <v-divider />

      <v-card-text v-if="userData">
        <v-row dense>
          <v-col cols="6" sm="4">
            <div class="text-caption text-medium-emphasis">所属群数</div>
            <div class="text-body-1 font-weight-medium">{{ userData.group_count }}</div>
          </v-col>
          <v-col cols="6" sm="4">
            <div class="text-caption text-medium-emphasis">关系等级</div>
            <div class="text-body-1 font-weight-medium">{{ relationLabel(userData.relation) }}</div>
          </v-col>
          <v-col cols="12" sm="4">
            <div class="text-caption text-medium-emphasis">最后同步</div>
            <div class="text-body-1 font-weight-medium">
              {{ userData.last_synced ? formatTime(userData.last_synced) : '-' }}
            </div>
          </v-col>
        </v-row>

        <!-- 所属群聊列表 -->
        <div class="text-subtitle-2 mt-4 mb-2">所属群聊</div>
        <v-table v-if="userGroups.length" density="compact" hover>
          <thead>
            <tr>
              <th>群号</th>
              <th>群名</th>
              <th>成员数</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="g in userGroups"
              :key="g.group_id"
              class="cursor-pointer"
              @click="$emit('open-group', g.group_id)"
            >
              <td>{{ g.group_id }}</td>
              <td>{{ g.group_name }}</td>
              <td>{{ g.member_count }} / {{ g.max_member_count }}</td>
              <td>
                <v-chip :color="activeColor(g.is_active)" size="x-small" variant="elevated">
                  {{ activeLabel(g.is_active) }}
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
        <v-btn color="red" variant="elevated" @click="$emit('update:modelValue', false)">
          关闭
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
/**
 * 用户信息卡片组件 —— 支持普通用户和群成员两个变体。
 *
 * - 普通用户变体（groupId 为空）：展示用户基本信息 + 所属群聊列表
 * - 群成员变体（groupId 有值）：展示用户在特定群内的成员信息
 *
 * 组件内部自动从 personnelStore 加载数据。
 */
import { ref, computed, watch } from 'vue'
import { usePersonnelStore } from '@/stores/personnel'
import type { UserDetail, GroupItem, GroupMemberItem } from '@/apis/personnel'
import { formatTime, formatTimestamp } from '@/utils/format'
import {
  activeColor,
  activeLabel,
  relationColor,
  relationLabel,
  relationIcon,
  roleColor,
  roleLabel,
} from '@/utils/personnel'

const props = defineProps<{
  modelValue: boolean
  qq: number | null
  groupId?: number | null
}>()

defineEmits<{
  'update:modelValue': [value: boolean]
  'open-group': [groupId: number]
}>()

const store = usePersonnelStore()

const loading = ref(false)
const userData = ref<UserDetail | null>(null)
const userGroups = ref<GroupItem[]>([])
const memberData = ref<GroupMemberItem | null>(null)

const isGroupVariant = computed(() => !!props.groupId)

watch(
  () => [props.modelValue, props.qq, props.groupId] as const,
  async ([open, qq]) => {
    if (!open || !qq) {
      userData.value = null
      userGroups.value = []
      memberData.value = null
      return
    }

    loading.value = true
    try {
      if (props.groupId) {
        memberData.value = await store.fetchMemberDetail(props.groupId, qq)
      } else {
        const result = await store.fetchUserDetail(qq)
        userData.value = result.user
        userGroups.value = result.groups
      }
    } finally {
      loading.value = false
    }
  },
  { immediate: false },
)
</script>
