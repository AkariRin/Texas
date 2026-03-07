/** 统计数据状态管理。 */

import { ref } from 'vue'
import { defineStore } from 'pinia'

export const useStatsStore = defineStore('stats', () => {
  const messageCount = ref({ today: 0, total: 0 })
  const activeGroups = ref(0)
  const activeUsers = ref(0)

  return { messageCount, activeGroups, activeUsers }
})

