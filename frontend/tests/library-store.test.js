import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useLibraryStore } from '../src/stores/library.js'
import { fetchNavigation, fetchPlatforms } from '../src/lib/api.js'

vi.mock('../src/lib/api.js', () => ({ fetchNavigation: vi.fn(), fetchPlatforms: vi.fn() }))
const nav = (n) => ({ inbox: n, inbox_hinted: n, archived: n, folders: [] })
let library
beforeEach(() => {
  setActivePinia(createPinia())
  vi.resetAllMocks()
  library = useLibraryStore()
})

describe('图库级资料', () => {
  it('旧导航慢返回时，不能覆盖更新的统计', async () => {
    let release
    fetchNavigation.mockReturnValueOnce(new Promise((r) => (release = r)))
    fetchNavigation.mockResolvedValueOnce(nav(9))
    const old = library.loadNav()
    await library.loadNav()
    release(nav(1))
    await old
    expect(library.nav).toEqual(nav(9))
  })

  it('新导航失败也不能让更旧的在途请求覆盖已显示的统计', async () => {
    fetchNavigation.mockResolvedValueOnce(nav(5))
    await library.loadNav()
    let release
    fetchNavigation.mockReturnValueOnce(new Promise((r) => (release = r)))
    const old = library.loadNav()
    fetchNavigation.mockRejectedValueOnce(new Error('offline'))
    await library.loadNav()
    release(nav(1))
    await old
    expect(library.nav).toEqual(nav(5))
  })

  it('平台并发请求合并成一次，成功后缓存', async () => {
    let release
    fetchPlatforms.mockReturnValueOnce(new Promise((r) => (release = r)))
    const a = library.loadPlatforms()
    const b = library.loadPlatforms()
    expect(fetchPlatforms).toHaveBeenCalledTimes(1)
    release([{ id: 'custom', name: '自定义' }])
    await Promise.all([a, b])
    await library.loadPlatforms()
    expect(fetchPlatforms).toHaveBeenCalledTimes(1)
    expect(library.platformNames).toEqual({ custom: '自定义' })
  })

  it('平台空列表也缓存，不反复请求', async () => {
    fetchPlatforms.mockResolvedValue([])
    await library.loadPlatforms()
    await library.loadPlatforms()
    expect(fetchPlatforms).toHaveBeenCalledTimes(1)
  })

  it('平台失败后可重试，不影响独立的导航刷新', async () => {
    fetchNavigation.mockResolvedValue(nav(3))
    fetchPlatforms.mockRejectedValueOnce(new Error('offline'))
    await library.refresh()
    expect(library.nav).toEqual(nav(3))
    expect(library.platformNames).toEqual({})
    fetchPlatforms.mockResolvedValueOnce([{ id: 'x', name: 'X' }])
    await library.loadPlatforms()
    expect(library.platformNames).toEqual({ x: 'X' })
  })
})
