<template>
  <v-container fluid v-bind="$attrs" class="page-layout">
    <div class="mb-6">
      <v-breadcrumbs v-if="route.meta.group" :items="breadcrumbItems" class="pa-0 mb-2">
        <template #divider>
          <v-icon size="small">mdi-chevron-right</v-icon>
        </template>
        <template #item="{ item }">
          <v-breadcrumbs-item :disabled="item.disabled" class="text-body-2 text-medium-emphasis">
            {{ item.title }}
          </v-breadcrumbs-item>
        </template>
      </v-breadcrumbs>
      <div class="d-flex align-center">
        <v-icon size="32" class="mr-3">{{ route.meta.icon }}</v-icon>
        <h1 class="text-h4 font-weight-bold">{{ route.meta.title }}</h1>
        <v-spacer />
        <slot name="actions" />
      </div>
      <p class="text-body-2 text-medium-emphasis mt-1">{{ route.meta.subtitle }}</p>
    </div>
    <slot />
  </v-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

defineOptions({ inheritAttrs: false })

const route = useRoute()

const breadcrumbItems = computed(() => [
  { title: route.meta.group ?? '', disabled: true },
  { title: route.meta.title ?? '', disabled: true },
])
</script>

<style scoped>
.page-layout {
  padding-left: 24px !important;
  padding-right: 24px !important;
}
</style>
