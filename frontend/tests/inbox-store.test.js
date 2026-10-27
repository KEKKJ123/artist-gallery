import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../src/lib/api.js', async () => {
  const actual = await vi.importActual('../src/lib/api.js')
  return { ...actual, fetchInbox: vi.fn() }
})
import { ApiError, fetchInbox } from '../src/lib/api.js'
import { useInboxStore } from '../src/stores/inbox.js'

const mk = (id) => ({ id, rel_path: `images/_inbox/${id}.png`, ext: '.png', thumb_url: `/thumbs/${id}` })
const page = (ids, total = ids.length) => ({ total, offset: 0, limit: 200, items: ids.map(mk) })

let inbox
beforeEach(() => {
  setActivePinia(createPinia())
  fetchInbox.mockReset()
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
