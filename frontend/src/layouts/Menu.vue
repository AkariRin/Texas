<template>
  <Teleport to="body">
    <!-- 遮罩淡入淡出 -->
    <Transition name="backdrop">
      <div v-if="open" class="mega-menu-backdrop" @click="emit('close')" />
    </Transition>

    <!-- 面板滑入 -->
    <Transition name="panel">
      <div v-if="open" class="mega-menu-panel">
        <!-- L1 左列：无分组直接项 + 分组名列表 -->
        <div class="mega-menu-l1">
          <!-- 顶层无分组页面（仪表盘）：点击直接导航 -->
          <div
            v-for="r in ungroupedRoutes"
            :key="String(r.name)"
            class="l1-item l1-item--direct"
            :class="{ 'l1-item--active': route.name === r.name }"
            @click="navigateTo(r.path)"
          >
            <v-icon size="16" class="l1-item__icon">{{ r.meta.icon }}</v-icon>
            <span class="l1-item__label">{{ r.meta.title }}</span>
          </div>

          <!-- 分组名列表（L1 = 分组） -->
          <div
            v-for="[group] in groupedRoutes"
            :key="group"
            class="l1-item"
            :class="{ 'l1-item--active': activeGroup === group }"
            @mouseenter="onGroupMouseEnter(group)"
            @mouseleave="onGroupMouseLeave"
            @click="onGroupClick(group)"
          >
            <span class="l1-item__label">{{ group }}</span>
            <v-icon size="14" class="l1-item__arrow">mdi-chevron-right</v-icon>
          </div>
        </div>

        <!-- L2 右区：选中分组下的页面卡片 -->
        <div class="mega-menu-l2">
          <!-- 未选中任何分组时 -->
          <div v-if="!activeGroup" class="l2-empty">
            <span>← 选择左侧分组</span>
          </div>

          <!-- 分组内页面卡片网格 -->
          <template v-else>
            <!-- 无 section 时显示 group 名称大标题；有 section 时由 section 标题代替 -->
            <div v-if="!sectionedRoutes.size" class="l2-title">{{ activePanelTitle }}</div>

            <!-- 无 section 的路由：直接渲染卡片（兼容扁平分组） -->
            <div v-if="unsectionedRoutes.length" class="l2-card-grid">
              <div
                v-for="r in unsectionedRoutes"
                :key="String(r.name)"
                class="l2-card"
                :class="{ 'l2-card--active': route.name === r.name }"
                @click="navigateTo(r.path)"
              >
                <div class="l2-card__header">
                  <v-icon size="16" class="l2-card__icon">{{ r.meta.icon }}</v-icon>
                  <div class="l2-card__title">{{ r.meta.title }}</div>
                </div>
                <div v-if="r.meta.subtitle" class="l2-card__subtitle">{{ r.meta.subtitle }}</div>
              </div>
            </div>

            <!-- 有 section 的路由：section 名称复用 l2-title 样式，无 divider -->
            <template v-for="[section, sectionRoutes] in sectionedRoutes" :key="section">
              <div class="l2-title">{{ section }}</div>
              <div class="l2-card-grid">
                <div
                  v-for="r in sectionRoutes"
                  :key="String(r.name)"
                  class="l2-card"
                  :class="{ 'l2-card--active': route.name === r.name }"
                  @click="navigateTo(r.path)"
                >
                  <div class="l2-card__header">
                    <v-icon size="16" class="l2-card__icon">{{ r.meta.icon }}</v-icon>
                    <div class="l2-card__title">{{ r.meta.title }}</div>
                  </div>
                  <div v-if="r.meta.subtitle" class="l2-card__subtitle">{{ r.meta.subtitle }}</div>
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

/** 无分组的顶层页面（仪表盘等），点击直接导航 */
const ungroupedRoutes = computed(() => navRoutes.value.filter((r) => !r.meta.group))

/** 按 group 分组，保持路由定义顺序；L1 展示分组名 */
const groupedRoutes = computed(() => {
  const map = new Map<string, RouteRecordNormalized[]>()
  for (const r of navRoutes.value) {
    const g = r.meta.group
    if (!g) continue
    if (!map.has(g)) map.set(g, [])
    map.get(g)!.push(r)
  }
  return map
})

/** 当前激活的 L1 分组名 */
const activeGroup = ref<string | null>(null)

/** 激活分组下的全部路由 */
const activeGroupRoutes = computed(() =>
  activeGroup.value ? (groupedRoutes.value.get(activeGroup.value) ?? []) : [],
)

/** 激活分组的右区面板标题（优先取 menuPanelTitles，回退到分组名） */
const activePanelTitle = computed(() =>
  activeGroup.value ? (menuPanelTitles[activeGroup.value] ?? activeGroup.value) : '',
)

/** 激活分组下无 section 的路由（直接展示，兼容扁平分组） */
const unsectionedRoutes = computed(() => activeGroupRoutes.value.filter((r) => !r.meta.section))

