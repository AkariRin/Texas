<template>
  <PageLayout>
    <!-- 数据表格 -->
    <v-data-table
      :headers="headers"
      :items="filteredGroups"
      :search="groupSearch"
      :loading="permStore.loading && !permStore.matrix"
      :item-value="(item: PermissionMatrixGroup) => String(item.group_id)"
      show-expand
      v-model:expanded="expandedRows"
      loading-text="加载权限数据..."
      no-data-text="暂无群聊数据"
    >
      <!-- 工具栏 -->
      <template #top>
        <v-toolbar flat>
          <v-text-field
            v-model="groupSearch"
            label="群名/群号搜索"
            density="compact"
            variant="solo-filled"
            hide-details
            clearable
            prepend-inner-icon="mdi-magnify"
            style="max-width: 280px"
            class="ms-2"
          />
          <v-spacer />
          <v-btn
            variant="elevated"
            color="red"
            prepend-icon="mdi-refresh"
            :loading="permStore.loading"
            @click="refresh"
          >
            刷新
          </v-btn>
        </v-toolbar>
      </template>

      <!-- Bot 总开关列 -->
      <template #item.bot_enabled="{ item }">
        <v-switch
          :model-value="item.bot_enabled"
          density="compact"
          color="red"
          hide-details
          @update:model-value="(val) => onBotSwitch(item.group_id, !!val)"
        />
      </template>

      <!-- 已启用功能统计列 -->
      <template #item.feature_count="{ item }">
        <v-chip size="small" color="red" variant="tonal">
          {{ permStore.groupEnabledCount(item.permissions) }}/{{
            permStore.totalMatrixFeatureCount
          }}
        </v-chip>
      </template>

      <!-- 展开行：功能树 -->
      <template #expanded-row="{ columns, item }">
        <tr>
          <td :colspan="columns.length" class="pa-0">
            <v-list density="compact" class="pa-0">
              <template v-for="ctrl in ctrlFeatures" :key="ctrl.name">
                <!-- Controller 节点（可展开子列表） -->
                <v-list-group :value="`${item.group_id}-${ctrl.name}`">
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
                          :model-value="item.permissions[ctrl.name]"
                          density="compact"
                          color="red"
                          hide-details
                          @click.stop
                          @update:model-value="(val) => onToggle(item.group_id, ctrl.name, !!val)"
                        />
                      </template>
                    </v-list-item>
                  </template>

                  <!-- Method 子节点 -->
                  <v-list-item v-for="child in ctrl.children" :key="child.name" class="method-item">
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
                        :model-value="item.permissions[child.name]"
                        density="compact"
                        color="red"
                        hide-details
                        @update:model-value="(val) => onToggle(item.group_id, child.name, !!val)"
                      />
                    </template>
                  </v-list-item>
                </v-list-group>
                <v-divider />
              </template>
            </v-list>
          </td>
        </tr>
      </template>
    </v-data-table>
  </PageLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { usePermissionStore } from '@/stores/permission'
import type { PermissionMatrixGroup } from '@/apis/permission'
import PageLayout from '@/components/PageLayout.vue'

const permStore = usePermissionStore()

const groupSearch = ref('')
const expandedRows = ref<string[]>([])

// 所有 controller 级功能（含 children）
const ctrlFeatures = computed(() => permStore.matrix?.features ?? [])

// 过滤群组（v-data-table 内置搜索，额外支持群号精确匹配）
const filteredGroups = computed(() => {
  const groups = permStore.matrix?.groups ?? []
  if (!groupSearch.value) return groups
  const q = groupSearch.value.toLowerCase()
  return groups.filter(
    (g) => g.group_name.toLowerCase().includes(q) || String(g.group_id).includes(q),
  )
})

const headers = [
  { title: '群名称', key: 'group_name', sortable: true },
  { title: '群号', key: 'group_id', sortable: true },
  { title: 'Bot 开关', key: 'bot_enabled', sortable: false, width: '110px' },
  { title: '已启用功能', key: 'feature_count', sortable: false, width: '130px' },
  { title: '', key: 'data-table-expand', width: '48px' },
]

async function onToggle(groupId: number, featureName: string, enabled: boolean) {
  await permStore.saveGroupFeatures(groupId, [{ feature_name: featureName, enabled }])
}

async function onBotSwitch(groupId: number, enabled: boolean) {
  await permStore.toggleGroupSwitch(groupId, enabled)
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
