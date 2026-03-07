<script setup lang="ts">
defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const navItems = [
  { title: 'Dashboard', icon: 'mdi-view-dashboard', to: '/' },
  { title: 'Handlers', icon: 'mdi-puzzle', to: '/handlers' },
  { title: 'Groups', icon: 'mdi-account-group', to: '/groups' },
  { title: 'Logs', icon: 'mdi-text-box-outline', to: '/logs' },
  { title: 'Settings', icon: 'mdi-cog', to: '/settings' },
]
</script>

<template>
  <v-navigation-drawer
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <v-list-item
      title="Texas Bot"
      subtitle="QQ Bot Framework"
      class="pa-4"
    />
    <v-divider />
    <v-list nav density="default">
      <v-list-item
        v-for="item in navItems"
        :key="item.to"
        :title="item.title"
        :prepend-icon="item.icon"
        :to="item.to"
        exact
      />
    </v-list>
  </v-navigation-drawer>
</template>

