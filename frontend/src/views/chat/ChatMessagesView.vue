<template>
  <v-container fluid class="pa-0" style="height: calc(100vh - 64px)">
    <v-row no-gutters style="height: 100%">
      <!-- 左侧：群/私聊选择器 -->
      <v-col cols="3" style="height: 100%; border-right: 1px solid rgba(0, 0, 0, 0.12)">
        <div class="group-selector d-flex flex-column" style="height: 100%">
          <!-- 搜索栏 -->
          <div class="pa-2">
            <v-text-field
              v-model="selectorSearchQuery"
              density="compact"
              variant="solo-filled"
              placeholder="搜索群聊 / 用户..."
              prepend-inner-icon="mdi-magnify"
              hide-details
              clearable
            ></v-text-field>
          </div>

          <!-- 标签切换 -->
          <v-tabs v-model="selectorTab" density="compact" grow color="primary">
            <v-tab value="groups">
              <v-icon start>mdi-account-group</v-icon>
              群聊
            </v-tab>
            <v-tab value="private">
              <v-icon start>mdi-account</v-icon>
              私聊
            </v-tab>
          </v-tabs>

          <v-divider></v-divider>

          <!-- 列表 -->
          <v-list
            density="compact"
            nav
            class="flex-grow-1 overflow-y-auto selector-list"
            style="min-height: 0"
          >
            <template v-if="selectorTab === 'groups'">
              <v-list-item
                v-for="group in filteredGroups"
                :key="group.group_id"
                :active="selectedType === 'group' && selectedId === group.group_id"
                @click="selectGroup(group)"
                rounded="lg"
              >
                <template #prepend>
                  <v-avatar size="32">
                    <v-img :src="`https://p.qlogo.cn/gh/${group.group_id}/${group.group_id}/100`">
                      <template #error>
                        <v-icon>mdi-account-group</v-icon>
                      </template>
                    </v-img>
                  </v-avatar>
                </template>
                <v-list-item-title class="text-body-2">{{ group.group_name }}</v-list-item-title>
                <v-list-item-subtitle class="text-caption">
                  {{ group.group_id }} &middot; {{ group.member_count }} 人
                </v-list-item-subtitle>
              </v-list-item>
              <v-list-item v-if="filteredGroups.length === 0">
                <v-list-item-title class="text-medium-emphasis text-center text-caption">
                  {{ selectorSearchQuery ? '无匹配结果' : '暂无群聊数据' }}
                </v-list-item-title>
              </v-list-item>
            </template>

            <template v-else>
              <v-list-item
                v-for="user in filteredUsers"
                :key="user.qq"
                :active="selectedType === 'private' && selectedId === user.qq"
                @click="selectUser(user)"
                rounded="lg"
              >
                <template #prepend>
                  <v-avatar size="32">
                    <v-img :src="`https://q1.qlogo.cn/g?b=qq&nk=${user.qq}&s=100`">
                      <template #error>
                        <v-icon>mdi-account</v-icon>
                      </template>
                    </v-img>
                  </v-avatar>
                </template>
                <v-list-item-title class="text-body-2">{{ user.nickname }}</v-list-item-title>
                <v-list-item-subtitle class="text-caption">{{ user.qq }}</v-list-item-subtitle>
              </v-list-item>
              <v-list-item v-if="filteredUsers.length === 0">
                <v-list-item-title class="text-medium-emphasis text-center text-caption">
                  {{ selectorSearchQuery ? '无匹配结果' : '暂无私聊数据' }}
                </v-list-item-title>
              </v-list-item>
            </template>
          </v-list>
        </div>
      </v-col>

      <!-- 右侧：消息区域 -->
      <v-col cols="9" class="d-flex flex-column" style="height: 100%">
        <!-- 未选择会话 -->
        <div
          v-if="!currentSession"
          class="d-flex flex-column align-center justify-center flex-grow-1 text-medium-emphasis"
        >
          <v-icon size="80" color="grey-lighten-1">mdi-message-text-outline</v-icon>
          <p class="text-h6 mt-4">选择一个会话查看消息</p>
          <p class="text-body-2">从左侧选择群聊或私聊</p>
        </div>

        <!-- 已选择会话 -->
        <template v-else>
          <!-- 顶部信息栏 -->
          <v-toolbar density="compact" flat color="transparent">
            <v-toolbar-title class="text-body-1 font-weight-medium">
              <v-icon class="mr-1" size="small">
                {{ currentSession.type === 'group' ? 'mdi-account-group' : 'mdi-account' }}
              </v-icon>
              {{ currentSession.name }}
              <span class="text-medium-emphasis ml-1">({{ currentSession.id }})</span>
            </v-toolbar-title>
            <v-spacer></v-spacer>

            <!-- 日期跳转 -->
            <v-menu :close-on-content-click="false">
              <template #activator="{ props }">
                <v-btn icon="mdi-calendar" size="small" variant="elevated" v-bind="props"></v-btn>
              </template>
              <v-date-picker @update:model-value="onDateJump" color="primary"></v-date-picker>
            </v-menu>
          </v-toolbar>

          <!-- 搜索 / 筛选栏 -->
          <div class="px-4 pb-2">
            <v-row dense>
              <v-col cols="5">
                <v-text-field
                  v-model="searchKeyword"
                  density="compact"
                  variant="solo-filled"
                  placeholder="搜索消息..."
                  prepend-inner-icon="mdi-magnify"
                  hide-details
                  clearable
                  @keyup.enter="doSearch"
                  @click:clear="clearSearch"
                ></v-text-field>
              </v-col>
              <v-col cols="3">
                <v-text-field
                  v-model="filterUserId"
                  density="compact"
                  variant="solo-filled"
                  placeholder="按 QQ 号筛选"
                  hide-details
                  clearable
                  type="number"
                ></v-text-field>
              </v-col>
              <v-col cols="2">
                <v-btn
                  block
                  variant="elevated"
                  color="primary"
                  @click="doSearch"
                  :loading="store.messagesLoading"
                >
                  搜索
                </v-btn>
              </v-col>
              <v-col cols="2">
                <v-btn block variant="elevated" @click="clearSearch"> 重置 </v-btn>
              </v-col>
            </v-row>
          </div>

          <v-divider></v-divider>

          <!-- 消息列表 -->
          <div ref="messageContainer" class="flex-grow-1 overflow-y-auto pa-4" @scroll="onScroll">
            <!-- 加载更多按钮 -->
            <div v-if="store.hasMore && store.messages.length > 0" class="text-center mb-4">
              <v-btn
                variant="elevated"
                size="small"
                color="primary"
                :loading="store.messagesLoading"
                @click="loadMore"
              >
                加载更早消息
              </v-btn>
            </div>

            <!-- 消息卡片 -->
            <div
              v-for="msg in reversedMessages"
              :key="`${msg.id}-${msg.created_at}`"
              class="message-bubble d-flex align-start mb-3"
            >
              <!-- 头像 -->
              <v-avatar size="36" class="flex-shrink-0 mr-2">
                <v-img
                  :src="`https://q1.qlogo.cn/g?b=qq&nk=${msg.user_id}&s=100`"
                  :alt="msg.sender_nickname"
                >
                  <template #error>
                    <v-icon>mdi-account-circle</v-icon>
                  </template>
                </v-img>
              </v-avatar>

              <!-- 内容 -->
              <div class="message-content" style="max-width: 70%">
                <!-- 昵称与时间 -->
                <div class="d-flex align-center ga-2 mb-1">
                  <span class="text-caption font-weight-medium">
                    {{ msg.sender_card || msg.sender_nickname || String(msg.user_id) }}
                  </span>
                  <span v-if="msg.sender_role && msg.sender_role !== 'member'" class="text-caption">
                    <v-chip
                      size="x-small"
                      variant="elevated"
                      :color="getRoleColor(msg.sender_role)"
                      >{{ getRoleLabel(msg.sender_role) }}</v-chip
                    >
                  </span>
                  <span class="text-caption text-medium-emphasis">
                    {{ formatMsgTime(msg.created_at) }}
                  </span>
                </div>

                <!-- 无法解析的消息 -->
                <v-card
                  v-if="!msg.segments || msg.segments.length === 0"
                  elevation="2"
                  rounded="lg"
                  class="message-body"
                  color="red-lighten-5"
                  variant="elevated"
                >
                  <div class="d-flex align-center py-2 px-3" style="gap: 8px">
                    <v-icon size="small" color="red-darken-1">mdi-alert-circle-outline</v-icon>
                    <span class="text-body-2 text-red-darken-1">消息无法解析</span>
                  </div>
                </v-card>

                <!-- 正常消息卡片 -->
                <v-card
                  v-else
                  elevation="2"
                  rounded="lg"
                  class="message-body"
                  :color="isSelf(msg) ? 'blue-lighten-4' : undefined"
                >
                  <!-- 消息段渲染 -->
                  <div class="d-flex align-center flex-wrap py-2 px-3" style="gap: 8px">
                    <template v-for="seg in msg.segments" :key="seg">
                      <span
                        v-if="seg.type === 'text'"
                        class="message-text"
                        v-html="escapeHtml(String(seg.data?.text ?? ''))"
                      ></span>
                      <v-img
                        v-else-if="seg.type === 'image'"
                        :src="getImageSrc(seg)"
                        max-width="200"
                        max-height="200"
                        class="rounded message-image cursor-pointer"
                        @click="openImagePreview(getImageSrc(seg))"
                      >
                        <template #placeholder>
                          <div class="d-flex align-center justify-center fill-height">
                            <v-progress-circular
                              indeterminate
                              size="24"
                              color="grey"
                            ></v-progress-circular>
                          </div>
                        </template>
                        <template #error>
                          <div
                            class="d-flex align-center justify-center fill-height bg-grey-lighten-3 rounded pa-2"
                          >
                            <v-icon color="grey">mdi-image-broken</v-icon>
                          </div>
                        </template>
                      </v-img>
                      <v-chip
                        v-else-if="seg.type === 'at'"
                        size="small"
                        color="blue-lighten-4"
                        variant="elevated"
                        class="mx-1 cursor-pointer"
                        :class="{ 'at-chip-clickable': seg.data?.qq !== 'all' }"
                        @click="onAtChipClick(seg.data?.qq)"
                      >
                        @{{ getAtDisplayName(seg.data?.qq) }}
                      </v-chip>
                      <v-chip
                        v-else-if="seg.type === 'reply'"
                        size="x-small"
                        color="grey-lighten-2"
                        variant="elevated"
                        prepend-icon="mdi-reply"
                        class="mr-1"
                      >
                        回复 #{{ seg.data?.id }}
                      </v-chip>
                      <span
                        v-else-if="seg.type === 'face'"
                        class="message-face"
                        :title="`表情 ${seg.data?.id}`"
                      >
                        [表情{{ seg.data?.id }}]
                      </span>
                      <!-- 商城表情 mface -->
                      <v-img
                        v-else-if="seg.type === 'mface' && seg.data?.url"
                        :src="String(seg.data.url)"
                        max-width="120"
                        max-height="120"
                        class="rounded message-image cursor-pointer"
                        :title="String(seg.data?.summary ?? '商城表情')"
                        @click="openImagePreview(String(seg.data.url))"
                      >
                        <template #error>
                          <v-chip size="x-small" color="amber-lighten-4" variant="elevated">
                            {{ seg.data?.summary ?? '[商城表情]' }}
                          </v-chip>
                        </template>
                      </v-img>
                      <v-chip
                        v-else-if="seg.type === 'mface'"
                        size="small"
                        color="amber-lighten-4"
                        variant="elevated"
                      >
                        {{ seg.data?.summary ?? '[商城表情]' }}
                      </v-chip>
                      <!-- 视频 -->
                      <v-card
                        v-else-if="seg.type === 'video'"
                        variant="outlined"
                        rounded="lg"
                        class="pa-2"
                        max-width="240"
                      >
                        <div class="d-flex align-center" style="gap: 8px">
                          <v-icon color="blue">mdi-video-outline</v-icon>
                          <div>
                            <div class="text-body-2">{{ seg.data?.name || '视频' }}</div>
                            <div
                              v-if="seg.data?.file_size"
                              class="text-caption text-medium-emphasis"
                            >
                              {{ formatFileSize(Number(seg.data.file_size)) }}
                            </div>
                          </div>
                        </div>
                        <video
                          v-if="seg.data?.url || seg.data?.file"
                          :src="String(seg.data?.url ?? seg.data?.file ?? '')"
                          controls
                          preload="metadata"
                          class="rounded mt-1"
                          style="max-width: 220px; max-height: 200px"
                        ></video>
                      </v-card>
                      <!-- 语音 -->
                      <v-card
                        v-else-if="seg.type === 'record'"
                        variant="outlined"
                        rounded="lg"
                        class="pa-2"
                        max-width="260"
                      >
                        <div class="d-flex align-center" style="gap: 8px">
                          <v-icon color="green">mdi-microphone</v-icon>
                          <span class="text-body-2">语音消息</span>
                        </div>
                        <audio
                          v-if="seg.data?.url || seg.data?.file"
                          :src="String(seg.data?.url ?? seg.data?.file ?? '')"
                          controls
                          preload="metadata"
                          class="mt-1"
                          style="max-width: 240px"
                        ></audio>
                      </v-card>
                      <!-- 文件 -->
                      <v-chip
                        v-else-if="seg.type === 'file'"
                        color="blue-grey-lighten-4"
                        variant="elevated"
                        prepend-icon="mdi-file-outline"
                      >
                        <span class="text-body-2">{{ seg.data?.name || '文件' }}</span>
                        <span
                          v-if="seg.data?.file_size"
                          class="text-caption text-medium-emphasis ml-1"
                        >
                          ({{ formatFileSize(Number(seg.data.file_size)) }})
                        </span>
                      </v-chip>
                      <!-- 转发消息 -->
                      <v-chip
                        v-else-if="seg.type === 'forward'"
                        size="small"
                        color="teal-lighten-4"
                        variant="elevated"
                        prepend-icon="mdi-share"
                      >
                        [合并转发]
                      </v-chip>
                      <!-- JSON 卡片消息 -->
                      <v-chip
                        v-else-if="seg.type === 'json'"
                        size="small"
                        color="purple-lighten-4"
                        variant="elevated"
                        prepend-icon="mdi-code-json"
                      >
                        [卡片消息]
                      </v-chip>
                      <!-- 戳一戳 -->
                      <v-chip
                        v-else-if="seg.type === 'poke'"
                        size="small"
                        color="pink-lighten-4"
                        variant="elevated"
                        prepend-icon="mdi-hand-pointing-right"
                      >
                        [戳一戳]
                      </v-chip>
                      <!-- 骰子 / 猜拳 -->
                      <v-chip
                        v-else-if="seg.type === 'dice'"
                        size="small"
                        color="orange-lighten-4"
                        variant="elevated"
                        prepend-icon="mdi-dice-multiple"
                      >
                        [骰子] {{ seg.data?.result != null ? `点数: ${seg.data.result}` : '' }}
                      </v-chip>
                      <v-chip
                        v-else-if="seg.type === 'rps'"
                        size="small"
                        color="orange-lighten-4"
                        variant="elevated"
                        prepend-icon="mdi-hand-back-right"
                      >
                        [猜拳] {{ seg.data?.result != null ? `结果: ${seg.data.result}` : '' }}
                      </v-chip>
                      <!-- Markdown -->
                      <div
                        v-else-if="seg.type === 'markdown'"
                        class="message-text"
                        v-html="escapeHtml(String(seg.data?.content ?? ''))"
                      ></div>
                      <!-- 未知消息段类型 -->
                      <v-chip
                        v-else
                        size="x-small"
                        color="red-lighten-4"
                        text-color="red-darken-1"
                        variant="elevated"
                        prepend-icon="mdi-alert-circle-outline"
                      >
                        无法解析: {{ seg.type }}
                      </v-chip>
                    </template>
                  </div>
                </v-card>
              </div>

              <!-- 详情按钮 -->
              <v-btn
                icon="mdi-information-outline"
                size="x-small"
                variant="text"
                color="grey"
                class="ml-1 mt-5 flex-shrink-0 detail-btn"
                @click="showDetail(msg)"
              ></v-btn>
            </div>

            <!-- 空状态 -->
            <div
              v-if="!store.messagesLoading && store.messages.length === 0"
              class="d-flex flex-column align-center justify-center text-medium-emphasis"
              style="min-height: 200px"
            >
              <v-icon size="48" color="grey-lighten-1">mdi-message-off-outline</v-icon>
              <p class="mt-2">暂无消息</p>
            </div>

            <!-- 加载中 -->
            <div v-if="store.messagesLoading && store.messages.length === 0" class="pa-4">
              <div v-for="n in 6" :key="n" class="d-flex mb-3">
                <v-skeleton-loader
                  type="list-item-avatar-two-line"
                  :width="n % 2 === 0 ? '60%' : '45%'"
                />
              </div>
            </div>
          </div>
        </template>
      </v-col>
    </v-row>

    <!-- 消息详情对话框 -->
    <v-dialog v-model="detailDialog" max-width="640" scrollable>
      <v-card rounded="lg">
        <v-card-title class="d-flex align-center">
          <v-icon class="mr-2" size="small">mdi-code-json</v-icon>
          消息详情
          <v-spacer></v-spacer>
          <v-btn icon="mdi-close" size="small" variant="text" @click="detailDialog = false"></v-btn>
        </v-card-title>
        <v-divider></v-divider>
        <v-card-text class="pa-0">
          <v-table density="compact">
            <tbody>
              <tr>
                <td class="text-caption font-weight-bold" style="width: 140px">ID</td>
                <td class="text-caption">{{ detailMessage?.id }}</td>
              </tr>
              <tr>
                <td class="text-caption font-weight-bold">Message ID</td>
                <td class="text-caption">{{ detailMessage?.message_id }}</td>
              </tr>
              <tr>
                <td class="text-caption font-weight-bold">消息类型</td>
                <td class="text-caption">{{ formatMessageType(detailMessage?.message_type) }}</td>
              </tr>
              <tr>
                <td class="text-caption font-weight-bold">群号</td>
                <td class="text-caption">{{ detailMessage?.group_id ?? '-' }}</td>
              </tr>
              <tr>
                <td class="text-caption font-weight-bold">发送者 QQ</td>
                <td class="text-caption">{{ detailMessage?.user_id }}</td>
              </tr>
              <tr>
                <td class="text-caption font-weight-bold">昵称</td>
                <td class="text-caption">{{ detailMessage?.sender_nickname }}</td>
              </tr>
              <tr>
                <td class="text-caption font-weight-bold">群名片</td>
                <td class="text-caption">{{ detailMessage?.sender_card ?? '-' }}</td>
              </tr>
              <tr>
                <td class="text-caption font-weight-bold">角色</td>
                <td class="text-caption">{{ detailMessage?.sender_role ?? '-' }}</td>
              </tr>
              <tr>
                <td class="text-caption font-weight-bold">原始消息</td>
                <td class="text-caption" style="white-space: pre-wrap; word-break: break-all">
                  {{ detailMessage?.raw_message }}
                </td>
              </tr>
              <tr>
                <td class="text-caption font-weight-bold">创建时间</td>
                <td class="text-caption">{{ detailMessage?.created_at ?? '-' }}</td>
              </tr>
              <tr>
                <td class="text-caption font-weight-bold">存储时间</td>
                <td class="text-caption">{{ detailMessage?.stored_at ?? '-' }}</td>
              </tr>
            </tbody>
          </v-table>
          <v-divider></v-divider>
          <div class="pa-3">
            <div class="text-caption font-weight-bold mb-1">Segments (JSON)</div>
            <pre class="text-caption detail-json pa-2 rounded bg-grey-lighten-4">{{
              JSON.stringify(detailMessage?.segments, null, 2)
            }}</pre>
          </div>
        </v-card-text>
      </v-card>
    </v-dialog>

    <!-- 群成员详情对话框 -->
    <v-dialog v-model="memberDetailDialog" max-width="480" scrollable>
      <v-card rounded="lg">
        <v-card-title class="d-flex align-center">
          <v-icon class="mr-2" size="small">mdi-account-details</v-icon>
          群成员详情
          <v-spacer></v-spacer>
          <v-btn
            icon="mdi-close"
            size="small"
            variant="text"
            @click="memberDetailDialog = false"
          ></v-btn>
        </v-card-title>
        <v-divider></v-divider>
        <v-card-text class="pa-0">
          <!-- 加载中 (skeleton) -->
          <div v-if="memberDetailLoading">
            <!-- 头部骨架：头像 + 文字 -->
            <div class="d-flex align-center pa-4" style="gap: 16px">
              <v-skeleton-loader
                type="avatar"
                style="width: 64px; height: 64px"
                boilerplate
              ></v-skeleton-loader>
              <div class="flex-grow-1">
                <v-skeleton-loader type="heading" class="mb-1"></v-skeleton-loader>
                <v-skeleton-loader type="text" style="max-width: 160px"></v-skeleton-loader>
                <div class="d-flex ga-2 mt-2">
                  <v-skeleton-loader type="chip" style="width: 72px"></v-skeleton-loader>
                  <v-skeleton-loader type="chip" style="width: 72px"></v-skeleton-loader>
                </div>
              </div>
            </div>
            <v-divider></v-divider>
            <!-- 表格骨架 -->
            <div class="pa-2">
              <v-skeleton-loader type="table-row@6"></v-skeleton-loader>
            </div>
          </div>
          <!-- 未找到 -->
          <div
            v-else-if="!memberDetail"
            class="d-flex flex-column align-center justify-center pa-8 text-medium-emphasis"
          >
            <v-icon size="48" color="grey-lighten-1">mdi-account-off-outline</v-icon>
            <p class="mt-2 text-body-2">未找到该成员信息</p>
          </div>
          <!-- 成员信息 -->
          <template v-else>
            <!-- 头部头像 + 名称 -->
            <div class="d-flex align-center pa-4" style="gap: 16px">
              <v-avatar size="64">
                <v-img :src="`https://q1.qlogo.cn/g?b=qq&nk=${memberDetail.qq}&s=100`">
                  <template #error>
                    <v-icon size="40">mdi-account-circle</v-icon>
                  </template>
                </v-img>
              </v-avatar>
              <div>
                <div class="text-h6">{{ memberDetail.card || memberDetail.nickname }}</div>
                <div v-if="memberDetail.card" class="text-body-2 text-medium-emphasis">
                  昵称: {{ memberDetail.nickname }}
                </div>
                <div class="d-flex align-center ga-2 mt-1">
                  <v-chip size="small" variant="elevated" :color="getRoleColor(memberDetail.role)">
                    {{ formatMemberRole(memberDetail.role) }}
                  </v-chip>
                  <v-chip size="small" variant="outlined" color="grey">
                    {{ formatMemberRelation(memberDetail.relation) }}
                  </v-chip>
                </div>
              </div>
            </div>
            <v-divider></v-divider>
            <!-- 详细信息表格 -->
            <v-table density="compact">
              <tbody>
                <tr>
                  <td class="text-caption font-weight-bold" style="width: 120px">QQ 号</td>
                  <td class="text-caption">{{ memberDetail.qq }}</td>
                </tr>
                <tr>
                  <td class="text-caption font-weight-bold">群名片</td>
                  <td class="text-caption">{{ memberDetail.card || '-' }}</td>
                </tr>
                <tr>
                  <td class="text-caption font-weight-bold">昵称</td>
                  <td class="text-caption">{{ memberDetail.nickname }}</td>
                </tr>
                <tr>
                  <td class="text-caption font-weight-bold">群角色</td>
                  <td class="text-caption">{{ formatMemberRole(memberDetail.role) }}</td>
                </tr>
                <tr>
                  <td class="text-caption font-weight-bold">关系</td>
                  <td class="text-caption">{{ formatMemberRelation(memberDetail.relation) }}</td>
                </tr>
                <tr>
                  <td class="text-caption font-weight-bold">专属头衔</td>
                  <td class="text-caption">{{ memberDetail.title || '-' }}</td>
                </tr>
                <tr>
                  <td class="text-caption font-weight-bold">入群时间</td>
                  <td class="text-caption">{{ formatTimestamp(memberDetail.join_time) }}</td>
                </tr>
                <tr>
                  <td class="text-caption font-weight-bold">最后活跃</td>
                  <td class="text-caption">{{ formatTimestamp(memberDetail.last_active_time) }}</td>
                </tr>
              </tbody>
            </v-table>
          </template>
        </v-card-text>
      </v-card>
    </v-dialog>

    <!-- 图片预览对话框 -->
    <v-dialog v-model="imagePreviewDialog" max-width="90vw" content-class="image-preview-dialog">
      <v-card
        flat
        color="transparent"
        class="d-flex align-center justify-center"
        @click="imagePreviewDialog = false"
      >
        <v-img
          :src="imagePreviewSrc"
          max-width="90vw"
          max-height="90vh"
          contain
          class="rounded-lg elevation-8"
        >
          <template #placeholder>
            <div class="d-flex align-center justify-center fill-height">
              <v-progress-circular indeterminate size="48" color="white"></v-progress-circular>
            </div>
          </template>
        </v-img>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useChatStore } from '@/stores/chat'
