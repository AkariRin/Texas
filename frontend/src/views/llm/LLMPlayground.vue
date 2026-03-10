<template>
  <v-container fluid>
    <v-card flat>
      <v-card-title class="d-flex align-center">
        <v-icon start>mdi-chat</v-icon>
        <span>对话测试</span>
      </v-card-title>

      <v-card-text>
        <v-row>
          <!-- 左侧：参数设置 -->
          <v-col cols="12" md="4">
            <v-select
              v-model="selectedModel"
              :items="modelOptions"
              label="选择模型"
              variant="outlined"
              density="compact"
              class="mb-3"
            />

            <v-textarea
              v-model="systemPrompt"
              label="系统提示词 (可选)"
              variant="outlined"
              density="compact"
              rows="3"
              class="mb-3"
              placeholder="You are a helpful assistant."
            />

            <div class="text-body-2 mb-1">温度: {{ temperature.toFixed(1) }}</div>
            <v-slider
              v-model="temperature"
              :min="0"
              :max="2"
              :step="0.1"
              color="red"
              thumb-label
              class="mb-3"
            />

            <v-text-field
              v-model.number="maxTokens"
              label="最大 Token (可选)"
              variant="outlined"
              density="compact"
              type="number"
              min="1"
              clearable
              class="mb-3"
            />
          </v-col>

          <!-- 右侧：对话区 -->
          <v-col cols="12" md="8">
            <v-card variant="outlined" class="chat-container mb-3">
              <v-card-text ref="chatArea" class="chat-messages">
                <div v-if="messages.length === 0" class="text-center text-medium-emphasis py-8">
                  选择模型并发送消息开始对话
                </div>
                <div
                  v-for="(msg, i) in messages"
                  :key="i"
                  class="chat-message mb-3"
                  :class="msg.role === 'user' ? 'text-right' : ''"
                >
                  <v-chip
                    :color="msg.role === 'user' ? 'red' : 'grey'"
                    variant="tonal"
                    size="small"
                    class="mb-1"
                  >
                    {{ msg.role === 'user' ? '你' : '助手' }}
                  </v-chip>
                  <div
                    class="text-body-2 pa-3 rounded-lg d-inline-block"
                    :class="msg.role === 'user'
                      ? 'bg-red-lighten-5 text-left'
                      : 'bg-grey-lighten-4 text-left'"
                    style="max-width: 90%; white-space: pre-wrap; word-break: break-word"
                  >
                    {{ msg.content }}
                    <span v-if="msg.role === 'assistant' && isStreaming && i === messages.length - 1" class="streaming-cursor">▌</span>
                  </div>
                </div>
              </v-card-text>
            </v-card>

            <div class="d-flex ga-2">
              <v-textarea
                v-model="userInput"
                label="输入消息"
                variant="outlined"
                density="compact"
                rows="2"
                auto-grow
                hide-details
                @keydown.enter.ctrl="sendMessage"
                class="flex-grow-1"
              />
              <div class="d-flex flex-column ga-1">
                <v-btn
                  color="red"
                  :loading="isStreaming"
                  :disabled="!selectedModel || !userInput.trim()"
                  @click="sendMessage"
                  icon="mdi-send"
                />
                <v-btn
                  variant="text"
                  size="small"
                  @click="clearChat"
                  icon="mdi-delete-sweep"
                >
                  <v-tooltip activator="parent" location="top">清空对话</v-tooltip>
                </v-btn>
              </div>
            </div>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useLLMStore } from '@/stores/llm'
import { chatStream } from '@/services/llm'

const store = useLLMStore()

const selectedModel = ref<string | null>(null)
const systemPrompt = ref('')
const temperature = ref(0.7)
const maxTokens = ref<number | null>(null)
const userInput = ref('')
const isStreaming = ref(false)
const chatArea = ref<HTMLElement | null>(null)

interface Message {
  role: string
  content: string
}

const messages = ref<Message[]>([])

const modelOptions = computed(() =>
  store.models
    .filter((m) => m.is_enabled)
    .map((m) => ({
      title: m.display_name || m.model_name,
      subtitle: m.provider_name,
      value: m.id,
    })),
)

function scrollToBottom() {
  nextTick(() => {
    const el = chatArea.value
    if (el) {
      const scrollEl = el.querySelector('.chat-messages')
      if (scrollEl) scrollEl.scrollTop = scrollEl.scrollHeight
    }
  })
}

async function sendMessage() {
  if (!selectedModel.value || !userInput.value.trim() || isStreaming.value) return

  const text = userInput.value.trim()
  userInput.value = ''

  messages.value.push({ role: 'user', content: text })
  scrollToBottom()

  // 构建消息列表
  const apiMessages: Message[] = []
  if (systemPrompt.value.trim()) {
    apiMessages.push({ role: 'system', content: systemPrompt.value.trim() })
  }
  apiMessages.push(...messages.value)

  // 添加空的 assistant 消息用于流式填充
  messages.value.push({ role: 'assistant', content: '' })
  const assistantIdx = messages.value.length - 1

  isStreaming.value = true

  await chatStream(
    selectedModel.value,
    apiMessages,
    (chunk) => {
      const msg = messages.value[assistantIdx]
      if (msg) msg.content += chunk
      scrollToBottom()
    },
    () => {
      isStreaming.value = false
      scrollToBottom()
    },
    (err) => {
      const msg = messages.value[assistantIdx]
      if (msg) msg.content += `\n\n[错误: ${err}]`
      isStreaming.value = false
      scrollToBottom()
    },
    {
      temperature: temperature.value,
      max_tokens: maxTokens.value ?? undefined,
    },
  )
}

function clearChat() {
  messages.value = []
}

onMounted(() => {
  store.loadModels()
  store.loadProviders()
})
</script>

<style scoped>
.chat-container {
  height: 450px;
  display: flex;
  flex-direction: column;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
}

.streaming-cursor {
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}
</style>
