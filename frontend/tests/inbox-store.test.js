import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../src/lib/api.js', async () => {
  const actual = await vi.importActual('../src/lib/api.js')
  return { ...actual, fetchInbox: vi.fn(), fetchArchived: vi.fn(), fetchNavigation: vi.fn(), fetchPlatforms: vi.fn() }
})
import { ApiError, fetchArchived, fetchNavigation, fetchInbox, fetchPlatforms } from '../src/lib/api.js'
import { useInboxStore } from '../src/stores/inbox.js'
import { useLibraryStore } from '../src/stores/library.js'

const mk = (id) => ({ id, rel_path: `images/_inbox/${id}.png`, ext: '.png', thumb_url: `/thumbs/${id}` })
const page = (ids, total = ids.length) => ({ total, offset: 0, limit: 200, items: ids.map(mk) })

let inbox
const NAV = { inbox: 0, archived: 0, folders: [] }
beforeEach(() => {
  setActivePinia(createPinia())
  fetchInbox.mockReset()
  fetchArchived.mockReset()
  fetchNavigation.mockReset()
  fetchPlatforms.mockReset()
  fetchPlatforms.mockResolvedValue([])
  fetchNavigation.mockResolvedValue(NAV) // 导航数据：每次 load 都会顺带取一次
  inbox = useInboxStore()
})

async function loaded(ids, total) {
  fetchInbox.mockResolvedValueOnce(page(ids, total))
  await inbox.load()
}

describe('load', () => {
  it('载入列表和总数', async () => {
    await loaded([1, 2, 3])
    expect(inbox.ids).toEqual([1, 2, 3])
    expect(inbox.total).toBe(3)
    expect(inbox.error).toBe('')
    expect(inbox.loading).toBe(false)
  })

  it('请求失败：保留错误文案，不清掉已有内容', async () => {
    await loaded([1, 2])
    fetchInbox.mockRejectedValueOnce(new ApiError('连不上服务', 0))
    await inbox.load()
    expect(inbox.error).toBe('连不上服务')
    expect(inbox.ids).toEqual([1, 2])
    expect(inbox.loading).toBe(false)
  })

  it('刷新后，已不存在的选中项、焦点、预览都被清掉', async () => {
    await loaded([1, 2, 3])
    inbox.click(2)
    inbox.openPreview(2)
    await loaded([1, 3])
    expect([...inbox.selected]).toEqual([])
    expect(inbox.focus).toBeNull()
    expect(inbox.previewId).toBeNull()
  })

  it('刷新后仍存在的选中项保留', async () => {
    await loaded([1, 2, 3])
    inbox.click(3)
    await loaded([1, 3])
    expect([...inbox.selected]).toEqual([3])
  })
})

describe('loadMore', () => {
  it('追加下一页，并去掉重复的 id', async () => {
    await loaded([1, 2], 4)
    fetchInbox.mockResolvedValueOnce(page([2, 3, 4], 4))
    await inbox.loadMore()
    expect(inbox.ids).toEqual([1, 2, 3, 4])
    expect(fetchInbox).toHaveBeenLastCalledWith(2, 200, 'all')
  })

  it('已经加载完就不再请求', async () => {
    await loaded([1, 2], 2)
    fetchInbox.mockClear()
    await inbox.loadMore()
    expect(fetchInbox).not.toHaveBeenCalled()
  })
})

describe('点击选择', () => {
  beforeEach(() => loaded([1, 2, 3, 4, 5]))

  it('普通点击单选；Ctrl 增减；Shift 选一段', () => {
    inbox.click(2)
    expect([...inbox.selected]).toEqual([2])
    inbox.click(4, { ctrl: true })
    expect([...inbox.selected].sort()).toEqual([2, 4])
    inbox.click(1)
    inbox.click(3, { shift: true })
    expect([...inbox.selected].sort()).toEqual([1, 2, 3])
  })

  it('触屏多选模式的点按是增减', () => {
    inbox.tapToggle(1)
    inbox.tapToggle(2)
    inbox.tapToggle(1)
    expect([...inbox.selected]).toEqual([2])
  })

  it('全选与清空', () => {
    inbox.selectAll()
    expect(inbox.selected.size).toBe(5)
    inbox.clearSelection()
    expect(inbox.selected.size).toBe(0)
  })
})