import { fetchGroups, fetchUsers, fetchGroupMembers } from '@/apis/personnel'
import type { GroupItem, UserItem, GroupMemberItem } from '@/apis/personnel'
import type { ChatMessage } from '@/apis/chat'

const store = useChatStore()

// 反转消息列表：后端返回 newest-first，展示需要 oldest-first（新消息在底部）
const reversedMessages = computed(() => [...store.messages].reverse())

// ── 会话选择器状态 ──

const selectorSearchQuery = ref('')
const selectorTab = ref('groups')
const selectorGroups = ref<GroupItem[]>([])
const selectorUsers = ref<UserItem[]>([])
const selectedType = ref<'group' | 'private'>('group')
const selectedId = ref<number | null>(null)

const filteredGroups = computed(() => {
  if (!selectorSearchQuery.value) return selectorGroups.value
  const q = selectorSearchQuery.value.toLowerCase()
  return selectorGroups.value.filter(
    (g) => g.group_name.toLowerCase().includes(q) || String(g.group_id).includes(q),
  )
})

const filteredUsers = computed(() => {
  if (!selectorSearchQuery.value) return selectorUsers.value
  const q = selectorSearchQuery.value.toLowerCase()
  return selectorUsers.value.filter(
    (u) => u.nickname.toLowerCase().includes(q) || String(u.qq).includes(q),
  )
})