/**
 * 激活分组下按 section 聚合的路由映射。
 * 保持路由定义顺序（Map 插入顺序 = 迭代顺序）。
 */
const sectionedRoutes = computed(() => {
  const map = new Map<string, RouteRecordNormalized[]>()
  for (const r of activeGroupRoutes.value) {
    const s = r.meta.section
    if (!s) continue
    if (!map.has(s)) map.set(s, [])
    map.get(s)!.push(r)
  }
  return map
})

/** 菜单打开时自动定位到当前路由所属分组 */
watch(
  () => props.open,
  (isOpen) => {
    if (!isOpen) return
    const currentNav = navRoutes.value.find((r) => r.name === route.name)
    activeGroup.value = (currentNav?.meta.group as string | undefined) ?? null
  },
)

let hoverTimer: ReturnType<typeof setTimeout> | null = null

function onGroupMouseEnter(group: string): void {
  if (hoverTimer) clearTimeout(hoverTimer)
  hoverTimer = setTimeout(() => {
    activeGroup.value = group
  }, 200)
}

function onGroupMouseLeave(): void {
  if (hoverTimer) clearTimeout(hoverTimer)
  // 不重置 activeGroup，防止鼠标滑入 L2 区时内容抖动
}

function onGroupClick(group: string): void {
  if (hoverTimer) clearTimeout(hoverTimer)
  activeGroup.value = group
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
  display: flex;
  background: rgb(var(--v-theme-surface));
  z-index: 201;
  box-shadow: 4px 0 32px rgba(var(--v-theme-on-surface), 0.15);
}

/* =====================
   L1 左列
   ===================== */
.mega-menu-l1 {
  width: 256px;
  flex-shrink: 0;
  border-right: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  overflow-y: auto;
  background: rgb(var(--v-theme-surface));
}

.l1-group-header {
  padding: 12px 16px 4px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: rgba(var(--v-theme-on-surface), 0.38);
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.06);
}

.l1-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  cursor: pointer;
  border-right: 3px solid transparent;
  transition:
    background 0.15s,
    border-color 0.15s;
}

.l1-item__arrow {
  margin-left: auto;
  opacity: 0.3;
  flex-shrink: 0;
}

.l1-item--active .l1-item__arrow {
  opacity: 0.7;
  color: rgb(var(--v-theme-primary));
}

.l1-item:hover {
  background: rgba(var(--v-theme-primary), 0.06);
}

.l1-item--active {
  border-right-color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.08);
}

.l1-item--active .l1-item__label {
  color: rgb(var(--v-theme-primary));
  font-weight: 600;
}

.l1-item__icon {
  opacity: 0.7;
  flex-shrink: 0;
}

.l1-item--active .l1-item__icon {
  opacity: 1;
  color: rgb(var(--v-theme-primary));
}

.l1-item__label {
  font-size: 13px;
  color: rgb(var(--v-theme-on-surface));
}

/* 顶层无分组页面与分组内容之间的分隔线 */
.l1-item--direct {
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.06);
  margin-bottom: 4px;
}

/* =====================
   L2 右区
   ===================== */
.mega-menu-l2 {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
  background: rgb(var(--v-theme-surface));
}

.l2-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: rgba(var(--v-theme-on-surface), 0.3);
  font-size: 13px;
}

.l2-title {
  display: flex;
  align-items: center;
  font-size: 14px;
  font-weight: 700;
  color: rgb(var(--v-theme-on-surface));
  margin-bottom: 16px;
}

.l2-section-header {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1.2px;
  text-transform: uppercase;
  color: rgba(var(--v-theme-on-surface), 0.38);
  margin: 12px 0 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.06);
}

.l2-card-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  margin-bottom: 4px;
}

.l2-card {
  padding: 12px 14px;
  border-radius: 8px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  cursor: pointer;
  transition:
    background 0.15s,
    border-color 0.15s,
    box-shadow 0.15s;
}

.l2-card:hover {
  background: rgba(var(--v-theme-primary), 0.05);
  border-color: rgba(var(--v-theme-primary), 0.2);
  box-shadow: 0 2px 8px rgba(var(--v-theme-primary), 0.1);
}

.l2-card--active {
  background: rgba(var(--v-theme-primary), 0.08);
  border-color: rgba(var(--v-theme-primary), 0.25);
}

.l2-card__header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.l2-card__icon {
  opacity: 0.6;
  flex-shrink: 0;
}

.l2-card--active .l2-card__icon {
  opacity: 1;
  color: rgb(var(--v-theme-primary));
}

.l2-card__title {
  font-size: 12px;
  font-weight: 600;
  color: rgb(var(--v-theme-on-surface));
}

.l2-card--active .l2-card__title {
  color: rgb(var(--v-theme-primary));
}

.l2-card__subtitle {
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.45);
  line-height: 1.4;
  padding-left: 24px; /* 与标题对齐（icon 16px + gap 8px） */
}
</style>
