<template>
  <Teleport to="body">
    <!-- 遮罩淡入淡出 -->
    <Transition name="backdrop">
      <div v-if="open" class="mega-menu-backdrop" @click="emit('close')" />
    </Transition>

    <!-- 面板滑入 -->
    <Transition name="panel">
      <div v-if="open" class="mega-menu-panel">
        <!-- L1 左列：所有页面按分组标题分隔 -->
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

          <!-- 分组页面 -->
          <template v-for="[group, routes] in groupedRoutes" :key="group">
            <div class="l1-group-header">{{ group }}</div>
            <div
              v-for="r in routes"
              :key="String(r.name)"
              class="l1-item"
              :class="{ 'l1-item--active': activePage?.name === r.name }"
              @mouseenter="onPageMouseEnter(r)"
              @mouseleave="onPageMouseLeave"
              @click="onPageClick(r)"
            >
              <v-icon size="16" class="l1-item__icon">{{ r.meta.icon }}</v-icon>
              <span class="l1-item__label">{{ r.meta.title }}</span>
            </div>
          </template>
        </div>

        <!-- L2 右区：选中页面的子路由卡片 -->
        <div class="mega-menu-l2">
          <!-- 未选中任何 L1 页面时 -->
          <div v-if="!activePage" class="l2-empty">
            <span>← 选择左侧页面</span>
          </div>

          <!-- 有子路由：分节卡片网格 -->
          <template v-else-if="subRoutes.length > 0">
            <div class="l2-title">
              <v-icon size="18" class="mr-2">{{ activePage.meta.icon }}</v-icon>
              {{ activePage.meta.title }}
            </div>
            <template v-for="[section, routes] in groupedSubRoutes" :key="section ?? '__default__'">
              <div v-if="section" class="l2-section-header">{{ section }}</div>
              <div class="l2-card-grid">
                <div
                  v-for="r in routes"
                  :key="String(r.name)"
                  class="l2-card"
                  :class="{ 'l2-card--active': route.name === r.name }"
                  @click="navigateTo(r.path)"
                >
                  <div class="l2-card__title">{{ r.meta.title }}</div>
                  <div v-if="r.meta.subtitle" class="l2-card__subtitle">{{ r.meta.subtitle }}</div>
                </div>
              </div>
            </template>
          </template>

          <!-- 无子路由：单张大卡片 -->
          <template v-else>
            <div class="l2-solo-card" @click="navigateTo(activePage.path)">
              <v-icon size="32" class="l2-solo-card__icon">{{ activePage.meta.icon }}</v-icon>
              <div class="l2-solo-card__title">{{ activePage.meta.title }}</div>
              <div v-if="activePage.meta.subtitle" class="l2-solo-card__subtitle">
                {{ activePage.meta.subtitle }}
              </div>
              <div class="l2-solo-card__action">
                <v-btn variant="tonal" color="primary" size="small" append-icon="mdi-arrow-right">
                  前往页面
                </v-btn>
              </div>
            </div>
          </template>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import type { RouteRecordNormalized } from 'vue-router'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()

const router = useRouter()
const route = useRoute()

/** 所有可见页面路由：有 title + icon、非 redirect、非子路由 */
const navRoutes = computed(() =>
  router
    .getRoutes()
    .filter(
      (r): r is RouteRecordNormalized =>
        !!r.meta.title && !!r.meta.icon && !r.redirect && !r.meta.parentPage,
    ),
)

/** 无分组的顶层页面（仪表盘等），点击直接导航 */
const ungroupedRoutes = computed(() => navRoutes.value.filter((r) => !r.meta.group))

/** 按 group 分组，保持路由定义顺序 */
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

/** 当前激活的 L1 页面 */
const activePage = ref<RouteRecordNormalized | null>(null)

/** 菜单打开时自动定位到当前路由所属页面；无分组页面则留空 */
watch(
  () => props.open,
  (isOpen) => {
    if (!isOpen) return
    const matched = navRoutes.value.find((r) => r.name === route.name)
    activePage.value = matched ?? null
  },
)

let hoverTimer: ReturnType<typeof setTimeout> | null = null

function onPageMouseEnter(page: RouteRecordNormalized): void {
  if (hoverTimer) clearTimeout(hoverTimer)
  hoverTimer = setTimeout(() => {
    activePage.value = page
  }, 200)
}

function onPageMouseLeave(): void {
  if (hoverTimer) clearTimeout(hoverTimer)
  // 不重置 activePage，防止鼠标滑入 L2 区时内容抖动
}

function onPageClick(page: RouteRecordNormalized): void {
  if (hoverTimer) clearTimeout(hoverTimer)
  activePage.value = page
}

function navigateTo(path: string): void {
  router.push(path)
  emit('close')
}

/** activePage 对应的所有子路由（parentPage === activePage.name） */
const subRoutes = computed(() => {
  if (!activePage.value) return []
  return router
    .getRoutes()
    .filter(
      (r) => r.meta.parentPage === String(activePage.value!.name) && !!r.meta.title && !r.redirect,
    )
})

/** 子路由按 group 字段分节，group 在子路由中用作 L2 小标题 */
const groupedSubRoutes = computed(() => {
  const map = new Map<string | undefined, typeof subRoutes.value>()
  for (const r of subRoutes.value) {
    const g = r.meta.group
    if (!map.has(g)) map.set(g, [])
    map.get(g)!.push(r)
  }
  return map
})

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
  gap: 10px;
  padding: 10px 16px;
  cursor: pointer;
  border-right: 3px solid transparent;
  transition:
    background 0.15s,
    border-color 0.15s;
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

.l2-card__title {
  font-size: 12px;
  font-weight: 600;
  color: rgb(var(--v-theme-on-surface));
  margin-bottom: 3px;
}

.l2-card--active .l2-card__title {
  color: rgb(var(--v-theme-primary));
}

.l2-card__subtitle {
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.45);
  line-height: 1.4;
}

/* 单张大卡片（无子路由时） */
.l2-solo-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  padding: 24px;
  border-radius: 12px;
  border: 1px solid rgba(var(--v-theme-primary), 0.2);
  background: rgba(var(--v-theme-primary), 0.04);
  cursor: pointer;
  transition: background 0.15s;
  max-width: 320px;
}

.l2-solo-card:hover {
  background: rgba(var(--v-theme-primary), 0.08);
}

.l2-solo-card__icon {
  color: rgb(var(--v-theme-primary));
  opacity: 0.7;
}

.l2-solo-card__title {
  font-size: 16px;
  font-weight: 700;
  color: rgb(var(--v-theme-on-surface));
}

.l2-solo-card__subtitle {
  font-size: 13px;
  color: rgba(var(--v-theme-on-surface), 0.5);
  line-height: 1.5;
}

.l2-solo-card__action {
  margin-top: 8px;
}
</style>
