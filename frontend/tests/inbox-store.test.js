import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../src/lib/api.js', async () => {
  const actual = await vi.importActual('../src/lib/api.js')
  return { ...actual, fetchInbox: vi.fn(), fetchFolder: vi.fn(), fetchFolders: vi.fn() }
})
import { ApiError, fetchFolder, fetchFolders, fetchInbox } from '../src/lib/api.js'
import { useInboxStore } from '../src/stores/inbox.js'

const mk = (id) => ({ id, rel_path: `images/_inbox/${id}.png`, ext: '.png', thumb_url: `/thumbs/${id}` })
const page = (ids, total = ids.length) => ({ total, offset: 0, limit: 200, items: ids.map(mk) })

let inbox
const NAV = { inbox: 0, archived: 0, folders: [] }
beforeEach(() => {
  setActivePinia(createPinia())
  fetchInbox.mockReset()
  fetchFolder.mockReset()
  fetchFolders.mockReset()
  fetchFolders.mockResolvedValue(NAV) // 导航数据：每次 load 都会顺带取一次
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
    expect(fetchInbox).toHaveBeenLastCalledWith(2, 200)
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

describe('视图切换（收件箱 / 文件夹）', () => {
  const folder = (path) => ({ kind: 'folder', path })

  it('默认是收件箱；文件夹视图用 fetchFolder 取数据，带上路径', async () => {
    expect(inbox.isInbox).toBe(true)
    fetchFolder.mockResolvedValueOnce({ folder: 'pixiv', ...page([1, 2]) })
    await inbox.setView(folder('pixiv'))
    expect(inbox.isInbox).toBe(false)
    expect(fetchFolder).toHaveBeenCalledWith('pixiv', 0, 200)
    expect(fetchInbox).not.toHaveBeenCalled()
    expect(inbox.ids).toEqual([1, 2])
  })

  it('切换视图时清掉选择、焦点、预览，并且先清空旧图', async () => {
    await loaded([1, 2, 3])
    inbox.click(2)
    inbox.openPreview(2)
    let release
    fetchFolder.mockReturnValueOnce(new Promise((r) => (release = r)))
    const p = inbox.setView(folder('x'))
    // 请求还没回来：旧的收件箱内容不能还留在界面上
    expect(inbox.items).toEqual([])
    expect(inbox.selected.size).toBe(0)
    expect(inbox.focus).toBeNull()
    expect(inbox.previewId).toBeNull()
    release({ folder: 'x', ...page([10]) })
    await p
    expect(inbox.ids).toEqual([10])
  })

  it('"全部已归档"（路径为空）也是文件夹视图，和收件箱不同', async () => {
    fetchFolder.mockResolvedValueOnce({ folder: '', ...page([5]) })
    await inbox.setView(folder(''))
    expect(inbox.isInbox).toBe(false)
    expect(fetchFolder).toHaveBeenCalledWith('', 0, 200)
  })

  it('快速连续切换：先发出、后返回的旧请求不能覆盖新结果', async () => {
    let releaseA
    fetchFolder.mockReturnValueOnce(new Promise((r) => (releaseA = r))) // A：慢
    fetchFolder.mockResolvedValueOnce({ folder: 'b', ...page([2]) }) // B：快
    const pa = inbox.setView(folder('a'))
    const pb = inbox.setView(folder('b'))
    await pb
    expect(inbox.ids).toEqual([2])
    releaseA({ folder: 'a', ...page([1]) }) // A 现在才回来
    await pa
    expect(inbox.ids).toEqual([2]) // 仍是 B 的结果
    expect(inbox.view).toEqual(folder('b'))
    expect(inbox.loading).toBe(false)
  })

  it('旧请求失败也不能把错误写到新视图上', async () => {
    let rejectA
    fetchFolder.mockReturnValueOnce(new Promise((_, rej) => (rejectA = rej)))
    fetchFolder.mockResolvedValueOnce({ folder: 'b', ...page([2]) })
    const pa = inbox.setView(folder('a'))
    const pb = inbox.setView(folder('b'))
    await pb
    rejectA(new ApiError('连不上服务', 0))
    await pa
    expect(inbox.error).toBe('')
    expect(inbox.ids).toEqual([2])
  })

  it('加载更多：翻页请求在途时用户切走了，旧页不能混进新视图', async () => {
    fetchFolder.mockResolvedValueOnce({ folder: 'a', ...page([1, 2], 4) })
    await inbox.setView(folder('a'))
    let releaseMore
    fetchFolder.mockReturnValueOnce(new Promise((r) => (releaseMore = r)))
    const more = inbox.loadMore()
    fetchFolder.mockResolvedValueOnce({ folder: 'b', ...page([9]) })
    await inbox.setView(folder('b'))
    releaseMore({ folder: 'a', ...page([3, 4], 4) })
    await more
    expect(inbox.ids).toEqual([9])
  })

  it('同一视图再次 setView 不重复请求；force 或 load 才刷新', async () => {
    fetchFolder.mockResolvedValue({ folder: 'a', ...page([1]) })
    await inbox.setView(folder('a'))
    await inbox.setView(folder('a'))
    expect(fetchFolder).toHaveBeenCalledTimes(1)
    await inbox.setView(folder('a'), { force: true })
    expect(fetchFolder).toHaveBeenCalledTimes(2)
  })

  it('同一视图的刷新保留选择（不清空）', async () => {
    fetchFolder.mockResolvedValue({ folder: 'a', ...page([1, 2, 3]) })
    await inbox.setView(folder('a'))
    inbox.click(2)
    await inbox.load()
    expect([...inbox.selected]).toEqual([2])
  })

  it('每次加载都会顺带刷新左侧导航数据；导航失败不影响看图', async () => {
    fetchFolders.mockResolvedValueOnce({ inbox: 3, archived: 7, folders: [{ path: 'x', name: 'x', depth: 0, count: 7, has_children: false }] })
    await loaded([1])
    expect(inbox.nav.archived).toBe(7)
    fetchFolders.mockRejectedValueOnce(new ApiError('boom', 500))
    await loaded([1, 2])
    expect(inbox.ids).toEqual([1, 2])
    expect(inbox.error).toBe('')
    expect(inbox.nav.archived).toBe(7) // 失败时保留旧导航，不清空
  })

  it('文件夹视图里的分页接着取下一页，用同一个路径', async () => {
    fetchFolder.mockResolvedValueOnce({ folder: 'a', ...page([1, 2], 3) })
    await inbox.setView(folder('a'))
    fetchFolder.mockResolvedValueOnce({ folder: 'a', ...page([3], 3) })
    await inbox.loadMore()
    expect(fetchFolder).toHaveBeenLastCalledWith('a', 2, 200)
    expect(inbox.ids).toEqual([1, 2, 3])
  })
})
