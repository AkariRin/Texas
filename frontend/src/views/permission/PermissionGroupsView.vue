<template>
  <v-container fluid>
    <PageHeader />

    <!-- 工具栏 -->
    <v-card flat class="mb-4">
      <v-card-title class="d-flex align-center flex-wrap ga-2">
        <v-text-field
          v-model="groupSearch"
          label="群名/群号搜索"
          density="compact"
          variant="solo-filled"
          hide-details
          clearable
          prepend-inner-icon="mdi-magnify"
          style="max-width: 240px"
        />
        <v-spacer />
        <v-btn variant="text" size="small" @click="toggleAllPanels">
          {{ allExpanded ? '全部折叠' : '全部展开' }}
        </v-btn>
        <v-btn
          variant="elevated"
          color="red"
          prepend-icon="mdi-refresh"
          :loading="permStore.loading"
          @click="refresh"
        >
          刷新
        </v-btn>
      </v-card-title>
    </v-card>

    <!-- 加载状态 -->
    <v-card v-if="permStore.loading && !filteredGroups.length" flat class="text-center pa-8">
      <v-progress-circular indeterminate color="red" />
      <div class="mt-2 text-medium-emphasis">加载权限数据...</div>
    </v-card>

    <!-- 空状态 -->
    <v-card v-else-if="!filteredGroups.length" flat class="text-center pa-8">
      <v-icon size="48" color="medium-emphasis">mdi-account-group-outline</v-icon>
      <div class="mt-2 text-medium-emphasis">暂无群聊数据</div>
    </v-card>

    <!-- 群组可展开面板列表 -->
    <v-expansion-panels v-else v-model="expandedPanels" variant="accordion" multiple>
      <v-expansion-panel v-for="group in filteredGroups" :key="group.group_id">
        <!-- 面板标题：左=群名+群号，右=功能启用统计 -->
        <v-expansion-panel-title>
          <div class="d-flex align-center w-100">
            <span class="font-weight-medium">{{ group.group_name }}</span>
            <span class="text-medium-emphasis text-body-2 ms-2">({{ group.group_id }})</span>
            <v-spacer />
            <v-chip size="small" color="red" variant="tonal" class="me-2">
              {{ permStore.groupEnabledCount(group.permissions) }}/{{
                permStore.totalMatrixFeatureCount
              }}
              已启用
            </v-chip>
          </div>
        </v-expansion-panel-title>

        <!-- 面板内容：功能树 -->
        <v-expansion-panel-text class="pa-0">
          <v-list density="compact" class="pa-0">
            <template v-for="ctrl in ctrlFeatures" :key="ctrl.name">
              <!-- Controller 节点（可展开子列表） -->
              <v-list-group :value="`${group.group_id}-${ctrl.name}`">
                <template #activator="{ props }">
                  <v-list-item v-bind="props" class="ctrl-item">
                    <template #prepend>
                      <v-chip
                        v-if="ctrl.admin"
                        size="x-small"
                        color="warning"
                        variant="tonal"
                        class="me-2"
                      >
                        管理员
                      </v-chip>
                    </template>
                    <v-list-item-title class="font-weight-medium">
                      {{ ctrl.display_name }}
                    </v-list-item-title>
                    <v-list-item-subtitle v-if="ctrl.description">
                      {{ ctrl.description }}
                    </v-list-item-subtitle>
                    <template #append>
                      <v-switch
                        :model-value="group.permissions[ctrl.name]"
                        density="compact"
                        color="red"
                        hide-details
                        @click.stop
                        @update:model-value="(val) => onToggle(group.group_id, ctrl.name, !!val)"
                      />
                    </template>
                  </v-list-item>
                </template>

                <!-- Method 子节点 -->
                <v-list-item
                  v-for="child in ctrl.children"
                  :key="child.name"
                  class="method-item"
                >
                  <template #prepend>
                    <v-tooltip location="top">
                      <template #activator="{ props: tp }">
                        <v-chip
                          v-bind="tp"
                          size="x-small"
                          variant="outlined"
                          color="grey"
                          class="me-2"
                          style="font-family: monospace; cursor: help"
                        >
                          {{ child.mapping_type || 'event' }}
                        </v-chip>
                      </template>
                      <div>
                        <div v-if="child.message_scope !== 'all'">
                          scope: {{ child.message_scope }}
                        </div>
                        <div v-if="child.admin">管理员专用指令</div>
                        <div v-if="!child.admin && child.message_scope === 'all'">无额外限制</div>
                      </div>
                    </v-tooltip>
                  </template>
                  <v-list-item-title>{{ child.display_name }}</v-list-item-title>
                  <v-list-item-subtitle v-if="child.description">
                    {{ child.description }}
                  </v-list-item-subtitle>
                  <template #append>
                    <v-switch
                      :model-value="group.permissions[child.name]"
                      density="compact"
                      color="red"
                      hide-details
                      @update:model-value="(val) => onToggle(group.group_id, child.name, !!val)"
                    />
                  </template>
                </v-list-item>
              </v-list-group>
              <v-divider />
            </template>
          </v-list>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { usePermissionStore } from '@/stores/permission'
import PageHeader from '@/components/PageHeader.vue'

const permStore = usePermissionStore()

const groupSearch = ref('')
const expandedPanels = ref<string[]>([])

// 所有 controller 级功能（含 children）
const ctrlFeatures = computed(() => permStore.matrix?.features ?? [])

// 过滤群组
const filteredGroups = computed(() => {
  const groups = permStore.matrix?.groups ?? []
  if (!groupSearch.value) return groups
  const q = groupSearch.value.toLowerCase()
  return groups.filter(
    (g) => g.group_name.toLowerCase().includes(q) || String(g.group_id).includes(q),
  )
})

// 全部展开/折叠
const allExpanded = computed(() => expandedPanels.value.length > 0)

function toggleAllPanels() {
  if (allExpanded.value) {
    expandedPanels.value = []
  } else {
    // 展开所有群组的所有 controller
    const keys: string[] = []
    for (const group of filteredGroups.value) {
      for (const ctrl of ctrlFeatures.value) {
        keys.push(`${group.group_id}-${ctrl.name}`)
      }
    }
    expandedPanels.value = keys
  }
}

async function onToggle(groupId: number, featureName: string, enabled: boolean) {
  await permStore.saveGroupFeatures(groupId, [{ feature_name: featureName, enabled }])
}

async function refresh() {
  await permStore.loadMatrix()
}

onMounted(async () => {
  await permStore.loadMatrix()
})
</script>

<style scoped>
.ctrl-item {
  background-color: rgba(var(--v-theme-surface-variant), 0.3);
}

.method-item {
  padding-left: 48px;
}
</style>
