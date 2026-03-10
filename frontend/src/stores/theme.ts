import { ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { useTheme } from 'vuetify'

export type ThemePreference = 'light' | 'dark' | 'followOS'

function getSystemDark(): boolean {
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

function resolveTheme(preference: ThemePreference): string {
  if (preference === 'followOS') {
    return getSystemDark() ? 'dark' : 'light'
  }
  return preference
}

export const useThemeStore = defineStore(
  'theme',
  () => {
    const preference = ref<ThemePreference>('light')

    function applyTheme(vuetifyTheme: ReturnType<typeof useTheme>) {
      vuetifyTheme.change(resolveTheme(preference.value))
    }

    function setPreference(value: ThemePreference, vuetifyTheme: ReturnType<typeof useTheme>) {
      preference.value = value
      applyTheme(vuetifyTheme)
    }

    function initTheme(vuetifyTheme: ReturnType<typeof useTheme>) {
      applyTheme(vuetifyTheme)

      // 监听操作系统主题变化
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
      mediaQuery.addEventListener('change', () => {
        if (preference.value === 'followOS') {
          applyTheme(vuetifyTheme)
        }
      })

      // 监听偏好设置变化
      watch(preference, () => {
        applyTheme(vuetifyTheme)
      })
    }

    return { preference, setPreference, initTheme }
  },
  {
    persist: {
      key: 'texas-theme-preference',
      pick: ['preference'],
    },
  },
)
