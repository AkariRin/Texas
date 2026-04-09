<template>
  <Teleport to="body">
    <!-- 遮罩淡入淡出 -->
    <Transition name="backdrop">
      <div v-if="open" class="mega-menu-backdrop" @click="emit('close')" />
    </Transition>

    <!-- 面板滑入 -->
    <Transition name="panel">
      <div v-if="open" class="mega-menu-panel d-flex">
        <!-- 左列：无分组直接项 + 面板名列表 -->
        <div class="panel-nav">
          <!-- 顶层无面板页面（仪表盘）：点击直接导航 -->
          <div
            v-for="r in unpanelRoutes"
            :key="String(r.name)"
            class="panel-nav__item panel-nav__item--direct d-flex align-center ga-2"
            :class="{ 'panel-nav__item--active': route.name === r.name }"
            @click="navigateTo(r.path)"
          >
            <v-icon size="16" class="panel-nav__item-icon flex-shrink-0">{{ r.meta.icon }}</v-icon>
            <span class="panel-nav__item-label">{{ r.meta.title }}</span>
          </div>

          <!-- 面板名列表 -->
          <div
            v-for="[panel] in panelRoutes"
            :key="panel"
            class="panel-nav__item d-flex align-center ga-2"
            :class="{ 'panel-nav__item--active': activePanel === panel }"
            @mouseenter="onPanelMouseEnter(panel)"
            @mouseleave="onPanelMouseLeave"
            @click="onPanelClick(panel)"
          >
            <span class="panel-nav__item-label">{{ panel }}</span>
            <v-icon size="14" class="panel-nav__item-arrow ml-auto flex-shrink-0"
              >mdi-chevron-right</v-icon
            >
          </div>
        </div>

        <!-- 右区：选中面板下的页面卡片 -->
        <div class="panel-content flex-grow-1 overflow-y-auto">
          <!-- 未选中任何面板时 -->
          <div
            v-if="!activePanel"
            class="panel-content__empty d-flex align-center justify-center h-100"
          >
            <span>← 选择左侧分组</span>
          </div>

          <!-- 面板内页面卡片 -->
          <template v-else>
            <!-- 无 section 时显示面板名称大标题；有 section 时由 section 标题代替 -->
            <div
              v-if="!sectionedRoutes.size"
              class="section-title d-flex align-center font-weight-bold mb-4"
            >
              {{ activePanelTitle }}
            </div>

            <!-- 无 section 的路由：直接渲染卡片（兼容扁平面板） -->
            <div v-if="unsectionedRoutes.length" class="section-grid">
              <div
                v-for="r in unsectionedRoutes"
                :key="String(r.name)"
                class="section-card"
                :class="{ 'section-card--active': route.name === r.name }"
                @click="navigateTo(r.path)"
              >
                <div class="section-card__header d-flex align-center ga-2 mb-1">
                  <v-icon size="16" class="section-card__icon flex-shrink-0">{{
                    r.meta.icon
                  }}</v-icon>
                  <div class="section-card__title">{{ r.meta.title }}</div>
                </div>
                <div v-if="r.meta.subtitle" class="section-card__subtitle">
                  {{ r.meta.subtitle }}
                </div>
              </div>
            </div>

            <!-- 有 section 的路由：section 名称作为标题 -->
            <template v-for="[section, sectionRoutes] in sectionedRoutes" :key="section">
              <div class="section-title d-flex align-center font-weight-bold mb-4">
                {{ section }}
              </div>
              <div class="section-grid">
                <div
                  v-for="r in sectionRoutes"
                  :key="String(r.name)"
                  class="section-card"
                  :class="{ 'section-card--active': route.name === r.name }"
                  @click="navigateTo(r.path)"
                >
                  <div class="section-card__header d-flex align-center ga-2 mb-1">
                    <v-icon size="16" class="section-card__icon flex-shrink-0">{{
                      r.meta.icon
                    }}</v-icon>
                    <div class="section-card__title">{{ r.meta.title }}</div>
                  </div>
                  <div v-if="r.meta.subtitle" class="section-card__subtitle">
                    {{ r.meta.subtitle }}
                  </div>
                </div>
              </div>
            </template>
          </template>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