function selectGroup(group: GroupItem) {
  selectedType.value = 'group'
  selectedId.value = group.group_id
  onSessionSelect('group', group.group_id, group.group_name)
}

function selectUser(user: UserItem) {
  selectedType.value = 'private'
  selectedId.value = user.qq
  onSessionSelect('private', user.qq, user.nickname)
}

async function loadSelectorData() {
  try {
    const [groupResult, userResult] = await Promise.all([
      fetchGroups({ page: 1, page_size: 100 }),
      fetchUsers({ page: 1, page_size: 100, relation: 'friend' }),
    ])
    selectorGroups.value = groupResult.items
    selectorUsers.value = userResult.items
  } catch {
    // 静默失败
  }
}

// ── 消息区域状态 ──

const currentSession = ref<{
  type: 'group' | 'private'
  id: number
  name: string
} | null>(null)

const searchKeyword = ref('')
const filterUserId = ref<string>('')
const messageContainer = ref<HTMLElement | null>(null)

// ── 消息详情对话框 ──

const detailDialog = ref(false)
const detailMessage = ref<ChatMessage | null>(null)

function showDetail(msg: ChatMessage) {
  detailMessage.value = msg
  detailDialog.value = true
}

function formatMessageType(type: number | undefined): string {
  switch (type) {
    case 1:
      return '群消息'
    case 2:
      return '私聊消息'
    case 3:
      return '自己发送'
    default:
      return String(type ?? '-')
  }
}

