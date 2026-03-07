<script setup lang="ts">
import { useBotStore } from '@/stores/bot'
import { useAutoRefresh } from '@/composables/useAutoRefresh'
import StatusCard from '@/components/dashboard/StatusCard.vue'
import StatsChart from '@/components/dashboard/StatsChart.vue'
import RecentMessages from '@/components/dashboard/RecentMessages.vue'

const botStore = useBotStore()
useAutoRefresh(() => botStore.loadStatus(), 5000)
</script>

<template>
  <div>
    <h1 class="text-h4 mb-6">Dashboard</h1>

    <v-row class="mb-6">
      <v-col cols="12" sm="6" md="3">
        <StatusCard
          title="Status"
          :value="botStore.status?.wsConnected ? 'Online' : 'Offline'"
          icon="mdi-robot"
          :color="botStore.status?.wsConnected ? 'success' : 'error'"
        />
      </v-col>
      <v-col cols="12" sm="6" md="3">
        <StatusCard
          title="WS Connections"
          :value="botStore.status?.wsConnections ?? 0"
          icon="mdi-lan-connect"
          color="info"
        />
      </v-col>
      <v-col cols="12" sm="6" md="3">
        <StatusCard
          title="Handlers"
          :value="botStore.status?.handlersRegistered ?? 0"
          icon="mdi-puzzle"
          color="warning"
        />
      </v-col>
      <v-col cols="12" sm="6" md="3">
        <StatusCard
          title="Uptime"
          :value="botStore.status ? `${Math.floor(botStore.status.uptimeSeconds)}s` : '-'"
          icon="mdi-clock-outline"
          color="primary"
        />
      </v-col>
    </v-row>

    <v-row>
      <v-col cols="12" md="8">
        <StatsChart />
      </v-col>
      <v-col cols="12" md="4">
        <RecentMessages />
      </v-col>
    </v-row>
  </div>
</template>

