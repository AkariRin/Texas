/**
 * 通用分页状态管理 composable。
 *
 * 封装 page / pageSize / loadPage / refreshPage / onPageSizeChange / debouncedLoad，
 * 消除各列表页重复的分页样板代码。
 */

import { ref } from 'vue'
import { debounce } from '@/utils/ui'

/**
 * 创建通用分页状态。
 * @param fetchFn 加载数据的异步函数，接收 (page, pageSize) 参数
 * @param initialPageSize 初始每页条数，默认 20
 */
export function usePagination(
  fetchFn: (page: number, pageSize: number) => Promise<void> | void,
  initialPageSize = 20,
) {
  const page = ref(1)
  const pageSize = ref(initialPageSize)

  async function loadPage(p: number) {
    page.value = p
    await fetchFn(p, pageSize.value)
  }

  async function refreshPage() {
    await fetchFn(page.value, pageSize.value)
  }

  async function onPageSizeChange(size: number) {
    pageSize.value = size
    await loadPage(1)
  }

  const debouncedLoad = debounce(() => loadPage(1))

  return { page, pageSize, loadPage, refreshPage, onPageSizeChange, debouncedLoad }
}