// ── @成员名片映射 & 成员详情弹窗 ──

/** 从已加载消息中构建 user_id -> 群名片/昵称 映射 */
const memberNameMap = computed(() => {
  const map = new Map<number, string>()
  for (const msg of store.messages) {
    if (msg.user_id && !map.has(msg.user_id)) {
      const name = msg.sender_card || msg.sender_nickname
      if (name) map.set(msg.user_id, name)
    }
  }
  return map
})

function getAtDisplayName(qq: unknown): string {
  if (qq === 'all') return '全体成员'
  const qqNum = Number(qq)
  if (isNaN(qqNum)) return String(qq)
  return memberNameMap.value.get(qqNum) || String(qq)
}

const memberDetailDialog = ref(false)
const memberDetailLoading = ref(false)
const memberDetail = ref<GroupMemberItem | null>(null)

async function onAtChipClick(qq: unknown) {
  if (qq === 'all') return
  if (!currentSession.value || currentSession.value.type !== 'group') return

  const qqNum = Number(qq)
  if (isNaN(qqNum)) return

  memberDetail.value = null
  memberDetailLoading.value = true
  memberDetailDialog.value = true

  try {
    const result = await fetchGroupMembers(currentSession.value.id, {
      page: 1,
      page_size: 1,
      qq: qqNum,
    })
    if (result.items.length > 0) {
      memberDetail.value = result.items[0]
    }
  } catch {
    // 静默失败
  } finally {
    memberDetailLoading.value = false
  }
}

