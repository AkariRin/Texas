<template>
  <PageLayout>
    <v-card flat>
      <!-- Tab 切换 -->
      <v-tabs v-model="activeTab" color="primary">
        <v-tab value="logs">抽取日志</v-tab>
        <v-tab value="presets">预设管理</v-tab>
      </v-tabs>

      <v-divider />

      <v-window v-model="activeTab">
        <!-- Tab 1: 抽取日志 -->
        <v-window-item value="logs">
          <v-card-title class="d-flex align-center flex-wrap ga-2 pt-3">
            <v-text-field
              v-model.number="logsFilter.group_id"
              label="群号"
              density="compact"
              variant="solo-filled"
              hide-details
              clearable
              type="number"
              style="max-width: 160px"
              @update:model-value="loadLogs(1)"
            />
            <v-text-field
              v-model.number="logsFilter.user_id"
              label="用户 QQ"
              density="compact"
              variant="solo-filled"
              hide-details
              clearable
              type="number"
              style="max-width: 160px"
              @update:model-value="loadLogs(1)"
            />
            <v-text-field
              v-model="logsFilter.date"
              label="日期"
              density="compact"
              variant="solo-filled"
              hide-details
              clearable
              type="date"
              style="max-width: 180px"
              @update:model-value="loadLogs(1)"
            />
          </v-card-title>

          <v-skeleton-loader v-if="logsLoading && !logItems.length" type="table" class="pa-2" />
          <v-data-table
            v-else
            :headers="logHeaders"
            :items="logItems"
            :items-length="logsTotal"
            :loading="logsLoading"
            :page="logsPage"
            :items-per-page="logsPageSize"
            :items-per-page-options="[10, 20, 50]"
            hover
            @update:page="loadLogs"
            @update:items-per-page="
              (v: number) => {
                logsPageSize = v
                loadLogs(1)
              }
            "
          >
            <!-- 老婆列 -->
            <template #[`item.wife_qq`]="{ item }">
              <div class="d-flex align-center ga-2">
                <v-avatar size="24">
                  <v-img :src="`https://q1.qlogo.cn/g?b=qq&nk=${item.wife_qq}&s=40`" />
                </v-avatar>
                <span class="text-caption">{{ item.wife_name }}（{{ item.wife_qq }}）</span>
              </div>
            </template>
            <!-- 抽取时间列 -->
            <template #[`item.drawn_at`]="{ item }">
              <v-chip :color="item.drawn_at ? 'success' : 'warning'" size="small" variant="tonal">
                {{ item.drawn_at ? formatTime(item.drawn_at) : '预设中' }}
              </v-chip>
            </template>
          </v-data-table>
        </v-window-item>

        <!-- Tab 2: 预设管理 -->
        <v-window-item value="presets">
          <v-card-title class="d-flex align-center pt-3">
            <v-spacer />
            <v-btn color="primary" prepend-icon="mdi-plus" @click="openCreateDialog">
              新增预设
            </v-btn>
          </v-card-title>

          <v-skeleton-loader
            v-if="presetsLoading && !presetItems.length"
            type="table"
            class="pa-2"
          />
          <v-data-table
            v-else
            :headers="presetHeaders"
            :items="presetItems"
            :items-length="presetsTotal"
            :loading="presetsLoading"
            :page="presetsPage"
            :items-per-page="presetsPageSize"
            :items-per-page-options="[10, 20, 50]"
            hover
            @update:page="loadPresets"
            @update:items-per-page="
              (v: number) => {
                presetsPageSize = v
                loadPresets(1)
              }
            "
          >
            <!-- 老婆列 -->
            <template #[`item.wife_qq`]="{ item }">
              <div class="d-flex align-center ga-2">
                <v-avatar size="24">
                  <v-img :src="`https://q1.qlogo.cn/g?b=qq&nk=${item.wife_qq}&s=40`" />
                </v-avatar>
                <span class="text-caption">{{ item.wife_name }}（{{ item.wife_qq }}）</span>
              </div>
            </template>
            <!-- 操作列 -->
            <template #[`item.actions`]="{ item }">
              <v-btn icon size="small" variant="text" @click="openEditDialog(item)">
                <v-icon>mdi-pencil</v-icon>
                <v-tooltip activator="parent" location="top">修改</v-tooltip>
              </v-btn>
              <v-btn icon size="small" variant="text" color="error" @click="confirmDelete(item)">
                <v-icon>mdi-delete</v-icon>
                <v-tooltip activator="parent" location="top">删除</v-tooltip>
              </v-btn>
            </template>
          </v-data-table>
        </v-window-item>
      </v-window>
    </v-card>

    <!-- 新增/编辑弹窗 -->
    <v-dialog v-model="formDialog" max-width="480" persistent>
      <v-card>
        <v-card-title>{{ isEditing ? '修改老婆' : '新增预设' }}</v-card-title>
        <v-card-text>
          <v-form ref="formRef">
            <template v-if="!isEditing">
              <v-text-field
                v-model.number="formData.group_id"
                label="群号"
                type="number"
                :rules="[required]"
                class="mb-2"
              />
              <v-text-field
                v-model.number="formData.user_id"
                label="抽取者 QQ"
                type="number"
                :rules="[required]"
                class="mb-2"
              />
              <v-text-field
                v-model="formData.date"
                label="日期"
                type="date"
                :rules="[required]"
                class="mb-2"
              />
            </template>
            <v-text-field
              v-model.number="formData.wife_qq"
              label="老婆 QQ"
              type="number"
              :rules="[required]"
              class="mb-2"
            />
            <v-text-field v-model="formData.wife_name" label="老婆昵称" :rules="[required]" />
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="formDialog = false">取消</v-btn>
          <v-btn color="primary" :loading="formLoading" @click="submitForm">确定</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 删除确认弹窗 -->
    <v-dialog v-model="deleteDialog" max-width="360">
      <v-card>
        <v-card-title>确认删除</v-card-title>
        <v-card-text>
          确定删除 {{ deleteTarget?.user_id }} 在群 {{ deleteTarget?.group_id }} 的预设老婆吗？
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog = false">取消</v-btn>
          <v-btn color="error" :loading="deleteLoading" @click="doDelete">删除</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </PageLayout>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import * as jrlpApi from '@/apis/jrlp'
