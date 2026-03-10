<template>
  <v-container fluid class="pa-0" style="height: calc(100vh - 64px)">
    <v-row no-gutters style="height: 100%">
      <!-- 左侧：群/私聊选择器 -->
      <v-col cols="3" style="height: 100%; border-right: 1px solid rgba(0, 0, 0, 0.12)">
        <div class="group-selector d-flex flex-column" style="height: 100%">
          <!-- 搜索栏 -->
          <div class="pa-2">
            <v-text-field
              v-model="selectorSearchQuery"
              density="compact"
              variant="solo-filled"
              placeholder="搜索群聊 / 用户..."
              prepend-inner-icon="mdi-magnify"
              hide-details
              clearable
            ></v-text-field>
          </div>

          <!-- 标签切换 -->
          <v-tabs v-model="selectorTab" density="compact" grow color="primary">
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
            <template v-if="selectorTab === 'groups'">
              <v-list-item
                v-for="group in filteredGroups"
                :key="group.group_id"
                :active="selectedType === 'group' && selectedId === group.group_id"
                @click="selectGroup(group)"
                rounded="lg"
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
                  {{ selectorSearchQuery ? '无匹配结果' : '暂无群聊数据' }}
                </v-list-item-title>
              </v-list-item>
            </template>

            <template v-else>
              <v-list-item
                v-for="user in filteredUsers"
                :key="user.qq"
                :active="selectedType === 'private' && selectedId === user.qq"
                @click="selectUser(user)"
                rounded="lg"
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
                  {{ selectorSearchQuery ? '无匹配结果' : '暂无私聊数据' }}
                </v-list-item-title>
              </v-list-item>
            </template>
          </v-list>
        </div>
      </v-col>

      <!-- 右侧：消息区域 -->
      <v-col cols="9" class="d-flex flex-column" style="height: 100%">
        <!-- 未选择会话 -->
        <div
          v-if="!currentSession"
          class="d-flex flex-column align-center justify-center flex-grow-1 text-medium-emphasis"
        >
          <v-icon size="80" color="grey-lighten-1">mdi-message-text-outline</v-icon>
          <p class="text-h6 mt-4">选择一个会话查看消息</p>
          <p class="text-body-2">从左侧选择群聊或私聊</p>
        </div>

        <!-- 已选择会话 -->
        <template v-else>
          <!-- 顶部信息栏 -->
          <v-toolbar density="compact" flat color="transparent">
            <v-toolbar-title class="text-body-1 font-weight-medium">
              <v-icon class="mr-1" size="small">
                {{ currentSession.type === 'group' ? 'mdi-account-group' : 'mdi-account' }}
              </v-icon>
              {{ currentSession.name }}
              <span class="text-medium-emphasis ml-1">({{ currentSession.id }})</span>
            </v-toolbar-title>
            <v-spacer></v-spacer>

            <!-- 日期跳转 -->
            <v-menu :close-on-content-click="false">
              <template #activator="{ props }">
                <v-btn icon="mdi-calendar" size="small" variant="elevated" v-bind="props"></v-btn>
              </template>
              <v-date-picker @update:model-value="onDateJump" color="primary"></v-date-picker>
            </v-menu>
          </v-toolbar>

          <!-- 搜索 / 筛选栏 -->
          <div class="px-4 pb-2">
            <v-row dense>
              <v-col cols="5">
                <v-text-field
                  v-model="searchKeyword"
                  density="compact"
                  variant="solo-filled"
                  placeholder="搜索消息..."
                  prepend-inner-icon="mdi-magnify"
                  hide-details
                  clearable
                  @keyup.enter="doSearch"
                  @click:clear="clearSearch"
                ></v-text-field>
              </v-col>
              <v-col cols="3">
                <v-text-field
                  v-model="filterUserId"
                  density="compact"
                  variant="solo-filled"
                  placeholder="按 QQ 号筛选"
                  hide-details
                  clearable
                  type="number"
                ></v-text-field>
              </v-col>
              <v-col cols="2">
                <v-btn
                  block
                  variant="elevated"
                  color="primary"
                  @click="doSearch"
                  :loading="store.messagesLoading"
                >
                  搜索
                </v-btn>
              </v-col>
              <v-col cols="2">
                <v-btn block variant="elevated" @click="clearSearch"> 重置 </v-btn>
              </v-col>
            </v-row>
          </div>

          <v-divider></v-divider>

          <!-- 消息列表 -->
          <div ref="messageContainer" class="flex-grow-1 overflow-y-auto pa-4" @scroll="onScroll">
            <!-- 加载更多按钮 -->
            <div v-if="store.hasMore" class="text-center mb-4">
              <v-btn
                variant="elevated"
                size="small"
                color="primary"
                :loading="store.messagesLoading"
                @click="loadMore"
              >
                加载更早消息
              </v-btn>
            </div>

            <!-- 消息气泡 -->
            <div
              v-for="msg in reversedMessages"
              :key="`${msg.id}-${msg.created_at}`"
              class="message-bubble d-flex mb-3"
              :class="{ 'flex-row-reverse': isSelf(msg) }"
            >
              <!-- 头像 -->
              <v-avatar size="36" class="flex-shrink-0" :class="isSelf(msg) ? 'ml-2' : 'mr-2'">
                <v-img
                  :src="`https://q1.qlogo.cn/g?b=qq&nk=${msg.user_id}&s=100`"
                  :alt="msg.sender_nickname"
                >
                  <template #error>
                    <v-icon>mdi-account-circle</v-icon>
                  </template>
                </v-img>
              </v-avatar>

              <!-- 内容 -->
              <div
                class="message-content"
                :class="{ 'text-right': isSelf(msg) }"
                style="max-width: 70%"
              >
                <!-- 昵称与时间 -->
                <div
                  class="d-flex align-center ga-2 mb-1"
                  :class="{ 'flex-row-reverse': isSelf(msg) }"
                >
                  <span class="text-caption font-weight-medium">
                    {{ msg.sender_card || msg.sender_nickname || String(msg.user_id) }}
                  </span>
                  <span v-if="msg.sender_role && msg.sender_role !== 'member'" class="text-caption">
                    <v-chip
                      size="x-small"
                      variant="elevated"
                      :color="getRoleColor(msg.sender_role)"
                      >{{ getRoleLabel(msg.sender_role) }}</v-chip
                    >
                  </span>
                  <span class="text-caption text-medium-emphasis">
                    {{ formatMsgTime(msg.created_at) }}
                  </span>
                </div>

                <!-- 消息气泡 -->
                <div
                  class="message-body rounded-lg pa-2 px-3"
                  :class="isSelf(msg) ? 'bg-blue-lighten-4' : 'bg-grey-lighten-3'"
                >
                  <!-- 消息段渲染 -->
                  <div class="d-flex align-center pa-2" style="gap: 8px">
                    <template v-for="seg in msg.segments" :key="seg">
                      <span
                        v-if="seg.type === 'text'"
                        class="message-text"
                        v-html="escapeHtml(String(seg.data?.text ?? ''))"
                      ></span>
                      <v-img
                        v-else-if="seg.type === 'image'"
                        :src="String(seg.data?.url ?? '')"
                        max-width="200"
                        max-height="200"
                        class="rounded message-image cursor-pointer"
                      >
                        <template #placeholder>
                          <div class="d-flex align-center justify-center fill-height">
                            <v-progress-circular
                              indeterminate
                              size="24"
                              color="grey"
                            ></v-progress-circular>
                          </div>
                        </template>
                        <template #error>
                          <div
                            class="d-flex align-center justify-center fill-height bg-grey-lighten-3 rounded pa-2"
                          >
                            <v-icon color="grey">mdi-image-broken</v-icon>
                          </div>
                        </template>
                      </v-img>
                      <v-chip
                        v-else-if="seg.type === 'at'"
                        size="small"
                        color="blue-lighten-4"
                        variant="elevated"
                        class="mx-1"
                      >
                        @{{ seg.data?.qq === 'all' ? '全体成员' : seg.data?.qq }}
                      </v-chip>
                      <v-chip
                        v-else-if="seg.type === 'reply'"
                        size="x-small"
                        color="grey-lighten-2"
                        variant="elevated"
                        prepend-icon="mdi-reply"
                        class="mr-1"
                      >
                        回复 #{{ seg.data?.id }}
                      </v-chip>
                      <span
                        v-else-if="seg.type === 'face'"
                        class="message-face"
                        :title="`表情 ${seg.data?.id}`"
                      >
                        [表情{{ seg.data?.id }}]
                      </span>
                      <v-chip v-else size="x-small" color="grey-lighten-2" variant="elevated">
                        [{{ seg.type }}]
                      </v-chip>
                    </template>
                  </div>
                </div>
              </div>
            </div>

            <!-- 空状态 -->
            <div
              v-if="!store.messagesLoading && store.messages.length === 0"
              class="d-flex flex-column align-center justify-center text-medium-emphasis"
              style="min-height: 200px"
            >
              <v-icon size="48" color="grey-lighten-1">mdi-message-off-outline</v-icon>
              <p class="mt-2">暂无消息</p>
            </div>

            <!-- 加载中 -->
            <div
              v-if="store.messagesLoading && store.messages.length === 0"
              class="text-center pa-8"
            >
              <v-progress-circular indeterminate color="primary"></v-progress-circular>
              <p class="mt-2 text-medium-emphasis">加载中...</p>
            </div>
          </div>
        </template>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useChatStore } from '@/stores/chat'