defineOptions({ name: 'AppMenu' })
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import type { RouteRecordNormalized } from 'vue-router'
import { menuPanelTitles } from '@/router'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()

const router = useRouter()
const route = useRoute()

/** 所有可见路由：有 title、非 redirect、未设 hideInMenu */
const navRoutes = computed(() =>
  router
    .getRoutes()
    .filter((r): r is RouteRecordNormalized => !!r.meta.title && !r.redirect && !r.meta.hideInMenu),
)

/** 无面板的顶层页面（仪表盘等），点击直接导航 */
const unpanelRoutes = computed(() => navRoutes.value.filter((r) => !r.meta.panel))

/** 按 panel 分组，保持路由定义顺序；L1 展示面板名 */
const panelRoutes = computed(() => {
  const map = new Map<string, RouteRecordNormalized[]>()
  for (const r of navRoutes.value) {
    const p = r.meta.panel
    if (!p) continue
    if (!map.has(p)) map.set(p, [])
    map.get(p)!.push(r)
  }
  return map
})

/** 当前激活的 L1 面板名 */
const activePanel = ref<string | null>(null)

/** 激活面板下的全部路由 */
const activePanelRoutes = computed(() =>
  activePanel.value ? (panelRoutes.value.get(activePanel.value) ?? []) : [],
)

/** 激活面板的右区标题（优先取 menuPanelTitles，回退到面板名） */
const activePanelTitle = computed(() =>
  activePanel.value ? (menuPanelTitles[activePanel.value] ?? activePanel.value) : '',
)

/** 激活面板下无 section 的路由（直接展示，兼容扁平面板） */
const unsectionedRoutes = computed(() => activePanelRoutes.value.filter((r) => !r.meta.section))

/**
 * 激活面板下按 section 聚合的路由映射。
 * 保持路由定义顺序（Map 插入顺序 = 迭代顺序）。
 */
const sectionedRoutes = computed(() => {
  const map = new Map<string, RouteRecordNormalized[]>()
  for (const r of activePanelRoutes.value) {
    const s = r.meta.section
    if (!s) continue
    if (!map.has(s)) map.set(s, [])
    map.get(s)!.push(r)
  }
  return map
})

/** 菜单打开时自动定位到当前路由所属面板 */
watch(
  () => props.open,
  (isOpen) => {
    if (!isOpen) return
    const currentNav = navRoutes.value.find((r) => r.name === route.name)
    activePanel.value = (currentNav?.meta.panel as string | undefined) ?? null
  },
)

let hoverTimer: ReturnType<typeof setTimeout> | null = null

function onPanelMouseEnter(panel: string): void {
  if (hoverTimer) clearTimeout(hoverTimer)
  hoverTimer = setTimeout(() => {
    activePanel.value = panel
  }, 200)
}

function onPanelMouseLeave(): void {
  if (hoverTimer) clearTimeout(hoverTimer)
  // 不重置 activePanel，防止鼠标滑入 L2 区时内容抖动
}

function onPanelClick(panel: string): void {
  if (hoverTimer) clearTimeout(hoverTimer)
  activePanel.value = panel
}

function navigateTo(path: string): void {
  router.push(path)
  emit('close')
}

/** ESC 键关闭菜单 */
function onKeyDown(e: KeyboardEvent): void {
  if (e.key === 'Escape' && props.open) emit('close')
}

/** 路由跳转后自动关闭（navigateTo 已处理，此处作为兜底） */
const stopRouterGuard = router.afterEach(() => {
  if (props.open) emit('close')
})

onMounted(() => {
  document.addEventListener('keydown', onKeyDown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', onKeyDown)
  stopRouterGuard()
})
</script>

<style scoped>
/* =====================
   遮罩动画
   ===================== */
.backdrop-enter-active,
.backdrop-leave-active {
  transition: opacity 0.22s ease;
}
.backdrop-enter-from,
.backdrop-leave-to {
  opacity: 0;
}

/* =====================
   面板滑入动画
   ===================== */
.panel-enter-active {
  transition: transform 0.22s cubic-bezier(0, 0, 0.2, 1);
}
.panel-leave-active {
  transition: transform 0.18s cubic-bezier(0.4, 0, 1, 1);
}
.panel-enter-from,
.panel-leave-to {
  transform: translateX(-100%);
}

/* =====================
   遮罩层
   ===================== */
.mega-menu-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.32);
  z-index: 200;
}

