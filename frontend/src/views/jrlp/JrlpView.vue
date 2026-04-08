<template>
  <PageLayout>
    <template #actions>
      <v-btn
        color="primary"
        variant="elevated"
        prepend-icon="mdi-pencil"
        @click="openSetWifeDialog"
      >
        手动设置老婆
      </v-btn>
    </template>

    <v-card flat>
      <!-- 筛选栏 -->
      <v-card-title class="d-flex align-center flex-wrap ga-2 pt-3">
        <v-text-field
          v-model.number="filter.group_id"
          label="群号"
          density="compact"
          variant="solo-filled"
          hide-details
          clearable
          type="number"
          style="max-width: 160px"
          @update:model-value="loadRecords(1)"
        />
        <v-text-field
          v-model.number="filter.user_id"
          label="用户 QQ"
          density="compact"
          variant="solo-filled"
          hide-details
          clearable
          type="number"
          style="max-width: 160px"
          @update:model-value="loadRecords(1)"
        />
        <v-text-field
          v-model="filter.date"
          label="日期"
          density="compact"
          variant="solo-filled"
          hide-details
          clearable
          type="date"
          style="max-width: 180px"
          @update:model-value="loadRecords(1)"
        />
      </v-card-title>

      <v-skeleton-loader v-if="loading && !items.length" type="table" class="pa-2" />
      <v-data-table
        v-else
        :headers="headers"
        :items="items"
        :items-length="total"
        :loading="loading"
        :page="page"
        :items-per-page="pageSize"
        :items-per-page-options="[10, 20, 50]"
        hover
        @update:page="loadRecords"
        @update:items-per-page="
          (v: number) => {
            pageSize = v
            loadRecords(1)
          }
        "
      >
        <!-- 群聊列 -->
        <template #[`item.group_id`]="{ item }">
          <div
            class="d-flex align-center ga-2 cursor-pointer"
            @click="openGroupInfo(item.group_id)"
          >
            <v-avatar size="24">
              <v-img :src="`https://p.qlogo.cn/gh/${item.group_id}/${item.group_id}/40`">
                <template #error>
                  <v-icon size="20">mdi-account-group</v-icon>
                </template>
              </v-img>
            </v-avatar>
            <span class="text-caption">{{ item.group_name }}（{{ item.group_id }}）</span>
          </div>
        </template>

        <!-- 抽取者列 -->
        <template #[`item.user_id`]="{ item }">
          <div
            class="d-flex align-center ga-2 cursor-pointer"
            @click="openUserInfo(item.user_id, item.group_id)"
          >
            <v-avatar size="24">
              <v-img :src="`https://q1.qlogo.cn/g?b=qq&nk=${item.user_id}&s=40`">
                <template #error>
                  <v-icon size="20">mdi-account-circle</v-icon>
                </template>
              </v-img>
            </v-avatar>
            <span class="text-caption">{{ item.user_nickname }}（{{ item.user_id }}）</span>
          </div>
        </template>

        <!-- 老婆列 -->
        <template #[`item.wife_qq`]="{ item }">
          <div
            class="d-flex align-center ga-2 cursor-pointer"
            @click="openUserInfo(item.wife_qq, item.group_id)"
          >
            <v-avatar size="24">
              <v-img :src="`https://q1.qlogo.cn/g?b=qq&nk=${item.wife_qq}&s=40`">
                <template #error>
                  <v-icon size="20">mdi-account-circle</v-icon>
                </template>
              </v-img>
            </v-avatar>
            <span class="text-caption">{{ item.wife_nickname }}（{{ item.wife_qq }}）</span>
          </div>
        </template>

        <!-- 抽取时间列 -->
        <template #[`item.drawn_at`]="{ item }">
          <v-chip :color="item.drawn_at ? 'success' : 'warning'" size="small" variant="tonal">
            {{ item.drawn_at ? formatTime(item.drawn_at) : '预设中' }}
          </v-chip>
        </template>

        <!-- 操作列 -->
        <template #[`item.actions`]="{ item }">
          <v-btn icon size="small" variant="text" @click="openEditDialog(item)">
            <v-icon>mdi-pencil</v-icon>
            <v-tooltip activator="parent" location="top">修改老婆</v-tooltip>
          </v-btn>
          <v-btn icon size="small" variant="text" color="error" @click="confirmDelete(item)">
            <v-icon>mdi-delete</v-icon>
            <v-tooltip activator="parent" location="top">删除记录</v-tooltip>
          </v-btn>
        </template>
      </v-data-table>
    </v-card>

    <!-- 手动设置老婆弹窗 -->
    <v-dialog v-model="setWifeDialog" max-width="480" persistent>
      <v-card>
        <v-card-title>手动设置老婆</v-card-title>
        <v-card-text>
          <v-form ref="setWifeFormRef">
            <v-text-field
              v-model.number="setWifeData.group_id"
              label="群号"
              type="number"
              :rules="[required]"
              class="mb-2"
            />
            <v-text-field
              v-model.number="setWifeData.user_id"
              label="抽取者 QQ"
              type="number"
              :rules="[required]"
              class="mb-2"
            />
            <v-text-field
              v-model.number="setWifeData.wife_qq"
              label="老婆 QQ"
              type="number"
              :rules="[required]"
              class="mb-2"
            />
            <v-text-field v-model="setWifeData.date" label="日期" type="date" :rules="[required]" />
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="setWifeDialog = false">取消</v-btn>
          <v-btn color="primary" :loading="setWifeLoading" @click="submitSetWife">确定</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 编辑老婆弹窗 -->
    <v-dialog v-model="editDialog" max-width="400" persistent>
      <v-card>
        <v-card-title>修改老婆</v-card-title>
        <v-card-text>
          <v-form ref="editFormRef">
            <v-text-field
              v-model.number="editData.wife_qq"
              label="新老婆 QQ"
              type="number"
              :rules="[required]"
            />
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="editDialog = false">取消</v-btn>
          <v-btn color="primary" :loading="editLoading" @click="submitEdit">确定</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 删除确认弹窗 -->
    <v-dialog v-model="deleteDialog" max-width="360">
      <v-card>
        <v-card-title>确认删除</v-card-title>
        <v-card-text>
          确定删除用户 {{ deleteTarget?.user_id }} 在群 {{ deleteTarget?.group_id }}
          {{ deleteTarget?.date }} 的老婆记录吗？
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="deleteDialog = false">取消</v-btn>
          <v-btn color="error" :loading="deleteLoading" @click="doDelete">删除</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 用户信息弹窗 -->
    <UserInfoCard v-model="userInfoDialog" :qq="userInfoQq" :group-id="userInfoGroupId" />

    <!-- 群聊信息弹窗 -->
    <GroupInfoCard v-model="groupInfoDialog" :group-id="groupInfoId" @open-user="openUserInfo" />
  </PageLayout>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import * as jrlpApi from '@/apis/jrlp'
