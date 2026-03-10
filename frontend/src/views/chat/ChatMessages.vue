<template>
  <v-container fluid class="pa-0" style="height: calc(100vh - 64px);">
    <v-row no-gutters style="height: 100%;">
      <!-- 左侧：群聊/私聊选择器 -->
      <v-col cols="3" style="height: 100%; border-right: 1px solid rgba(0,0,0,0.12);">
        <GroupSelector @select="onSessionSelect" />
      </v-col>

      <!-- 右侧：消息区域 -->
      <v-col cols="9" class="d-flex flex-column" style="height: 100%;">
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
                <v-btn icon="mdi-calendar" size="small" variant="text" v-bind="props"></v-btn>
              </template>
              <v-date-picker
                @update:model-value="onDateJump"
                color="primary"
              ></v-date-picker>
            </v-menu>
          </v-toolbar>

          <!-- 搜索 / 筛选栏 -->
          <div class="px-4 pb-2">
            <v-row dense>
              <v-col cols="5">
                <v-text-field
                  v-model="searchKeyword"
                  density="compact"
                  variant="outlined"
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
                  variant="outlined"
                  placeholder="按 QQ 号筛选"
                  hide-details
                  clearable
                  type="number"
                ></v-text-field>
              </v-col>
              <v-col cols="2">
                <v-btn
                  block
                  variant="tonal"
                  color="primary"
                  @click="doSearch"
                  :loading="store.messagesLoading"
                >
                  搜索
                </v-btn>
              </v-col>
              <v-col cols="2">
                <v-btn
                  block
                  variant="outlined"
                  @click="clearSearch"
                >
                  重置
                </v-btn>
              </v-col>
            </v-row>
          </div>

          <v-divider></v-divider>

          <!-- 消息列表 -->
          <div ref="messageContainer" class="flex-grow-1 overflow-y-auto pa-4" @scroll="onScroll">
            <!-- 加载更多按钮 -->
            <div v-if="store.hasMore" class="text-center mb-4">
              <v-btn
                variant="text"
                size="small"
                color="primary"
                :loading="store.messagesLoading"
                @click="loadMore"
              >
                加载更早消息
              </v-btn>
            </div>

            <!-- 消息气泡 -->
            <MessageBubble
              v-for="msg in store.messages"
              :key="`${msg.id}-${msg.created_at}`"
              :message="msg"
            />

            <!-- 空状态 -->
            <div
              v-if="!store.messagesLoading && store.messages.length === 0"
              class="d-flex flex-column align-center justify-center text-medium-emphasis"
              style="min-height: 200px;"
            >
              <v-icon size="48" color="grey-lighten-1">mdi-message-off-outline</v-icon>
              <p class="mt-2">暂无消息</p>
            </div>

            <!-- 加载中 -->
            <div v-if="store.messagesLoading && store.messages.length === 0" class="text-center pa-8">
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
import { ref } from 'vue'
import { useChatStore } from '@/stores/chat'
import GroupSelector from './GroupSelector.vue'
import MessageBubble from './MessageBubble.vue'

const store = useChatStore()

const currentSession = ref<{
  type: 'group' | 'private'
  id: number
  name: string
} | null>(null)

const searchKeyword = ref('')
const filterUserId = ref<string>('')
const messageContainer = ref<HTMLElement | null>(null)

function onSessionSelect(type: 'group' | 'private', id: number, name: string) {
  currentSession.value = { type, id, name }
  searchKeyword.value = ''
  filterUserId.value = ''
  store.clearMessages()
  loadMessages()
}

function loadMessages() {
  if (!currentSession.value) return

  const params: {
    keyword?: string
    userId?: number
    limit?: number
  } = { limit: 50 }

  if (searchKeyword.value) params.keyword = searchKeyword.value
  if (filterUserId.value) params.userId = Number(filterUserId.value)

  if (currentSession.value.type === 'group') {
    store.loadGroupMessages(currentSession.value.id, params)
  } else {
    store.loadPrivateMessages(currentSession.value.id, { limit: params.limit })
  }
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

  // date 可能是 Date 对象或字符串
  const d = date instanceof Date ? date : new Date(String(date))
  // 跳转到指定日期之后的消息
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
  // 当滚动到顶部附近时自动加载更多
  if (el.scrollTop < 100 && store.hasMore && !store.messagesLoading) {
    loadMore()
  }
}
</script>

