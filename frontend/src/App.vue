<template>
  <v-app>
    <v-app-bar app color="red" prominent>
      <v-app-bar-nav-icon @click="rail = !rail"></v-app-bar-nav-icon>
      <v-app-bar-title>Texas</v-app-bar-title>
      <v-spacer></v-spacer>
      <v-tooltip text="主题偏好" location="bottom">
        <template #activator="{ props }">
          <v-btn icon="mdi-weather-night" v-bind="props" @click="dialogDark = true"></v-btn>
        </template>
      </v-tooltip>
      <v-tooltip text="GitHub" location="bottom">
        <template #activator="{ props }">
          <v-btn
            icon="mdi-github"
            v-bind="props"
            href="https://github.com/AkariRin/Texas"
            target="_blank"
          ></v-btn>
        </template>
      </v-tooltip>
      <v-menu offset-y>
        <template #activator="{ props }">
          <v-btn icon v-bind="props" class="ml-1">
            <v-avatar size="32">
              <v-img
                v-if="botStore.avatarUrl"
                :src="botStore.avatarUrl"
                :alt="botStore.nickname ?? 'Bot'"
              ></v-img>
              <v-icon v-else icon="mdi-robot"></v-icon>
            </v-avatar>
          </v-btn>
        </template>
        <v-card min-width="200">
          <v-card-text class="text-center pa-4">
            <v-avatar size="64" class="mb-2">
              <v-img
                v-if="botStore.avatarUrl"
                :src="botStore.avatarUrl"
                :alt="botStore.nickname ?? 'Bot'"
              ></v-img>
              <v-icon v-else icon="mdi-robot" size="40"></v-icon>
            </v-avatar>
            <div class="text-subtitle-1 font-weight-bold">{{ botStore.nickname ?? '未连接' }}</div>
            <div class="text-caption text-medium-emphasis">{{ botStore.userId ?? '-' }}</div>
            <v-chip
              :color="botStore.online ? 'success' : 'grey'"
              variant="tonal"
              size="small"
              class="mt-2"
            >
              <v-icon start :icon="botStore.online ? 'mdi-circle' : 'mdi-circle-outline'" size="x-small"></v-icon>
              {{ botStore.online ? '在线' : '离线' }}
            </v-chip>
          </v-card-text>
          <v-divider></v-divider>
          <v-list density="compact">
            <v-list-item
              prepend-icon="mdi-refresh"
              title="刷新状态"
              @click="botStore.fetchStatus()"
            ></v-list-item>
          </v-list>
        </v-card>
      </v-menu>
    </v-app-bar>
    <v-navigation-drawer :rail="rail" permanent class="nav-drawer">
      <!-- 仪表盘 -->
      <v-list density="compact" nav class="nav-list">
        <v-list-item
          prepend-icon="mdi-view-dashboard"
          title="仪表盘"
          value="dashboard"
          to="/"
          rounded="lg"
          class="nav-item"
        ></v-list-item>
      </v-list>

      <!-- 用户与群聊 -->
      <v-list density="compact" nav class="nav-list">
        <v-list-subheader v-if="!rail" class="nav-subheader">用户与群聊</v-list-subheader>
        <v-list-item
          prepend-icon="mdi-account-group"
          title="用户管理"
          value="personnel-users"
          to="/personnel/users"
          rounded="lg"
          class="nav-item"
        ></v-list-item>
        <v-list-item
          prepend-icon="mdi-forum"
          title="群聊管理"
          value="personnel-groups"
          to="/personnel/groups"
          rounded="lg"
          class="nav-item"
        ></v-list-item>
        <v-list-item
          prepend-icon="mdi-shield-account"
          title="管理员"
          value="personnel-admins"
          to="/personnel/admins"
          rounded="lg"
          class="nav-item"
        ></v-list-item>
        <v-list-item
          prepend-icon="mdi-sync"
          title="数据同步"
          value="personnel-sync"
          to="/personnel/sync"
          rounded="lg"
          class="nav-item"
        ></v-list-item>
      </v-list>

      <!-- 大模型 -->
      <v-list density="compact" nav class="nav-list">
        <v-list-subheader v-if="!rail" class="nav-subheader">大模型</v-list-subheader>
        <v-list-item
          prepend-icon="mdi-server-network"
          title="提供商"
          value="llm-providers"
          to="/llm/providers"
          rounded="lg"
          class="nav-item"
        ></v-list-item>
        <v-list-item
          prepend-icon="mdi-brain"
          title="模型管理"
          value="llm-models"
          to="/llm/models"
          rounded="lg"
          class="nav-item"
        ></v-list-item>
        <v-list-item
          prepend-icon="mdi-chat"
          title="对话测试"
          value="llm-playground"
          to="/llm/playground"
          rounded="lg"
          class="nav-item"
        ></v-list-item>
      </v-list>

      <!-- 系统 -->
      <v-list density="compact" nav class="nav-list">
        <v-list-subheader v-if="!rail" class="nav-subheader">系统</v-list-subheader>
        <v-list-item
          prepend-icon="mdi-tray-full"
          title="任务队列"
          value="queue"
          to="/queue"
          rounded="lg"
          class="nav-item"
        ></v-list-item>
        <v-list-item
          prepend-icon="mdi-text-box-outline"
          title="应用日志"
          value="logs"
          to="/logs"
          rounded="lg"
          class="nav-item"
        ></v-list-item>
        <v-list-item
          prepend-icon="mdi-cog"
          title="设置"
          value="settings"
          to="/settings"
          rounded="lg"
          class="nav-item"
        ></v-list-item>
      </v-list>
    </v-navigation-drawer>
    <v-main>
      <v-dialog v-model="dialogDark" max-width="300">
        <v-card>
          <v-card-title>主题偏好</v-card-title>
          <v-card-text>
            <v-radio-group v-model="themePreference" column mandatory>
              <v-radio label="浅色模式" value="light"></v-radio>
              <v-radio label="深色模式" value="dark"></v-radio>
              <v-radio label="跟随系统设置" value="followOS"></v-radio>
            </v-radio-group>
          </v-card-text>
          <v-card-actions>
            <v-spacer></v-spacer>
            <v-btn color="red" @click="dialogDark = false">
              <v-icon start>mdi-close</v-icon>关闭
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>
      <router-view />
    </v-main>
  </v-app>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useTheme } from 'vuetify'
