import { createApp } from 'vue'
import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'

import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'
import 'unfonts.css'
import { createVuetify } from 'vuetify'
import { zhHans } from 'vuetify/locale'

import App from './App.vue'
import router from './router'

createApp(App)
  .use(createPinia().use(piniaPluginPersistedstate))
  .use(router)
  .use(
    createVuetify({
      icons: {
        defaultSet: 'mdi',
      },
      theme: {
        defaultTheme: 'light',
        themes: {
          light: {
            colors: {
              primary: '#455A64',
            },
          },
          dark: {
            colors: {
              primary: '#455A64',
            },
          },
        },
      },
      locale: {
        locale: 'zhHans',
        messages: { zhHans },
      },
    }),
  )
  .mount('#app')
