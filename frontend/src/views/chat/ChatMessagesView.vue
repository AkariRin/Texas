<template>
  <v-container fluid class="pa-0" style="height: calc(100vh - 64px)">
    <v-row no-gutters style="height: 100%">
      <!-- 左侧：群/私聊选择器 -->
      <v-col cols="3" style="height: 100%; border-right: 1px solid rgba(0, 0, 0, 0.12)">
        <SessionSelector
          :active-type="currentSession?.type ?? null"
          :active-id="currentSession?.id ?? null"
          :groups="personnelStore.sessionGroups"
          :users="personnelStore.sessionUsers"
          @select="onSessionSelect"
        />
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
                  :loading="store.messagesLoading"
                  @click="doSearch"
                >
                  搜索
                </v-btn>
              </v-col>
              <v-col cols="2">
                <v-btn block variant="elevated" @click="clearSearch">重置</v-btn>
              </v-col>
            </v-row>
          </div>

          <v-divider></v-divider>

          <!-- 消息列表 -->
          <div ref="messageContainer" class="flex-grow-1 overflow-y-auto pa-4" @scroll="onScroll">
            <!-- 加载更多按钮 -->
            <div v-if="store.hasMore && store.messages.length > 0" class="text-center mb-4">
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

            <!-- 消息气泡列表 -->
            <MessageBubble
              v-for="msg in reversedMessages"
              :key="`${msg.id}-${msg.created_at}`"
              :msg="msg"
              :member-name-map="memberNameMap"
              @show-detail="showDetail"
              @open-member="onAtChipClick"
              @open-image="openImagePreview"
            />

            <!-- 空状态 -->
            <div
              v-if="!store.messagesLoading && store.messages.length === 0"
              class="d-flex flex-column align-center justify-center text-medium-emphasis"
              style="min-height: 200px"
            >
              <v-icon size="48" color="grey-lighten-1">mdi-message-off-outline</v-icon>
              <p class="mt-2">暂无消息</p>
            </div>

            <!-- 加载中骨架 -->
            <div v-if="store.messagesLoading && store.messages.length === 0" class="pa-4">
              <div v-for="n in 6" :key="n" class="d-flex mb-3">
                <v-skeleton-loader
                  type="list-item-avatar-two-line"
                  :width="n % 2 === 0 ? '60%' : '45%'"
                />
              </div>
            </div>
          </div>
        </template>
      </v-col>
    </v-row>

    <!-- 弹窗 -->
    <MessageDetailDialog v-model="detailDialog" :message="detailMessage" />
    <MemberDetailDialog
      v-model="memberDetailDialog"
      :loading="memberDetailLoading"
      :member="memberDetail"
    />
    <ImagePreviewDialog v-model="imagePreviewDialog" :src="imagePreviewSrc" />
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from 'vue'
import { useChatStore } from '@/stores/chat'
import { usePersonnelStore } from '@/stores/personnel'
import type { GroupMemberItem } from '@/apis/personnel'
import type { ChatMessage } from '@/apis/chat'
import SessionSelector from './components/SessionSelector.vue'
import MessageBubble from './components/MessageBubble.vue'
import MessageDetailDialog from './components/MessageDetailDialog.vue'
import MemberDetailDialog from './components/MemberDetailDialog.vue'
import ImagePreviewDialog from './components/ImagePreviewDialog.vue'

const store = useChatStore()
const personnelStore = usePersonnelStore()

const reversedMessages = computed(() => [...store.messages].reverse())

// ── 会话状态 ──

const currentSession = ref<{ type: 'group' | 'private'; id: number; name: string } | null>(null)
const searchKeyword = ref('')
const filterUserId = ref<string>('')
const messageContainer = ref<HTMLElement | null>(null)

// ── 弹窗状态 ──

const detailDialog = ref(false)
const detailMessage = ref<ChatMessage | null>(null)

const memberDetailDialog = ref(false)
const memberDetailLoading = ref(false)
const memberDetail = ref<GroupMemberItem | null>(null)

const imagePreviewDialog = ref(false)
const imagePreviewSrc = ref('')

// ── @成员名片映射 ──

const memberNameMap = computed(() => {
  const map = new Map<number, string>()
  for (const msg of store.messages) {
    if (msg.user_id && !map.has(msg.user_id)) {
      const name = msg.sender_card || msg.sender_nickname
      if (name) map.set(msg.user_id, name)
    }
  }
  return map
})

// ── 操作函数 ──

function showDetail(msg: ChatMessage) {
  detailMessage.value = msg
  detailDialog.value = true
}

async function onAtChipClick(qq: unknown) {
  if (qq === 'all') return
  if (!currentSession.value || currentSession.value.type !== 'group') return
  const qqNum = Number(qq)
  if (isNaN(qqNum)) return

  memberDetail.value = null
  memberDetailLoading.value = true
  memberDetailDialog.value = true

  try {
    await personnelStore.loadGroupMembers(currentSession.value.id, {
      page: 1,
      page_size: 1,
      qq: qqNum,
    })
    memberDetail.value = personnelStore.groupMembers.items[0] ?? null
  } catch {
    memberDetail.value = null
  } finally {
    memberDetailLoading.value = false
  }
}

function openImagePreview(src: string) {
  if (!src) return
  imagePreviewSrc.value = src
  imagePreviewDialog.value = true
}

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
  const params: { keyword?: string; userId?: number; limit?: number } = { limit: 50 }
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

  const before = oldest.created_at
  if (currentSession.value.type === 'group') {
    const params = {
      before,
      limit: 50,
      ...(searchKeyword.value ? { keyword: searchKeyword.value } : {}),
      ...(filterUserId.value ? { userId: Number(filterUserId.value) } : {}),
    }
    store.loadGroupMessages(currentSession.value.id, params)
  } else {
    store.loadPrivateMessages(currentSession.value.id, { before, limit: 50 })
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
  store.clearMessages()
  if (currentSession.value.type === 'group') {
    store.loadGroupMessages(currentSession.value.id, { startDate: d.toISOString(), limit: 50 })
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
  personnelStore.loadSessionData()
})
</script>