import { useThemeStore } from './stores/theme'
import { useBotStore } from './stores/bot'
import type { ThemePreference } from './stores/theme'

const vuetifyTheme = useTheme()
const themeStore = useThemeStore()
const botStore = useBotStore()

const dialogDark = ref(false)
const rail = ref(false)

const themePreference = computed({
  get(): ThemePreference {
    return themeStore.preference
  },
  set(value: ThemePreference) {
    themeStore.setPreference(value, vuetifyTheme)
  },
})

onMounted(() => {
  themeStore.initTheme(vuetifyTheme)
  botStore.startPolling()
})

onUnmounted(() => {
  botStore.stopPolling()
})
</script>

<style scoped>
/* Navigation drawer depth */
:deep(.nav-drawer) {
  border-right: 1px solid rgba(0, 0, 0, 0.08) !important;
  box-shadow: 2px 0 12px rgba(0, 0, 0, 0.1), 4px 0 24px rgba(0, 0, 0, 0.06) !important;
  background: linear-gradient(180deg, #fafafa 0%, #f5f5f5 100%) !important;
}

/* Dark mode drawer */
:deep(.v-theme--dark .nav-drawer) {
  background: linear-gradient(180deg, #1e1e2e 0%, #181825 100%) !important;
  box-shadow: 2px 0 12px rgba(0, 0, 0, 0.4), 4px 0 24px rgba(0, 0, 0, 0.25) !important;
  border-right: 1px solid rgba(255, 255, 255, 0.06) !important;
}

/* Brand area */
.nav-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 16px 12px;
}

.nav-brand-text {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.5px;
  background: linear-gradient(135deg, #e53935, #ef9a9a);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* Subheader */
:deep(.nav-subheader) {
  font-size: 10px !important;
  font-weight: 700 !important;
  letter-spacing: 1.2px !important;
  text-transform: uppercase;
  color: rgba(0, 0, 0, 0.38) !important;
  padding-left: 12px !important;
}

:deep(.v-theme--dark .nav-subheader) {
  color: rgba(255, 255, 255, 0.3) !important;
}

/* Nav list padding */
.nav-list {
  padding: 4px 8px !important;
}

/* Nav items with 3D depth effect */
:deep(.nav-item) {
  margin-bottom: 4px !important;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
  border: 1px solid transparent !important;
}

:deep(.nav-item:hover) {
  background: rgba(229, 57, 53, 0.08) !important;
  border-color: rgba(229, 57, 53, 0.15) !important;
  box-shadow: 0 2px 8px rgba(229, 57, 53, 0.12), 0 1px 3px rgba(0, 0, 0, 0.08) !important;
  transform: translateX(2px);
}

:deep(.nav-item.v-list-item--active) {
  background: linear-gradient(135deg, rgba(229, 57, 53, 0.15), rgba(229, 57, 53, 0.08)) !important;
  border-color: rgba(229, 57, 53, 0.3) !important;
  box-shadow:
    0 3px 10px rgba(229, 57, 53, 0.2),
    0 1px 4px rgba(0, 0, 0, 0.1),
    inset 0 1px 0 rgba(255, 255, 255, 0.3) !important;
  transform: translateX(3px);
}

:deep(.v-theme--dark .nav-item:hover) {
  background: rgba(239, 154, 154, 0.1) !important;
  border-color: rgba(239, 154, 154, 0.2) !important;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3), 0 1px 3px rgba(0, 0, 0, 0.2) !important;
}

:deep(.v-theme--dark .nav-item.v-list-item--active) {
  background: linear-gradient(135deg, rgba(239, 154, 154, 0.18), rgba(239, 154, 154, 0.08)) !important;
  border-color: rgba(239, 154, 154, 0.3) !important;
  box-shadow:
    0 3px 10px rgba(0, 0, 0, 0.35),
    inset 0 1px 0 rgba(255, 255, 255, 0.08) !important;
}

/* Active icon color */
:deep(.nav-item.v-list-item--active .v-icon) {
  color: #e53935 !important;
  filter: drop-shadow(0 0 4px rgba(229, 57, 53, 0.4));
}

/* Footer */
.nav-footer {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 16px;
}

.nav-footer-text {
  font-size: 11px;
  color: rgba(0, 0, 0, 0.38);
}

:deep(.v-theme--dark) .nav-footer-text {
  color: rgba(255, 255, 255, 0.3);
}
</style>
