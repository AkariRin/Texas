import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { usePagination } from '@/composables/usePagination'

describe('usePagination', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('初始值正确', () => {
    const fetchFn = vi.fn()
    const { page, pageSize } = usePagination(fetchFn, 10)
    expect(page.value).toBe(1)
    expect(pageSize.value).toBe(10)
  })

  it('initialPageSize 默认值为 20', () => {
    const fetchFn = vi.fn()
    const { pageSize } = usePagination(fetchFn)
    expect(pageSize.value).toBe(20)
  })

  it('loadPage 更新 page 并调用 fetchFn', async () => {
    const fetchFn = vi.fn().mockResolvedValue(undefined)
    const { page, loadPage } = usePagination(fetchFn)

    await loadPage(3)

    expect(page.value).toBe(3)
    expect(fetchFn).toHaveBeenCalledWith(3, 20)
  })

  it('refreshPage 以当前 page/pageSize 重新调用 fetchFn', async () => {
    const fetchFn = vi.fn().mockResolvedValue(undefined)
    const { loadPage, refreshPage } = usePagination(fetchFn)

    await loadPage(2)
    fetchFn.mockClear()

    await refreshPage()

    expect(fetchFn).toHaveBeenCalledWith(2, 20)
  })

  it('onPageSizeChange 更新 pageSize 并重置为第 1 页', async () => {
    const fetchFn = vi.fn().mockResolvedValue(undefined)
    const { page, pageSize, loadPage, onPageSizeChange } = usePagination(fetchFn)

    await loadPage(5)
    fetchFn.mockClear()

    await onPageSizeChange(50)

    expect(pageSize.value).toBe(50)
    expect(page.value).toBe(1)
    expect(fetchFn).toHaveBeenCalledWith(1, 50)
  })

  it('debouncedLoad 防抖触发 loadPage(1)', async () => {
    const fetchFn = vi.fn().mockResolvedValue(undefined)
    const { page, debouncedLoad } = usePagination(fetchFn)

    debouncedLoad()
    debouncedLoad()
    debouncedLoad()

    expect(fetchFn).not.toHaveBeenCalled()

    await vi.runAllTimersAsync()

    expect(page.value).toBe(1)
    expect(fetchFn).toHaveBeenCalledTimes(1)
  })
})