/* =====================
   菜单面板
   ===================== */
.mega-menu-panel {
  position: fixed;
  left: 0;
  top: var(--appbar-height, 64px);
  height: calc(100vh - var(--appbar-height, 64px));
  width: 50vw;
  min-width: 480px;
  background: rgb(var(--v-theme-surface));
  z-index: 201;
  box-shadow: 4px 0 32px rgba(var(--v-theme-on-surface), 0.15);
}

/* =====================
   左侧面板导航列
   ===================== */
.panel-nav {
  width: 256px;
  flex-shrink: 0;
  border-right: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  overflow-y: auto;
  background: rgb(var(--v-theme-surface));
}

.panel-nav__group-header {
  padding: 12px 16px 4px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: rgba(var(--v-theme-on-surface), 0.38);
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.06);
}

.panel-nav__item {
  padding: 10px 16px;
  cursor: pointer;
  border-right: 3px solid transparent;
  transition:
    background 0.15s,
    border-color 0.15s;
}

.panel-nav__item-arrow {
  opacity: 0.3;
}

.panel-nav__item--active .panel-nav__item-arrow {
  opacity: 0.7;
  color: rgb(var(--v-theme-primary));
}

.panel-nav__item:hover {
  background: rgba(var(--v-theme-primary), 0.06);
}

.panel-nav__item--active {
  border-right-color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.08);
}

.panel-nav__item--active .panel-nav__item-label {
  color: rgb(var(--v-theme-primary));
  font-weight: 600;
}

.panel-nav__item-icon {
  opacity: 0.7;
}

.panel-nav__item--active .panel-nav__item-icon {
  opacity: 1;
  color: rgb(var(--v-theme-primary));
}

.panel-nav__item-label {
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface));
}

/* 顶层无分组页面与面板列表之间的分隔线 */
.panel-nav__item--direct {
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.06);
  margin-bottom: 4px;
}

/* =====================
   右侧面板内容区
   ===================== */
.panel-content {
  padding: 16px 20px;
  background: rgb(var(--v-theme-surface));
}

.panel-content__empty {
  color: rgba(var(--v-theme-on-surface), 0.3);
  font-size: 13px;
}

.section-title {
  font-size: 14px;
  color: rgb(var(--v-theme-on-surface));
}

.section-header {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1.2px;
  text-transform: uppercase;
  color: rgba(var(--v-theme-on-surface), 0.38);
  margin: 12px 0 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.06);
}

.section-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  margin-bottom: 4px;
}

.section-grid + .section-title {
  margin-top: 20px;
}

.section-card {
  padding: 12px 14px;
  border-radius: 8px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  cursor: pointer;
  transition:
    background 0.15s,
    border-color 0.15s,
    box-shadow 0.15s;
}

.section-card:hover {
  background: rgba(var(--v-theme-primary), 0.05);
  border-color: rgba(var(--v-theme-primary), 0.2);
  box-shadow: 0 2px 8px rgba(var(--v-theme-primary), 0.1);
}

.section-card--active {
  background: rgba(var(--v-theme-primary), 0.08);
  border-color: rgba(var(--v-theme-primary), 0.25);
}

.section-card__icon {
  opacity: 0.6;
}

.section-card--active .section-card__icon {
  opacity: 1;
  color: rgb(var(--v-theme-primary));
}

.section-card__title {
  font-size: 12px;
  font-weight: 600;
  color: rgb(var(--v-theme-on-surface));
}

.section-card--active .section-card__title {
  color: rgb(var(--v-theme-primary));
}

.section-card__subtitle {
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.45);
  line-height: 1.4;
  padding-left: 24px; /* 与标题对齐（icon 16px + gap 8px） */
}
</style>
