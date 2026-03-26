<template>
  <v-container fluid>
    <PageHeader />

    <v-row>
      <!-- 左侧：功能树形列表 -->
      <v-col cols="12" md="4">
        <v-card flat>
          <v-card-title class="text-subtitle-1">功能列表</v-card-title>
          <v-list density="compact" nav>
            <template v-for="feat in permStore.controllerFeatures" :key="feat.name">
              <v-list-group :value="feat.name">
                <template #activator="{ props }">
                  <v-list-item
                    v-bind="props"
                    :active="selectedFeature === feat.name"
                    active-color="red"
                    rounded="lg"
                    @click.stop="selectFeature(feat)"
                  >
                    <template #prepend>
                      <v-icon :color="feat.enabled ? 'green' : 'grey'" size="small">
                        {{ feat.enabled ? 'mdi-check-circle' : 'mdi-close-circle' }}
                      </v-icon>
                    </template>
                    <v-list-item-title>{{ feat.display_name || feat.name }}</v-list-item-title>
                    <v-list-item-subtitle class="text-caption">
                      {{ feat.description || feat.name }}
                    </v-list-item-subtitle>
                    <template #append>
                      <v-chip v-if="feat.admin" size="x-small" color="warning" variant="tonal">
                        管理员
                      </v-chip>
                    </template>
                  </v-list-item>
                </template>

                <!-- Method 子节点（仅展示，不可选择私聊权限） -->
                <v-list-item
                  v-for="child in feat.children"
                  :key="child.name"
                  class="ps-6"
                  density="compact"
                >
                  <template #prepend>
                    <v-tooltip location="top">
                      <template #activator="{ props: tp }">
                        <v-chip
                          v-bind="tp"
                          size="x-small"
                          variant="outlined"
                          color="grey"
                          style="font-family: monospace; cursor: help"
                        >
                          {{ child.mapping_type || 'event' }}
                        </v-chip>
                      </template>
                      <div>
                        <div v-if="child.message_scope !== 'all'">scope: {{ child.message_scope }}</div>
                        <div v-if="child.admin">管理员专用指令</div>
                        <div v-if="!child.admin && child.message_scope === 'all'">无额外限制</div>
                      </div>
                    </v-tooltip>
                  </template>
                  <v-list-item-title class="text-caption">
                    {{ child.display_name || child.name }}
                  </v-list-item-title>
                  <v-list-item-subtitle v-if="child.description" class="text-caption">
                    {{ child.description }}
                  </v-list-item-subtitle>
                </v-list-item>
              </v-list-group>
            </template>
          </v-list>
        </v-card>
      </v-col>

      <!-- 右侧：用户管理 -->
      <v-col cols="12" md="8">
        <v-card flat>
          <template v-if="selectedFeature">
            <v-card-title class="d-flex align-center ga-2">
              <span>{{ currentFeature?.display_name || selectedFeature }}</span>
              <v-spacer />
              <!-- 模式切换 -->
              <v-btn-toggle
                v-model="currentMode"
                density="compact"
                color="red"
                variant="outlined"
                mandatory
                @update:model-value="onModeChange"
              >
                <v-btn value="blacklist" size="small">黑名单</v-btn>
                <v-btn value="whitelist" size="small">白名单</v-btn>
              </v-btn-toggle>
            </v-card-title>

            <v-card-subtitle class="pb-2">
              <template v-if="currentMode === 'blacklist'">
                黑名单模式：列表中的用户<strong>无法</strong>使用此功能
              </template>
              <template v-else>
                白名单模式：仅列表中的用户<strong>可以</strong>使用此功能
              </template>
            </v-card-subtitle>

            <v-divider />

            <!-- 添加用户 -->
            <v-card-text>
              <div class="d-flex align-center ga-2 mb-4">
                <v-text-field
                  v-model="newQqStr"
                  label="输入 QQ 号"
                  density="compact"
                  variant="solo-filled"
                  hide-details
                  type="number"
                  style="max-width: 200px"
                  @keyup.enter="addUser"
                />
                <v-btn
                  color="red"
                  variant="elevated"
                  prepend-icon="mdi-plus"
                  :loading="adding"
                  @click="addUser"
                >
                  添加
                </v-btn>
              </div>

              <!-- 用户列表 -->
              <v-list density="compact">
                <v-list-item
                  v-for="qq in currentUsers"
                  :key="qq"
                  :title="String(qq)"
                  prepend-icon="mdi-account"
                >
                  <template #append>
                    <v-btn
                      icon="mdi-delete-outline"
                      size="small"
                      variant="text"
                      color="error"
                      @click="removeUser(qq)"
                    />
                  </template>
                </v-list-item>
                <v-list-item v-if="!currentUsers.length" class="text-medium-emphasis">
                  <v-list-item-title>列表为空</v-list-item-title>
                </v-list-item>
              </v-list>
            </v-card-text>
          </template>

          <template v-else>
            <v-card-text class="text-center text-medium-emphasis pa-8">
              <v-icon size="48" class="mb-2">mdi-cursor-pointer</v-icon>
              <div>请从左侧选择一个功能</div>
            </v-card-text>
          </template>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { usePermissionStore } from '@/stores/permission'
import PageHeader from '@/components/PageHeader.vue'
import type { FeatureItem } from '@/apis/permission'

const permStore = usePermissionStore()

const selectedFeature = ref<string | null>(null)
const currentMode = ref<'blacklist' | 'whitelist'>('blacklist')
const newQqStr = ref('')
const adding = ref(false)

const currentFeature = computed<FeatureItem | undefined>(() =>
  permStore.controllerFeatures.find((f) => f.name === selectedFeature.value),
)

const currentUsers = computed<number[]>(() =>
  selectedFeature.value ? (permStore.privateUsers[selectedFeature.value] ?? []) : [],
)

async function selectFeature(feat: FeatureItem) {
  selectedFeature.value = feat.name
  currentMode.value = feat.private_mode
  await permStore.loadPrivateUsers(feat.name)
}

async function onModeChange(mode: string) {
  if (!selectedFeature.value) return
  await permStore.patchFeature(selectedFeature.value, undefined, mode)
}

async function addUser() {
  if (!selectedFeature.value || !newQqStr.value) return
  const qq = parseInt(newQqStr.value, 10)
  if (isNaN(qq)) return
  adding.value = true
  try {
    await permStore.addUser(selectedFeature.value, qq)
    newQqStr.value = ''
  } finally {
    adding.value = false
  }
}

async function removeUser(qq: number) {
  if (!selectedFeature.value) return
  await permStore.removeUser(selectedFeature.value, qq)
}

onMounted(async () => {
  await permStore.loadFeatures()
})
</script>
