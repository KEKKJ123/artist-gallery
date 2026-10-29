import { createPinia, setActivePinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'
import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { useReviewStore } from '../src/stores/review.js'
import * as api from '../src/lib/api.js'

vi.mock('../src/lib/api.js', () => ({
  fetchMetadata: vi.fn(), fetchImage: vi.fn(), fetchDraft: vi.fn(), fetchFileSize: vi.fn(),
  putDraft: vi.fn(), parseLinks: vi.fn(), saveReview: vi.fn(), planArchive: vi.fn(),
  executeArchive: vi.fn(), undoOperation: vi.fn(), recoverOperation: vi.fn(),
}))
const image = (id, revision = `r${id}`) => ({
  id, revision, file_id: id, state: 'inbox', file_url: `/images/${id}.png`,
  sources: [], evidence: [], source_hints: [],
})
function deferred() { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }
beforeEach(() => {
  vi.useFakeTimers()
  vi.resetAllMocks()
  localStorage.clear()
  setActivePinia(createPinia())
  api.fetchMetadata.mockResolvedValue({ library_id: 'lib-a', operations: { can_undo: false, pending: [] } })
  api.fetchImage.mockImplementation(async (id) => image(id))
  api.fetchDraft.mockImplementation(async (id) => ({ image_id: id, library_id: 'lib-a', revision: 0, payload: null }))
  api.fetchFileSize.mockImplementation(async (id) => ({ file_id: id, bytes: id * 100 }))
  api.putDraft.mockImplementation(async (id, payload, revision) => ({ revision: revision + 1, payload }))
  api.parseLinks.mockResolvedValue({ lines: [] })
})
afterEach(() => { vi.clearAllTimers(); vi.useRealTimers() })

it('快速切图时旧图片／文件大小响应不能覆盖新图', async () => {
  const old = deferred(), oldSize = deferred()
  api.fetchImage.mockImplementation((id) => id === 1 ? old.promise : Promise.resolve(image(id)))
  api.fetchFileSize.mockImplementation((id) => id === 1 ? oldSize.promise : Promise.resolve({ file_id: id, bytes: 200 }))
  const review = useReviewStore()
  const first = review.start([1, 2]); await flushPromises()
  await review.show(1)
  old.resolve(image(1)); oldSize.resolve({ file_id: 1, bytes: 99999 })
  await first; await flushPromises()
  expect(review.item.id).toBe(2)
  expect(review.size).toBe(200)
})

it('草稿立即本地保存、串行同步；切图不写正式资料', async () => {
  const review = useReviewStore()
  await review.start([1, 2])
  review.draft.text = 'draft-one'; review.changed()
  expect(localStorage.getItem('artist-gallery:review-draft:lib-a:1')).toContain('draft-one')
  await review.step(1)
  expect(review.draft.text).toBe('')
  await vi.advanceTimersByTimeAsync(350)
  await review.step(-1)
  expect(review.draft.text).toBe('draft-one')
  expect(api.putDraft).toHaveBeenCalledWith(1, expect.objectContaining({ text: 'draft-one' }), 0, 'lib-a')
  expect(api.saveReview).not.toHaveBeenCalled()
})

it('同步期间继续输入，按递增版本再保存，不丢后一次输入', async () => {
  const slow = deferred()
  api.putDraft.mockReturnValueOnce(slow.promise)
  const review = useReviewStore(); await review.start([1])
  review.draft.text = 'first'; review.changed()
  await vi.advanceTimersByTimeAsync(301)
  review.draft.text = 'second'; review.changed()
  slow.resolve({ revision: 1 }); await flushPromises()
  expect(api.putDraft).toHaveBeenNthCalledWith(2, 1, expect.objectContaining({ text: 'second' }), 1, 'lib-a')
  expect(review.draft.text).toBe('second')
})

it('新 store 从服务端恢复草稿，不把草稿确认为正式来源', async () => {
  api.fetchDraft.mockResolvedValue({ revision: 4, payload: { base: 'r1', text: 'restored', edits: {}, evidence_edits: {} } })
  const review = useReviewStore(); await review.start([1])
  expect(review.draft.text).toBe('restored')
  expect(api.saveReview).not.toHaveBeenCalled()
})

it('其他页面已改草稿时不自动覆盖，本地内容保留', async () => {
  localStorage.setItem('artist-gallery:review-draft:lib-a:1', JSON.stringify({ revision: 0, payload: { base: 'r1', text: 'mine', edits: {}, evidence_edits: {} } }))
  api.fetchDraft.mockResolvedValue({ revision: 3, payload: null })
  const review = useReviewStore(); await review.start([1])
  expect(review.draft.text).toBe('mine')
  expect(review.active.failed).toBe(true)
  expect(api.putDraft).not.toHaveBeenCalled()
})

it('过期草稿不能保存或偷偷并入当前资料', async () => {
  api.fetchDraft.mockResolvedValue({ revision: 1, payload: { base: 'old', text: 'old', edits: {}, evidence_edits: {} } })
  const review = useReviewStore(); await review.start([1])
  expect(review.stale).toBe(true)
  expect(await review.save()).toBe(false)
  expect(api.saveReview).not.toHaveBeenCalled()
})

it('保存并下一张只保存当前图，不触发归档；坏行保留且不前进', async () => {
  api.saveReview.mockResolvedValue({ items: [image(1, 'new')], lines: [{ input: 'bad', error: 'bad line' }] })
  const review = useReviewStore(); await review.start([1, 2])
  review.draft.text = 'bad'; review.changed()
  await review.save(true)
  expect(review.index).toBe(0)
  expect(review.draft.text).toBe('bad')
  expect(api.executeArchive).not.toHaveBeenCalled()
  expect(api.saveReview.mock.calls[0][0].ids).toEqual([1])
})

it('保存失败保留草稿，不前进、不重试写操作', async () => {
  api.saveReview.mockRejectedValue(new Error('network unknown'))
  const review = useReviewStore(); await review.start([1, 2])
  review.draft.text = 'mine'; review.changed()
  await review.save(true)
  expect(review.index).toBe(0)
  expect(review.draft.text).toBe('mine')
  expect(api.saveReview).toHaveBeenCalledTimes(1)
})

it('解析的旧响应不能覆盖切图后状态', async () => {
  const slow = deferred(); api.parseLinks.mockReturnValue(slow.promise)
  const review = useReviewStore(); await review.start([1, 2])
  const parsing = review.parse(); await review.step(1)
  slow.resolve({ lines: [{ input: 'old' }] }); await parsing
  expect(review.lines).toEqual([])
})

it('单图正常归档直接执行，强制或多图必须停在清单', async () => {
  api.planArchive.mockResolvedValue({ errors: [], token: 'p', force: false, moves: [] })
  api.executeArchive.mockResolvedValue({ status: 'done' })
  const review = useReviewStore(); await review.start([1])
  expect(await review.prepareArchive([1])).toBe(true)
  expect(api.executeArchive).toHaveBeenCalledTimes(1)
  expect(review.stale).toBe(false)
  await review.prepareArchive([1, 2])
  expect(review.archivePlan.ids).toEqual([1, 2])
  expect(api.executeArchive).toHaveBeenCalledTimes(1)
})

it('单图正常归档全程不写入清单，弹窗不会闪现；成功后发出提示', async () => {
  api.planArchive.mockResolvedValue({ errors: [], token: 'p', force: false, moves: [] })
  let planDuringExecute = 'unset'
  api.executeArchive.mockImplementation(async () => {
    planDuringExecute = review.archivePlan
    return { status: 'done' }
  })
  const review = useReviewStore(); await review.start([1])
  const seq = review.noticeSeq
  expect(await review.prepareArchive([1])).toBe(true)
  expect(planDuringExecute).toBe(null)
  expect(review.archivePlan).toBe(null)
  expect(review.noticeSeq).toBe(seq + 1)
  expect(review.notice).toContain('已归档 1 张')
})

it('预检有缺项或强制归档停在清单，不执行也不发成功提示', async () => {
  api.planArchive.mockResolvedValueOnce({ errors: [{ image_id: 1, reason: '缺来源' }], token: 'p', force: false, moves: [] })
  const review = useReviewStore(); await review.start([1])
  const seq = review.noticeSeq
  expect(await review.prepareArchive([1])).toBe(false)
  expect(review.archivePlan.errors).toHaveLength(1)
  review.archivePlan = null
  api.planArchive.mockResolvedValueOnce({ errors: [], token: 'p', force: true, moves: [] })
  expect(await review.prepareArchive([1], true)).toBe(false)
  expect(review.archivePlan.force).toBe(true)
  expect(api.executeArchive).not.toHaveBeenCalled()
  expect(review.noticeSeq).toBe(seq)
})

it('归档失败写入错误，不发成功提示', async () => {
  api.planArchive.mockResolvedValue({ errors: [], token: 'p', force: false, moves: [] })
  api.executeArchive.mockRejectedValue(new Error('目标被占用'))
  const review = useReviewStore(); await review.start([1])
  const seq = review.noticeSeq
  expect(await review.prepareArchive([1])).toBe(false)
  expect(review.error).toBe('目标被占用')
  expect(review.noticeSeq).toBe(seq)
  expect(review.busy).toBe(false)
})

it('批量范围在准备时冻结，后续提交不变成别的图片', async () => {
  api.saveReview.mockResolvedValue({ lines: [], items: [image(1), image(2)] })
  const review = useReviewStore(); const selected = [1, 2]
  await review.prepareBulk(selected)
  selected.push(3)
  review.bulk.text = 'link'; await review.saveBulk()
  expect(api.saveReview.mock.calls[0][0].ids).toEqual([1, 2])
  expect(api.saveReview.mock.calls[0][0].confirm_scope).toBe(true)
})

it('文件大小失败显示原因而不是零', async () => {
  api.fetchFileSize.mockRejectedValue(new Error('missing file'))
  const review = useReviewStore(); await review.start([1]); await flushPromises()
  expect(review.size).toBe(null)
  expect(review.sizeError).toContain('missing file')
})

it('放弃草稿不能清掉另一页面的新草稿，只能明确读取最新版本', async () => {
  const review = useReviewStore(); await review.start([1])
  api.fetchDraft.mockResolvedValue({ revision: 9, payload: { base: 'r1', text: 'other', edits: {}, evidence_edits: {} } })
  await review.discard()
  expect(api.putDraft).not.toHaveBeenCalled()
  expect(review.error).toContain('未清空')
  await review.reloadDraft()
  expect(review.draft.text).toBe('other')
  expect(api.putDraft).not.toHaveBeenCalled()
})

it('同步已成功但响应前关页，键顺序不同也识别为同一草稿', async () => {
  localStorage.setItem('artist-gallery:review-draft:lib-a:1', JSON.stringify({ revision: 0, payload: { base: 'r1', text: 'mine', edits: {}, evidence_edits: {} } }))
  api.fetchDraft.mockResolvedValue({ revision: 1, payload: { evidence_edits: {}, edits: {}, text: 'mine', base: 'r1' } })
  const review = useReviewStore(); await review.start([1])
  expect(review.draft.text).toBe('mine')
  expect(review.active.failed).toBe(false)
  expect(api.putDraft).not.toHaveBeenCalled()
})

it('批量解析旧响应不覆盖新输入', async () => {
  const slow = deferred(); api.parseLinks.mockReturnValue(slow.promise)
  const review = useReviewStore(); await review.prepareBulk([1, 2])
  review.bulk.text = 'old'; const parsing = review.parseBulk()
  review.bulk.text = 'new'; review.bulkChanged()
  slow.resolve({ lines: [{ line: 1, input: 'old' }] }); await parsing
  expect(review.bulk.lines).toEqual([])
})

it('关闭检查后读取中的旧响应不能重新打开界面', async () => {
  const slow = deferred(); api.fetchImage.mockReturnValue(slow.promise)
  const review = useReviewStore(); const pending = review.start([1]); await flushPromises()
  review.close(); slow.resolve(image(1)); await pending
  expect(review.open).toBe(false)
  expect(review.item).toBe(null)
})
