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

    <!-- 权限矩阵表格 -->
    <v-card flat>
      <v-data-table
        :headers="tableHeaders"
        :items="filteredGroups"
        :loading="permStore.loading"
        density="compact"
        hover
      >
        <!-- 功能列渲染：v-switch -->
        <template v-for="feat in features" :key="feat.name" #[`item.${feat.name}`]="{ item }">
          <v-switch
            :model-value="item.permissions[feat.name]"
            density="compact"
            color="red"
            hide-details
            @update:model-value="(val) => onToggle(item.group_id, feat.name, !!val)"
          />
        </template>
      </v-data-table>
    </v-card>
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { usePermissionStore } from '@/stores/permission'
import PageHeader from '@/components/PageHeader.vue'

const permStore = usePermissionStore()

const groupSearch = ref('')

// 计算表头（群名列 + 每个 controller 功能列）
const features = computed(() => permStore.matrix?.features ?? [])

const tableHeaders = computed(() => [
  { title: '群聊', key: 'group_name', sortable: true, width: 200 },
  { title: '群号', key: 'group_id', sortable: true, width: 120 },
  ...features.value.map((f) => ({
    title: f.display_name || f.name,
    key: f.name,
    sortable: false,
    width: 120,
  })),
])

// 过滤
const filteredGroups = computed(() => {
  const groups = permStore.matrix?.groups ?? []
  if (!groupSearch.value) return groups
  const q = groupSearch.value.toLowerCase()
  return groups.filter(
    (g) => g.group_name.toLowerCase().includes(q) || String(g.group_id).includes(q),
  )
})

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
