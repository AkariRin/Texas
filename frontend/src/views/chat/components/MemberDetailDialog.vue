<template>
  <v-dialog
    :model-value="modelValue"
    max-width="480"
    scrollable
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <v-card rounded="lg">
      <v-card-title class="d-flex align-center">
        <v-icon class="mr-2" size="small">mdi-account-details</v-icon>
        群成员详情
        <v-spacer></v-spacer>
        <v-btn
          icon="mdi-close"
          size="small"
          variant="text"
          @click="$emit('update:modelValue', false)"
        ></v-btn>
      </v-card-title>
      <v-divider></v-divider>
      <v-card-text class="pa-0">
        <!-- 加载中 -->
        <div v-if="loading">
          <div class="d-flex align-center pa-4" style="gap: 16px">
            <v-skeleton-loader
              type="avatar"
              style="width: 64px; height: 64px"
              boilerplate
            ></v-skeleton-loader>
            <div class="flex-grow-1">
              <v-skeleton-loader type="heading" class="mb-1"></v-skeleton-loader>
              <v-skeleton-loader type="text" style="max-width: 160px"></v-skeleton-loader>
              <div class="d-flex ga-2 mt-2">
                <v-skeleton-loader type="chip" style="width: 72px"></v-skeleton-loader>
                <v-skeleton-loader type="chip" style="width: 72px"></v-skeleton-loader>
              </div>
            </div>
          </div>
          <v-divider></v-divider>
          <div class="pa-2">
            <v-skeleton-loader type="table-row@6"></v-skeleton-loader>
          </div>
        </div>
        <!-- 未找到 -->
        <div
          v-else-if="!member"
          class="d-flex flex-column align-center justify-center pa-8 text-medium-emphasis"
        >
          <v-icon size="48" color="grey-lighten-1">mdi-account-off-outline</v-icon>
          <p class="mt-2 text-body-2">未找到该成员信息</p>
        </div>
        <!-- 成员信息 -->
        <template v-else>
          <div class="d-flex align-center pa-4" style="gap: 16px">
            <v-avatar size="64">
              <v-img :src="`https://q1.qlogo.cn/g?b=qq&nk=${member.qq}&s=100`">
                <template #error>
                  <v-icon size="40">mdi-account-circle</v-icon>
                </template>
              </v-img>
            </v-avatar>
            <div>
              <div class="text-h6">{{ member.card || member.nickname }}</div>
              <div v-if="member.card" class="text-body-2 text-medium-emphasis">
                昵称: {{ member.nickname }}
              </div>
              <div class="d-flex align-center ga-2 mt-1">
                <v-chip size="small" variant="elevated" :color="roleColor(member.role)">
                  {{ roleLabel(member.role) }}
                </v-chip>
                <v-chip size="small" variant="outlined" color="grey">
                  {{ relationLabel(member.relation) }}
                </v-chip>
              </div>
            </div>
          </div>
          <v-divider></v-divider>
          <v-table density="compact">
            <tbody>
              <tr>
                <td class="text-caption font-weight-bold" style="width: 120px">QQ 号</td>
                <td class="text-caption">{{ member.qq }}</td>
              </tr>
              <tr>
                <td class="text-caption font-weight-bold">群名片</td>
                <td class="text-caption">{{ member.card || '-' }}</td>
              </tr>
              <tr>
                <td class="text-caption font-weight-bold">昵称</td>
                <td class="text-caption">{{ member.nickname }}</td>
              </tr>
              <tr>
                <td class="text-caption font-weight-bold">群角色</td>
                <td class="text-caption">{{ roleLabel(member.role) }}</td>
              </tr>
              <tr>
                <td class="text-caption font-weight-bold">关系</td>
                <td class="text-caption">{{ relationLabel(member.relation) }}</td>
              </tr>
              <tr>
                <td class="text-caption font-weight-bold">专属头衔</td>
                <td class="text-caption">{{ member.title || '-' }}</td>
              </tr>
              <tr>
                <td class="text-caption font-weight-bold">入群时间</td>
                <td class="text-caption">{{ formatTimestamp(member.join_time) }}</td>
              </tr>
              <tr>
                <td class="text-caption font-weight-bold">最后活跃</td>
                <td class="text-caption">{{ formatTimestamp(member.last_active_time) }}</td>
              </tr>
            </tbody>
          </v-table>
        </template>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import type { GroupMemberItem } from '@/apis/personnel'
import { formatTimestamp } from '@/utils/format'
import { roleColor, roleLabel, relationLabel } from '@/utils/personnel'

defineProps<{
  modelValue: boolean
  loading: boolean
  member: GroupMemberItem | null
}>()
defineEmits<{ 'update:modelValue': [value: boolean] }>()
</script>
