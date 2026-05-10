import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useThemeStore } from '@/stores/theme'

// mock vuetify useTheme，避免依赖真实 Vuetify 实例
vi.mock('vuetify', () => ({
  useTheme: vi.fn(() => ({
    change: vi.fn(),
  })),
}))

import { useTheme } from 'vuetify'

// jsdom 未实现 matchMedia，提供最小 stub
const mockMediaQuery = {
  matches: false,
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
}
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn(() => mockMediaQuery),
})

function makeMockTheme() {
  return { change: vi.fn() } as unknown as ReturnType<typeof useTheme>
}

describe('useThemeStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockMediaQuery.matches = false
  })

  // ── 初始状态 ──

  describe('初始状态', () => {
    it('preference 初始为 "light"', () => {
      const store = useThemeStore()
      expect(store.preference).toBe('light')
    })
  })

  // ── setPreference() ──

  describe('setPreference()', () => {
    it('设置为 "dark" 后 preference 更新', () => {
      const store = useThemeStore()
      const mockTheme = makeMockTheme()

      store.setPreference('dark', mockTheme)

      expect(store.preference).toBe('dark')
    })

    it('设置为 "dark" 时调用 vuetifyTheme.change("dark")', () => {
      const store = useThemeStore()
      const mockTheme = makeMockTheme()

      store.setPreference('dark', mockTheme)

      expect(mockTheme.change).toHaveBeenCalledWith('dark')
    })

    it('设置为 "light" 时调用 vuetifyTheme.change("light")', () => {
      const store = useThemeStore()
      const mockTheme = makeMockTheme()

      store.setPreference('light', mockTheme)

      expect(mockTheme.change).toHaveBeenCalledWith('light')
    })

    it('设置为 "followOS" 时根据系统主题调用 change（jsdom 默认非暗色）', () => {
      const store = useThemeStore()
      const mockTheme = makeMockTheme()

      store.setPreference('followOS', mockTheme)

      expect(store.preference).toBe('followOS')
      expect(mockTheme.change).toHaveBeenCalledWith('light')
    })

    it('设置为 "followOS" 且系统为暗色时调用 change("dark")', () => {
      mockMediaQuery.matches = true
      const store = useThemeStore()
      const mockTheme = makeMockTheme()

      store.setPreference('followOS', mockTheme)

      expect(mockTheme.change).toHaveBeenCalledWith('dark')
    })
  })

  // ── initTheme() ──

  describe('initTheme()', () => {
    it('调用时立即应用当前 preference', () => {
      const store = useThemeStore()
      const mockTheme = makeMockTheme()
      store.preference = 'dark'

      store.initTheme(mockTheme)

      expect(mockTheme.change).toHaveBeenCalledWith('dark')
    })

    it('注册 matchMedia change 事件监听器', () => {
      const store = useThemeStore()
      const mockTheme = makeMockTheme()

      store.initTheme(mockTheme)

      expect(mockMediaQuery.addEventListener).toHaveBeenCalledWith('change', expect.any(Function))
    })
  })
})