describe('方向键', () => {
  beforeEach(() => loaded([1, 2, 3, 4, 5, 6]))

  it('第一次按方向键只落下焦点并选中第一张', () => {
    inbox.moveFocus('ArrowRight', 3)
    expect(inbox.focus).toBe(1)
    expect([...inbox.selected]).toEqual([1])
  })

  it('之后每次移动并单选；Shift 扩展范围', () => {
    inbox.moveFocus('ArrowRight', 3)
    inbox.moveFocus('ArrowRight', 3)
    expect(inbox.focus).toBe(2)
    expect([...inbox.selected]).toEqual([2])
    inbox.moveFocus('ArrowDown', 3, { shift: true })
    expect([...inbox.selected].sort()).toEqual([2, 3, 4, 5])
  })
})

describe('预览', () => {
  beforeEach(() => loaded([1, 2, 3]))

  it('空格打开焦点那张；没有焦点时不打开', () => {
    inbox.openPreview()
    expect(inbox.previewId).toBeNull()
    inbox.click(2)
    inbox.openPreview()
    expect(inbox.previewItem.id).toBe(2)
  })

  it('左右切图，到头停住，并带动焦点', () => {
    inbox.openPreview(1)
    inbox.stepPreview(-1)
    expect(inbox.previewId).toBe(1)
    inbox.stepPreview(1)
    inbox.stepPreview(1)
    inbox.stepPreview(1)
    expect(inbox.previewId).toBe(3)
    expect(inbox.focus).toBe(3)
  })

  it('关闭', () => {
    inbox.openPreview(1)
    inbox.closePreview()
    expect(inbox.previewItem).toBeNull()
  })
})

describe('收件箱／已归档视图', () => {
  const archived = { kind: 'archived' }
  it('已归档接口不带平台路径', async () => {
    fetchArchived.mockResolvedValueOnce(page([1, 2]))
    await inbox.setView(archived)
    expect(inbox.isInbox).toBe(false)
    expect(fetchArchived).toHaveBeenCalledWith(0, 200)
    expect(inbox.ids).toEqual([1, 2])
  })
  it('切换清掉选择、焦点、预览', async () => {
    await loaded([1, 2]); inbox.click(2); inbox.openPreview(2)
    let release
    fetchArchived.mockReturnValueOnce(new Promise(r => release = r))
    const pending = inbox.setView(archived)
    expect(inbox.items).toEqual([])
    expect(inbox.selected.size).toBe(0)
    expect(inbox.previewId).toBeNull()
    release(page([3])); await pending
    expect(inbox.ids).toEqual([3])
  })
  it('旧视图慢请求不能覆盖新视图', async () => {
    let release
    fetchArchived.mockReturnValueOnce(new Promise(r => release = r))
    const old = inbox.setView(archived)
    fetchInbox.mockResolvedValueOnce(page([9]))
    await inbox.setView({ kind: 'inbox', filter: 'hint' })
    release(page([1])); await old
    expect(inbox.ids).toEqual([9])
  })
  it('旧视图错误不能污染新视图', async () => {
    let reject
    fetchArchived.mockReturnValueOnce(new Promise((_, r) => reject = r))
    const old = inbox.setView(archived)
    fetchInbox.mockResolvedValueOnce(page([9]))
    await inbox.setView({ kind: 'inbox', filter: 'all' })
    reject(new ApiError('old',500)); await old
    expect(inbox.error).toBe('')
  })
  it('分页旧请求不混入新视图', async () => {
    fetchArchived.mockResolvedValueOnce(page([1,2],4))
    await inbox.setView(archived)
    let release
    fetchArchived.mockReturnValueOnce(new Promise(r => release = r))
    const old = inbox.loadMore()
    fetchInbox.mockResolvedValueOnce(page([9]))
    await inbox.setView({ kind: 'inbox' })
    release(page([3,4],4)); await old
    expect(inbox.ids).toEqual([9])
  })
  it('相同视图不重复取，force 可刷新并保留选择', async () => {
    fetchArchived.mockResolvedValue(page([1,2]))
    await inbox.setView(archived); inbox.click(2)
    await inbox.setView(archived)
    expect(fetchArchived).toHaveBeenCalledTimes(1)
    await inbox.setView(archived,{force:true})
    expect(fetchArchived).toHaveBeenCalledTimes(2)
    expect([...inbox.selected]).toEqual([2])
  })
  it('导航失败不阻断图片，也保留旧统计', async () => {
    fetchNavigation.mockResolvedValueOnce({inbox:3,inbox_hinted:0,archived:7})
    await loaded([1])
    fetchNavigation.mockRejectedValueOnce(new Error('offline'))
    await loaded([1,2])
    expect(useLibraryStore().nav.archived).toBe(7)
    expect(inbox.ids).toEqual([1,2])
  })
  it('已归档分页使用同一状态接口', async () => {
    fetchArchived.mockResolvedValueOnce(page([1,2],3))
    await inbox.setView(archived)
    fetchArchived.mockResolvedValueOnce(page([3],3))
    await inbox.loadMore()
    expect(fetchArchived).toHaveBeenLastCalledWith(2,200)
    expect(inbox.ids).toEqual([1,2,3])
  })
})