import type { WifeRecord } from '@/apis/jrlp'
import PageLayout from '@/components/PageLayout.vue'
import { formatTime } from '@/utils/format'

// ── 当前激活 Tab ──
const activeTab = ref<'logs' | 'presets'>('logs')

// ── 抽取日志 ──
const logsPage = ref(1)
const logsPageSize = ref(20)
const logsLoading = ref(false)
const logItems = ref<WifeRecord[]>([])
const logsTotal = ref(0)
const logsFilter = ref<{ group_id: number | null; user_id: number | null; date: string | null }>({
  group_id: null,
  user_id: null,
  date: null,
})

const logHeaders = [
  { title: '群号', key: 'group_id', sortable: false },
  { title: '抽取者 QQ', key: 'user_id', sortable: false },
  { title: '老婆', key: 'wife_qq', sortable: false },
  { title: '日期', key: 'date', sortable: false },
  { title: '抽取时间', key: 'drawn_at', sortable: false },
]

async function loadLogs(page = logsPage.value) {
  logsLoading.value = true
  logsPage.value = page
  try {
    const result = await jrlpApi.listRecords({
      group_id: logsFilter.value.group_id ?? undefined,
      user_id: logsFilter.value.user_id ?? undefined,
      date: logsFilter.value.date ?? undefined,
      page,
      page_size: logsPageSize.value,
    })
    logItems.value = result.items
    logsTotal.value = result.total
  } finally {
    logsLoading.value = false
  }
}

// ── 预设管理 ──
const presetsPage = ref(1)
const presetsPageSize = ref(20)
const presetsLoading = ref(false)
const presetItems = ref<WifeRecord[]>([])
const presetsTotal = ref(0)

const presetHeaders = [
  { title: '群号', key: 'group_id', sortable: false },
  { title: '抽取者 QQ', key: 'user_id', sortable: false },
  { title: '老婆', key: 'wife_qq', sortable: false },
  { title: '日期', key: 'date', sortable: false },
  { title: '操作', key: 'actions', sortable: false },
]

async function loadPresets(page = presetsPage.value) {
  presetsLoading.value = true
  presetsPage.value = page
  try {
    // 预设 = drawn_at 为 null；后端暂无此过滤参数，前端过滤已有数据
    const result = await jrlpApi.listRecords({
      page,
      page_size: presetsPageSize.value,
    })
    presetItems.value = result.items.filter((r) => r.drawn_at === null)
    presetsTotal.value = presetItems.value.length
  } finally {
    presetsLoading.value = false
  }
}

// ── 表单弹窗 ──
const formDialog = ref(false)
const formLoading = ref(false)
const isEditing = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)
const formData = ref({
  group_id: null as number | null,
  user_id: null as number | null,
  wife_qq: null as number | null,
  wife_name: '',
  date: '',
})

const required = (v: unknown) => !!v || '此字段为必填'

function openCreateDialog() {
  isEditing.value = false
  editingId.value = null
  formData.value = { group_id: null, user_id: null, wife_qq: null, wife_name: '', date: '' }
  formDialog.value = true
}

function openEditDialog(item: WifeRecord) {
  isEditing.value = true
  editingId.value = item.id
  formData.value = {
    group_id: item.group_id,
    user_id: item.user_id,
    wife_qq: item.wife_qq,
    wife_name: item.wife_name,
    date: item.date,
  }
  formDialog.value = true
}

async function submitForm() {
  const valid = await formRef.value?.validate()
  if (!valid?.valid) return
  formLoading.value = true
  try {
    if (isEditing.value && editingId.value != null) {
      await jrlpApi.updateRecord({
        id: editingId.value,
        wife_qq: formData.value.wife_qq!,
        wife_name: formData.value.wife_name,
      })
    } else {
      await jrlpApi.createPreset({
        group_id: formData.value.group_id!,
        user_id: formData.value.user_id!,
        wife_qq: formData.value.wife_qq!,
        wife_name: formData.value.wife_name,
        date: formData.value.date,
      })
    }
    formDialog.value = false
    await loadPresets(1)
  } finally {
    formLoading.value = false
  }
}

// ── 删除 ──
const deleteDialog = ref(false)
const deleteLoading = ref(false)
const deleteTarget = ref<WifeRecord | null>(null)

function confirmDelete(item: WifeRecord) {
  deleteTarget.value = item
  deleteDialog.value = true
}

async function doDelete() {
  if (!deleteTarget.value) return
  deleteLoading.value = true
  try {
    await jrlpApi.deleteRecord({ id: deleteTarget.value.id })
    deleteDialog.value = false
    await loadPresets(1)
  } finally {
    deleteLoading.value = false
  }
}

onMounted(() => {
  loadLogs()
  loadPresets()
})
</script>