import { fetchGroups, fetchUsers } from '@/apis/personnel'
import type { GroupItem, UserItem } from '@/apis/personnel'
import type { ChatMessage } from '@/apis/chat'

const store = useChatStore()

// 反转消息列表：后端返回 newest-first，展示需要 oldest-first（新消息在底部）
const reversedMessages = computed(() => [...store.messages].reverse())

// ── 会话选择器状态 ──

const selectorSearchQuery = ref('')
const selectorTab = ref('groups')
const selectorGroups = ref<GroupItem[]>([])
const selectorUsers = ref<UserItem[]>([])
const selectedType = ref<'group' | 'private'>('group')
const selectedId = ref<number | null>(null)

const filteredGroups = computed(() => {
  if (!selectorSearchQuery.value) return selectorGroups.value
  const q = selectorSearchQuery.value.toLowerCase()
  return selectorGroups.value.filter(
    (g) => g.group_name.toLowerCase().includes(q) || String(g.group_id).includes(q),
  )
})

const filteredUsers = computed(() => {
  if (!selectorSearchQuery.value) return selectorUsers.value
  const q = selectorSearchQuery.value.toLowerCase()
  return selectorUsers.value.filter(
    (u) => u.nickname.toLowerCase().includes(q) || String(u.qq).includes(q),
  )
})