describe('收件箱来源建议筛选', () => {
  const inboxView = (filter) => ({ kind: 'inbox', filter })

  it('带筛选请求收件箱：filter 参数传给接口，分页也沿用', async () => {
    fetchInbox.mockResolvedValueOnce({ filter: 'hint', ...page([1, 2], 3) })
    await inbox.setView(inboxView('hint'))
    expect(fetchInbox).toHaveBeenCalledWith(0, 200, 'hint')
    expect(inbox.hintFilter).toBe('hint')
    expect(inbox.isInbox).toBe(true)
    fetchInbox.mockResolvedValueOnce({ filter: 'hint', ...page([3], 3) })
    await inbox.loadMore()
    expect(fetchInbox).toHaveBeenLastCalledWith(2, 200, 'hint')
    expect(inbox.ids).toEqual([1, 2, 3])
  })

  it('默认视图不带筛选时按 all 请求', async () => {
    await loaded([1])
    expect(fetchInbox).toHaveBeenCalledWith(0, 200, 'all')
    expect(inbox.hintFilter).toBe('all')
  })

  it('切换筛选是一次视图变化：清空旧图、清掉选择，不残留上一个筛选的内容', async () => {
    await loaded([1, 2, 3])
    inbox.click(2)
    let release
    fetchInbox.mockReturnValueOnce(new Promise((r) => (release = r)))
    const p = inbox.setView(inboxView('nohint'))
    expect(inbox.items).toEqual([])
    expect(inbox.selected.size).toBe(0)
    release({ filter: 'nohint', ...page([9]) })
    await p
    expect(inbox.ids).toEqual([9])
    expect(inbox.hintFilter).toBe('nohint')
  })

  it('在筛选之间快速切换：慢返回的旧结果不能覆盖新筛选', async () => {
    let releaseHint
    fetchInbox.mockReturnValueOnce(new Promise((r) => (releaseHint = r)))
    fetchInbox.mockResolvedValueOnce({ filter: 'nohint', ...page([7]) })
    const pa = inbox.setView(inboxView('hint'))
    const pb = inbox.setView(inboxView('nohint'))
    await pb
    releaseHint({ filter: 'hint', ...page([1, 2]) })
    await pa
    expect(inbox.ids).toEqual([7])
    expect(inbox.hintFilter).toBe('nohint')
  })

  it('同一筛选再次 setView 不重复请求；不同筛选会请求', async () => {
    fetchInbox.mockResolvedValue({ filter: 'hint', ...page([1]) })
    await inbox.setView(inboxView('hint'))
    await inbox.setView(inboxView('hint'))
    expect(fetchInbox).toHaveBeenCalledTimes(1)
    await inbox.setView(inboxView('all'))
    expect(fetchInbox).toHaveBeenCalledTimes(2)
  })

  it('已归档里 hintFilter 恒为 all（筛选只属于收件箱）', async () => {
    fetchArchived.mockResolvedValueOnce({ folder: 'x', ...page([1]) })
    await inbox.setView({ kind: 'archived' })
    expect(inbox.isInbox).toBe(false)
    expect(inbox.hintFilter).toBe('all')
    expect(fetchInbox).not.toHaveBeenCalled()
  })

  it('导航数据带来源建议张数；平台名只取一次', async () => {
    fetchNavigation.mockResolvedValue({ inbox: 10, inbox_hinted: 4, archived: 0, folders: [] })
    fetchPlatforms.mockResolvedValue([{ id: 'lofter', name: '乐乎' }])
    await loaded([1])
    expect(useLibraryStore().nav.inbox_hinted).toBe(4)
    expect(useLibraryStore().platformNames).toEqual({ lofter: '乐乎' })
    await inbox.load()
    expect(fetchPlatforms).toHaveBeenCalledTimes(1)
  })

  it('平台名取不到不影响看图', async () => {
    fetchPlatforms.mockRejectedValue(new ApiError('boom', 500))
    await loaded([1, 2])
    expect(inbox.ids).toEqual([1, 2])
    expect(inbox.error).toBe('')
    expect(useLibraryStore().platformNames).toEqual({})
  })
})
