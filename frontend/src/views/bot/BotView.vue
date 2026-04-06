<template>
  <PageLayout>
    <template #actions>
      <v-btn
        variant="tonal"
        prepend-icon="mdi-refresh"
        :loading="botStore.profileLoading"
        @click="refresh"
      >
        刷新
      </v-btn>
    </template>

    <!-- 骨架屏：初次加载 -->
    <v-row v-if="botStore.profileLoading && !botStore.profile.user_id">
      <v-col cols="12" md="5" lg="4">
        <v-skeleton-loader type="card" rounded="lg" />
      </v-col>
      <v-col cols="12" md="7" lg="8">
        <v-skeleton-loader type="card" rounded="lg" />
      </v-col>
    </v-row>

    <v-row v-else>
      <!-- 头像与基本信息卡片 -->
      <v-col cols="12" md="5" lg="4">
        <v-card rounded="lg">
          <v-card-text class="d-flex flex-column align-center pa-6">
            <v-avatar size="96" class="mb-4">
              <v-img
                v-if="botStore.profile.avatar_url"
                :src="botStore.profile.avatar_url"
                :alt="botStore.profile.nickname ?? 'Bot'"
              ></v-img>
              <v-icon v-else icon="mdi-robot" size="56"></v-icon>
            </v-avatar>

            <v-chip
              :color="botStore.profile.online ? 'success' : 'grey'"
              variant="tonal"
              size="small"
              class="mb-4"
            >
              <v-icon
                start
                :icon="botStore.profile.online ? 'mdi-circle' : 'mdi-circle-outline'"
                size="x-small"
              ></v-icon>
              {{ botStore.profile.online ? '在线' : '离线' }}
            </v-chip>

            <div class="text-h6 font-weight-bold text-center mb-1">
              {{ botStore.profile.nickname ?? '未连接' }}
            </div>
            <div class="text-body-2 text-medium-emphasis">
              {{ botStore.profile.user_id ? `QQ: ${botStore.profile.user_id}` : '-' }}
            </div>
          </v-card-text>

          <v-divider />

          <!-- 编辑表单 -->
          <v-card-text class="pa-4">
            <div class="text-caption text-medium-emphasis mb-3">编辑资料</div>
            <v-text-field
              v-model="editForm.nickname"
              label="昵称"
              density="compact"
              variant="outlined"
              :disabled="!botStore.profile.online || botStore.profileSaving"
              :hint="botStore.profile.online ? '' : '离线时无法编辑'"
              persistent-hint
              class="mb-2"
            ></v-text-field>
            <v-text-field
              v-model="editForm.personal_note"
              label="个性签名"
              density="compact"
              variant="outlined"
              :disabled="!botStore.profile.online || botStore.profileSaving"
              class="mb-3"
            ></v-text-field>
            <v-btn
              color="primary"
              variant="tonal"
              block
              :disabled="!botStore.profile.online || !hasChanges"
              :loading="botStore.profileSaving"
              @click="saveProfile"
            >
              保存修改
            </v-btn>
          </v-card-text>
        </v-card>
      </v-col>

      <!-- 连接信息卡片 -->
      <v-col cols="12" md="7" lg="8">
        <v-card rounded="lg" class="mb-4">
          <v-card-title class="pa-4 pb-2 text-body-1 font-weight-bold">
            <v-icon start size="20">mdi-information-outline</v-icon>
            连接信息
          </v-card-title>
          <v-card-text class="pa-4 pt-0">
            <v-list density="compact" lines="two">
              <v-list-item>
                <template #prepend>
                  <v-icon size="20" class="mr-2">mdi-protocol</v-icon>
                </template>
                <v-list-item-title class="text-body-2 text-medium-emphasis"
                  >协议版本</v-list-item-title
                >
                <v-list-item-subtitle class="text-body-1">
                  {{ botStore.profile.version?.protocol_version || '-' }}
                </v-list-item-subtitle>
              </v-list-item>
              <v-list-item>
                <template #prepend>
                  <v-icon size="20" class="mr-2">mdi-application</v-icon>
                </template>
                <v-list-item-title class="text-body-2 text-medium-emphasis"
                  >客户端</v-list-item-title
                >
                <v-list-item-subtitle class="text-body-1">
                  {{ botStore.profile.version?.app_name || '-' }}
                  <span
                    v-if="botStore.profile.version?.app_version"
                    class="text-medium-emphasis text-body-2"
                  >
                    v{{ botStore.profile.version.app_version }}
                  </span>
                </v-list-item-subtitle>
              </v-list-item>
              <v-list-item>
                <template #prepend>
                  <v-icon size="20" class="mr-2">mdi-link-variant</v-icon>
                </template>
                <v-list-item-title class="text-body-2 text-medium-emphasis"
                  >WebSocket 连接</v-list-item-title
                >
                <v-list-item-subtitle>
                  <v-chip
                    :color="botStore.profile.online ? 'success' : 'error'"
                    variant="tonal"
                    size="x-small"
                  >
                    {{ botStore.profile.online ? '已连接' : '未连接' }}
                  </v-chip>
                </v-list-item-subtitle>
              </v-list-item>
            </v-list>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- 操作结果 Snackbar -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="3000" location="top">
      {{ snackbar.message }}
    </v-snackbar>
  </PageLayout>
</template>

<script setup lang="ts">
import { reactive, computed, onMounted } from 'vue'
import PageLayout from '@/components/PageLayout.vue'
import { useBotStore } from '@/stores/bot'

const botStore = useBotStore()

const editForm = reactive({
  nickname: '',
  personal_note: '',
})

const snackbar = reactive({
  show: false,
  message: '',
  color: 'success' as 'success' | 'error',
})

// 是否有待保存的改动
const hasChanges = computed(() => {
  return (
    editForm.nickname.trim() !== (botStore.profile.nickname ?? '') ||
    editForm.personal_note.trim() !== ''
  )
})

async function refresh() {
  try {
    await botStore.fetchProfile()
    editForm.nickname = botStore.profile.nickname ?? ''
    editForm.personal_note = ''
  } catch (e: unknown) {
    console.warn('获取 Bot 信息失败', e)
  }
}

async function saveProfile() {
  const payload: Record<string, string> = {}
  const trimmedNickname = editForm.nickname.trim()
  const trimmedNote = editForm.personal_note.trim()

  if (trimmedNickname && trimmedNickname !== (botStore.profile.nickname ?? '')) {
    payload.nickname = trimmedNickname
  }
  if (trimmedNote) {
    payload.personal_note = trimmedNote
  }

  const success = await botStore.saveProfile(payload)
  if (success) {
    snackbar.message = '修改成功'
    snackbar.color = 'success'
    snackbar.show = true
    editForm.nickname = botStore.profile.nickname ?? ''
    editForm.personal_note = ''
  } else {
    snackbar.message = '修改失败，请重试'
    snackbar.color = 'error'
    snackbar.show = true
  }
}

onMounted(() => {
  refresh()
})
</script>