function selectGroup(group: GroupItem) {
  selectedType.value = 'group'
  selectedId.value = group.group_id
  onSessionSelect('group', group.group_id, group.group_name)
}

function selectUser(user: UserItem) {
  selectedType.value = 'private'
  selectedId.value = user.qq
  onSessionSelect('private', user.qq, user.nickname)
}

async function loadSelectorData() {
  try {
    const [groupResult, userResult] = await Promise.all([
      fetchGroups({ page: 1, page_size: 100 }),
      fetchUsers({ page: 1, page_size: 100, relation: 'friend' }),
    ])
    selectorGroups.value = groupResult.items
    selectorUsers.value = userResult.items
  } catch {
    // 静默失败
  }
}

// ── 消息区域状态 ──

const currentSession = ref<{
  type: 'group' | 'private'
  id: number
  name: string
} | null>(null)

const searchKeyword = ref('')
const filterUserId = ref<string>('')
const messageContainer = ref<HTMLElement | null>(null)

// ── 消息气泡辅助 ──

function isSelf(msg: ChatMessage): boolean {
  return msg.message_type === 3 // SELF_SENT
}

function getRoleColor(role: string | undefined): string {
  switch (role) {
    case 'owner':
      return 'amber'
    case 'admin':
      return 'blue'
    default:
      return 'grey'
  }
}

function getRoleLabel(role: string | undefined): string {
  switch (role) {
    case 'owner':
      return '群主'
    case 'admin':
      return '管理员'
    default:
      return role ?? ''
  }
}

function formatMsgTime(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  const time = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  if (isToday) return time
  return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }) + ' ' + time
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
}

// ── 会话与消息操作 ──

function onSessionSelect(type: 'group' | 'private', id: number, name: string) {
  currentSession.value = { type, id, name }
  searchKeyword.value = ''
  filterUserId.value = ''
  store.clearMessages()
  loadMessages(true)
}

function scrollToBottom() {
  nextTick(() => {
    const el = messageContainer.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

async function loadMessages(scrollBottom = false) {
  if (!currentSession.value) return

  const params: {
    keyword?: string
    userId?: number
    limit?: number
  } = { limit: 50 }

  if (searchKeyword.value) params.keyword = searchKeyword.value
  if (filterUserId.value) params.userId = Number(filterUserId.value)

  if (currentSession.value.type === 'group') {
    await store.loadGroupMessages(currentSession.value.id, params)
  } else {
    await store.loadPrivateMessages(currentSession.value.id, { limit: params.limit })
  }

  if (scrollBottom) scrollToBottom()
}

function loadMore() {
  if (!currentSession.value || store.messages.length === 0) return

  const oldest = store.messages[store.messages.length - 1]
  if (!oldest?.created_at) return

  const params: {
    before: string
    keyword?: string
    userId?: number
    limit: number
  } = {
    before: oldest.created_at,
    limit: 50,
  }

  if (searchKeyword.value) params.keyword = searchKeyword.value
  if (filterUserId.value) params.userId = Number(filterUserId.value)

  if (currentSession.value.type === 'group') {
    store.loadGroupMessages(currentSession.value.id, params)
  } else {
    store.loadPrivateMessages(currentSession.value.id, { before: oldest.created_at, limit: 50 })
  }
}

function doSearch() {
  store.clearMessages()
  loadMessages()
}

function clearSearch() {
  searchKeyword.value = ''
  filterUserId.value = ''
  store.clearMessages()
  loadMessages()
}

function onDateJump(date: unknown) {
  if (!currentSession.value || !date) return

  const d = date instanceof Date ? date : new Date(String(date))
  const isoDate = d.toISOString()

  store.clearMessages()
  if (currentSession.value.type === 'group') {
    store.loadGroupMessages(currentSession.value.id, {
      startDate: isoDate,
      limit: 50,
    })
  }
}

function onScroll() {
  const el = messageContainer.value
  if (!el) return
  if (el.scrollTop < 100 && store.hasMore && !store.messagesLoading) {
    loadMore()
  }
}

onMounted(() => {
  loadSelectorData()
})
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

.message-bubble {
  padding: 0 4px;
}

.message-body {
  display: inline-block;
  text-align: left;
  max-width: 100%;
}

.message-text {
  white-space: pre-wrap;
  word-break: break-word;
}

.message-image {
  border: 1px solid rgba(0, 0, 0, 0.1);
}

.message-face {
  color: #f59e0b;
  font-size: 0.9em;
}
</style>