function formatMemberRole(role: string | undefined): string {
  switch (role) {
    case 'owner':
      return '群主'
    case 'admin':
      return '管理员'
    case 'member':
      return '普通成员'
    default:
      return role ?? '-'
  }
}

function formatMemberRelation(relation: string | undefined): string {
  switch (relation) {
    case 'friend':
      return '好友'
    case 'group_member':
      return '群成员'
    case 'stranger':
      return '陌生人'
    case 'admin':
      return '管理员'
    default:
      return relation ?? '-'
  }
}

function formatTimestamp(ts: number | undefined): string {
  if (!ts || ts <= 0) return '-'
  const d = new Date(ts * 1000)
  return d.toLocaleString('zh-CN')
}

// ── 消息气泡辅助 ──

function isSelf(msg: ChatMessage): boolean {
  return msg.message_type === 3 // SELF_SENT
}

function getRoleColor(role: string | undefined): string {
  switch (role) {
    case 'owner':
      return 'amber'
    case 'admin':
      return 'blue'
    default:
      return 'grey'
  }
}

function getRoleLabel(role: string | undefined): string {
  switch (role) {
    case 'owner':
      return '群主'
    case 'admin':
      return '管理员'
    default:
      return role ?? ''
  }
}

function formatMsgTime(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  const time = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  if (isToday) return time
  return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }) + ' ' + time
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
}

