import { describe, expect, it, vi } from 'vitest'
import { useImageCollection } from '../src/composables/use-image-collection.js'

const page = (ids, total = ids.length) => ({ items: ids.map((id) => ({ id })), total })

describe('独立分页集合（不需要 Pinia 或组件）', () => {
  it('同一页与跨页都去重，并阻止同时重复翻页', async () => {
    let release
    const fetchPage = vi.fn().mockResolvedValueOnce(page([1, 1, 2], 4))
      .mockReturnValueOnce(new Promise((r) => (release = r)))
    const c = useImageCollection(fetchPage)
    await c.load()
    const more = c.loadMore()
    await c.loadMore()
    expect(fetchPage).toHaveBeenCalledTimes(2)
    expect(fetchPage).toHaveBeenLastCalledWith(2)
    release(page([2, 3, 3, 4]))
    await more
    expect(c.ids.value).toEqual([1, 2, 3, 4])
    expect(c.hasMore.value).toBe(false)
  })

  it('失效请求不能提前结束新请求的 loading', async () => {
    let oldRelease, newRelease
    const fetchPage = vi.fn()
      .mockReturnValueOnce(new Promise((r) => (oldRelease = r)))
      .mockReturnValueOnce(new Promise((r) => (newRelease = r)))
    const c = useImageCollection(fetchPage)
    const old = c.load()
    const current = c.load()
    oldRelease(page([1]))
    expect(await old).toBe(false)
    expect(c.loading.value).toBe(true)
    expect(c.ids.value).toEqual([])
    newRelease(page([2]))
    expect(await current).toBe(true)
    expect(c.ids.value).toEqual([2])
    expect(c.loading.value).toBe(false)
  })

  it('reset 单独使用也会失效旧请求并清掉错误和加载状态', async () => {
    let reject
    const fetchPage = vi.fn().mockReturnValueOnce(new Promise((_, r) => (reject = r)))
    const c = useImageCollection(fetchPage)
    const old = c.load()
    c.reset()
    reject(new Error('旧错误'))
    await old
    expect(c.items.value).toEqual([])
    expect(c.error.value).toBe('')
    expect(c.loading.value).toBe(false)
  })

  it('翻页失败保留已有内容；重试成功清掉旧错误', async () => {
    const fetchPage = vi.fn().mockResolvedValueOnce(page([1], 2))
      .mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce(page([2]))
    const c = useImageCollection(fetchPage)
    await c.load()
    await c.loadMore()
    expect(c.ids.value).toEqual([1])
    expect(c.error.value).toBe('offline')
    await c.loadMore()
    expect(c.error.value).toBe('')
    expect(c.ids.value).toEqual([1, 2])
  })

  it('集合实例之间不共享加载状态或数据', async () => {
    const a = useImageCollection(() => Promise.resolve(page([1])))
    const b = useImageCollection(() => Promise.resolve(page([9])))
    await Promise.all([a.load(), b.load()])
    a.reset()
    expect(b.ids.value).toEqual([9])
  })
})
