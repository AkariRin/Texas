<template>
  <v-app>
    <v-app-bar app color="red" prominent>
      <v-app-bar-nav-icon @click="menuOpen = !menuOpen"></v-app-bar-nav-icon>
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
              variant="elevated"
              size="small"
              class="mt-2"
            >
              <v-icon
                start
                :icon="botStore.online ? 'mdi-circle' : 'mdi-circle-outline'"
                size="x-small"
              ></v-icon>
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

    <AppMegaMenu :open="menuOpen" @close="menuOpen = false" />

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
import AppMegaMenu from './components/AppMegaMenu.vue'

const vuetifyTheme = useTheme()
const themeStore = useThemeStore()
const botStore = useBotStore()

const dialogDark = ref(false)
const menuOpen = ref(false)

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