// ── 图片预览 ──

const imagePreviewDialog = ref(false)
const imagePreviewSrc = ref('')

/**
 * 从 image 类型的消息段中解析图片地址。
 * 优先使用 url，其次 file（可能是 http/https URL 或 base64）。
 */
function getImageSrc(seg: { data?: Record<string, unknown> }): string {
  const url = seg.data?.url
  if (url && typeof url === 'string' && url.length > 0) return url
  const file = seg.data?.file
  if (file && typeof file === 'string' && file.length > 0) return file
  const path = seg.data?.path
  if (path && typeof path === 'string' && path.length > 0) return path
  return ''
}

function openImagePreview(src: string) {
  if (!src) return
  imagePreviewSrc.value = src
  imagePreviewDialog.value = true
}

/**
 * 格式化文件大小为可读字符串。
 */
function formatFileSize(bytes: number): string {
  if (bytes <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const size = bytes / Math.pow(1024, i)
  return `${size.toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

// ── 会话与消息操作 ──

function onSessionSelect(type: 'group' | 'private', id: number, name: string) {
  currentSession.value = { type, id, name }
  searchKeyword.value = ''
  filterUserId.value = ''
  store.clearMessages()
  loadMessages(true)
}

function scrollToBottom() {
  nextTick(() => {
    const el = messageContainer.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

async function loadMessages(scrollBottom = false) {
  if (!currentSession.value) return

  const params: {
    keyword?: string
    userId?: number
    limit?: number
  } = { limit: 50 }

  if (searchKeyword.value) params.keyword = searchKeyword.value
  if (filterUserId.value) params.userId = Number(filterUserId.value)

  if (currentSession.value.type === 'group') {
    await store.loadGroupMessages(currentSession.value.id, params)
  } else {
    await store.loadPrivateMessages(currentSession.value.id, { limit: params.limit })
  }

  if (scrollBottom) scrollToBottom()
}

function loadMore() {
  if (!currentSession.value || store.messages.length === 0) return

  const oldest = store.messages[store.messages.length - 1]
  if (!oldest?.created_at) return

  const params: {
    before: string
    keyword?: string
    userId?: number
    limit: number
  } = {
    before: oldest.created_at,
    limit: 50,
  }

  if (searchKeyword.value) params.keyword = searchKeyword.value
  if (filterUserId.value) params.userId = Number(filterUserId.value)

  if (currentSession.value.type === 'group') {
    store.loadGroupMessages(currentSession.value.id, params)
  } else {
    store.loadPrivateMessages(currentSession.value.id, { before: oldest.created_at, limit: 50 })
  }
}

function doSearch() {
  store.clearMessages()
  loadMessages()
}

function clearSearch() {
  searchKeyword.value = ''
  filterUserId.value = ''
  store.clearMessages()
  loadMessages()
}

function onDateJump(date: unknown) {
  if (!currentSession.value || !date) return

  const d = date instanceof Date ? date : new Date(String(date))
  const isoDate = d.toISOString()

  store.clearMessages()
  if (currentSession.value.type === 'group') {
    store.loadGroupMessages(currentSession.value.id, {
      startDate: isoDate,
      limit: 50,
    })
  }
}

function onScroll() {
  const el = messageContainer.value
  if (!el) return
  if (el.scrollTop < 100 && store.hasMore && !store.messagesLoading) {
    loadMore()
  }
}

onMounted(() => {
  loadSelectorData()
})
</script>

<style scoped>
.group-selector :deep(.v-tabs) {
  flex: none;
}

.group-selector :deep(.v-tabs .v-window) {
  display: none;
}

.selector-list {
  padding-top: 4px !important;
  padding-bottom: 0 !important;
}

.message-bubble {
  padding: 0 4px;
}

.message-body {
  text-align: left;
  max-width: 100%;
}

.message-text {
  white-space: pre-wrap;
  word-break: break-word;
}

.message-image {
  border: 1px solid rgba(0, 0, 0, 0.1);
}

.message-face {
  color: #f59e0b;
  font-size: 0.9em;
}

.detail-btn {
  opacity: 0;
  transition: opacity 0.15s ease;
}

.message-bubble:hover .detail-btn {
  opacity: 1;
}

.at-chip-clickable:hover {
  filter: brightness(0.92);
  text-decoration: underline;
}

.detail-json {
  overflow-x: auto;
  max-height: 300px;
  font-family: monospace;
  white-space: pre;
  word-break: break-all;
}
</style>
