import { createApp } from 'vue'
import { createPinia } from 'pinia'

import 'vuetify/styles'
import 'unfonts.css'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'

import App from './App.vue'
import router from './router'

createApp(App)
  .use(createPinia())
  .use(router)
  .use(
    createVuetify({
      components,
      directives,
    })
  )
  .mount('#app')
