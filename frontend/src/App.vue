<template>
  <v-app>
    <v-app-bar app color="primary" prominent>
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
      <v-tooltip text="Bot 信息" location="bottom">
        <template #activator="{ props }">
          <v-btn icon class="ml-1" v-bind="props" @click="router.push({ name: 'bot-profile' })">
            <v-badge
              class="status-badge"
              :color="botStore.online ? 'success' : 'grey-darken-1'"
              dot
              location="bottom end"
            >
              <v-avatar size="32">
                <v-img
                  v-if="botStore.avatarUrl"
                  :src="botStore.avatarUrl"
                  :alt="botStore.nickname ?? 'Bot'"
                ></v-img>
                <v-icon v-else icon="mdi-robot"></v-icon>
              </v-avatar>
            </v-badge>
          </v-btn>
        </template>
      </v-tooltip>
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
import { useRouter } from 'vue-router'
import { useThemeStore } from './stores/theme'
import { useBotStore } from './stores/bot'
import type { ThemePreference } from './stores/theme'
import AppMegaMenu from './components/AppMegaMenu.vue'

const vuetifyTheme = useTheme()
const router = useRouter()
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

<style scoped>
/* 放大在线状态 dot，去除白色描边 */
:deep(.status-badge .v-badge__badge) {
  width: 10px;
  height: 10px;
  min-width: 10px;
  border: none !important;
  box-shadow: none !important;
}
</style>
