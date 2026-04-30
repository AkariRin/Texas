// global test setup：Vuetify polyfills + @vue/test-utils 全局配置
import { createVuetify } from 'vuetify'
import { config } from '@vue/test-utils'

// Vuetify 的 v-data-table 等组件需要 ResizeObserver
class ResizeObserverStub {
  observe(_target: Element, _options?: ResizeObserverOptions): void {}
  unobserve(_target: Element): void {}
  disconnect(): void {}
}
globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver

// 为所有测试注册 vuetify 插件
const vuetify = createVuetify()
config.global.plugins ??= []
;(config.global.plugins as unknown[]).push(vuetify)
