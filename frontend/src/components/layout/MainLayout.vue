<script setup lang="ts">
import { ref } from 'vue'
import { useTheme } from 'vuetify'
import AppBar from './AppBar.vue'
import SideNav from './SideNav.vue'

const drawer = ref(true)
const theme = useTheme()

function toggleTheme() {
  theme.global.name.value = theme.global.current.value.dark ? 'light' : 'dark'
}
</script>

<template>
  <v-app>
    <AppBar title="Texas Bot" @toggle-drawer="drawer = !drawer" @toggle-theme="toggleTheme" />
    <SideNav v-model="drawer" />
    <v-main>
      <v-container fluid>
        <router-view />
      </v-container>
    </v-main>
  </v-app>
</template>