import type { WifeRecord } from '@/apis/jrlp'
import PageLayout from '@/layouts/PageLayout.vue'
import GroupInfoCard from '@/components/GroupInfoCard.vue'
import UserInfoCard from '@/components/UserInfoCard.vue'
import { formatTime } from '@/utils/format'

// ── 记录列表 ──
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const items = ref<WifeRecord[]>([])
const total = ref(0)
const filter = ref<{ group_id: number | null; user_id: number | null; date: string | null }>({
  group_id: null,
  user_id: null,
  date: null,
})

const headers = [
  { title: '群聊', key: 'group_id', sortable: false },
  { title: '抽取者', key: 'user_id', sortable: false },
  { title: '老婆', key: 'wife_qq', sortable: false },
  { title: '日期', key: 'date', sortable: false },
  { title: '状态', key: 'drawn_at', sortable: false },
  { title: '操作', key: 'actions', sortable: false },
]

async function loadRecords(p = page.value) {
  loading.value = true
  page.value = p
  try {
    const result = await jrlpApi.listRecords({
      group_id: filter.value.group_id ?? undefined,
      user_id: filter.value.user_id ?? undefined,
      date: filter.value.date ?? undefined,
      page: p,
      page_size: pageSize.value,
    })
    items.value = result.items
    total.value = result.total
  } finally {
    loading.value = false
  }
}

// ── 公共表单校验 ──
const required = (v: unknown) => !!v || '此字段为必填'

// ── 手动设置老婆 ──
const setWifeDialog = ref(false)
const setWifeLoading = ref(false)
const setWifeFormRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)
const setWifeData = ref({
  group_id: null as number | null,
  user_id: null as number | null,
  wife_qq: null as number | null,
  date: '',
})

function openSetWifeDialog() {
  setWifeData.value = { group_id: null, user_id: null, wife_qq: null, date: '' }
  setWifeDialog.value = true
}

async function submitSetWife() {
  const valid = await setWifeFormRef.value?.validate()
  if (!valid?.valid) return
  setWifeLoading.value = true
  try {
    await jrlpApi.setWife({
      group_id: setWifeData.value.group_id!,
      user_id: setWifeData.value.user_id!,
      wife_qq: setWifeData.value.wife_qq!,
      date: setWifeData.value.date,
    })
    setWifeDialog.value = false
    await loadRecords(1)
  } finally {
    setWifeLoading.value = false
  }
}

// ── 编辑老婆 ──
const editDialog = ref(false)
const editLoading = ref(false)
const editingId = ref<number | null>(null)
const editFormRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(null)
const editData = ref({ wife_qq: null as number | null })

function openEditDialog(item: WifeRecord) {
  editingId.value = item.id
  editData.value = { wife_qq: item.wife_qq }
  editDialog.value = true
}

async function submitEdit() {
  const valid = await editFormRef.value?.validate()
  if (!valid?.valid) return
  if (editingId.value == null) return
  editLoading.value = true
  try {
    await jrlpApi.updateRecord({ id: editingId.value, wife_qq: editData.value.wife_qq! })
    editDialog.value = false
    await loadRecords()
  } finally {
    editLoading.value = false
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
    await loadRecords()
  } finally {
    deleteLoading.value = false
  }
}

// ── 用户信息弹窗 ──
const userInfoDialog = ref(false)
const userInfoQq = ref<number | null>(null)
const userInfoGroupId = ref<number | null>(null)

function openUserInfo(qq: number, groupId: number) {
  userInfoQq.value = qq
  userInfoGroupId.value = groupId
  userInfoDialog.value = true
}

// ── 群聊信息弹窗 ──
const groupInfoDialog = ref(false)
const groupInfoId = ref<number | null>(null)

function openGroupInfo(groupId: number) {
  groupInfoId.value = groupId
  groupInfoDialog.value = true
}

onMounted(() => {
  loadRecords()
})
</script>
