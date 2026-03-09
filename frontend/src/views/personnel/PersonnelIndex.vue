<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <v-tabs v-model="activeTab" color="red" align-tabs="start" class="mb-4">
          <v-tab value="users" prepend-icon="mdi-account-group">用户管理</v-tab>
          <v-tab value="groups" prepend-icon="mdi-forum">群聊管理</v-tab>
          <v-tab value="admins" prepend-icon="mdi-shield-account">管理员</v-tab>
          <v-tab value="sync" prepend-icon="mdi-sync">数据同步</v-tab>
        </v-tabs>
      </v-col>
    </v-row>

    <v-tabs-window v-model="activeTab">
      <v-tabs-window-item value="users">
        <personnel-users />
      </v-tabs-window-item>
      <v-tabs-window-item value="groups">
        <personnel-groups />
      </v-tabs-window-item>
      <v-tabs-window-item value="admins">
        <personnel-admins />
      </v-tabs-window-item>
      <v-tabs-window-item value="sync">
        <personnel-sync />
      </v-tabs-window-item>
    </v-tabs-window>
  </v-container>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import PersonnelUsers from './PersonnelUsers.vue'
import PersonnelGroups from './PersonnelGroups.vue'
import PersonnelAdmins from './PersonnelAdmins.vue'
import PersonnelSync from './PersonnelSync.vue'

const activeTab = ref('users')
</script>

