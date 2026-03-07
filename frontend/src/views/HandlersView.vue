<script setup lang="ts">
import { ref } from 'vue'
import { useHandlersStore } from '@/stores/handlers'
import { useAutoRefresh } from '@/composables/useAutoRefresh'
import type { ControllerInfo } from '@/types/handler'
import HandlerCard from '@/components/handlers/HandlerCard.vue'
import HandlerDetail from '@/components/handlers/HandlerDetail.vue'

const handlersStore = useHandlersStore()
useAutoRefresh(() => handlersStore.loadControllers(), 30000)

const detailOpen = ref(false)
const selectedController = ref<ControllerInfo | null>(null)

function showDetail(ctrl: ControllerInfo) {
  selectedController.value = ctrl
  detailOpen.value = true
}
</script>

<template>
  <div>
    <h1 class="text-h4 mb-6">Handlers</h1>

    <v-progress-linear v-if="handlersStore.loading" indeterminate class="mb-4" />

    <v-alert v-if="handlersStore.error" type="error" class="mb-4">
      {{ handlersStore.error }}
    </v-alert>

    <v-row>
      <v-col
        v-for="ctrl in handlersStore.controllers"
        :key="ctrl.name"
        cols="12"
        sm="6"
        md="4"
      >
        <HandlerCard :controller="ctrl" @click="showDetail(ctrl)" />
      </v-col>
    </v-row>

    <v-alert
      v-if="!handlersStore.loading && handlersStore.controllers.length === 0"
      type="info"
      variant="tonal"
    >
      No controllers registered yet. Create a handler in <code>src/handlers/</code>.
    </v-alert>

    <HandlerDetail v-model="detailOpen" :controller="selectedController" />
  </div>
</template>

