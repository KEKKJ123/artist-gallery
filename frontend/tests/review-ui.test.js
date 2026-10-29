import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import ReviewScreen from '../src/components/ReviewScreen.vue'
import OperationDialogs from '../src/components/OperationDialogs.vue'
import { useReviewStore } from '../src/stores/review.js'
import * as api from '../src/lib/api.js'
vi.mock('../src/lib/api.js', () => ({
  fetchMetadata: vi.fn(), fetchImage: vi.fn(), fetchDraft: vi.fn(), fetchFileSize: vi.fn(),
  putDraft: vi.fn(), parseLinks: vi.fn(), saveReview: vi.fn(), planArchive: vi.fn(),
  executeArchive: vi.fn(), undoOperation: vi.fn(), recoverOperation: vi.fn(),
}))
let wrapper, review, pinia
const item = {
  id: 1, revision: 'r1', file_id: 1, state: 'inbox', display_status: 'ok', file_url: '/image.png',
  sources: [{ id: 1, platform: 'pixiv', post_id: '123456789', status: 'pending', page: 2, posted_at: null }], evidence: [], source_hints: [],
}
beforeEach(async () => {
  vi.resetAllMocks(); localStorage.clear()
  pinia = createPinia(); setActivePinia(pinia)
  api.fetchMetadata.mockResolvedValue({ library_id: 'lib', operations: { can_undo: false, pending: [] } })
  api.fetchImage.mockResolvedValue(item)
  api.fetchDraft.mockResolvedValue({ revision: 0, payload: null })
  api.fetchFileSize.mockResolvedValue({ file_id: 1, bytes: 1024 })
  api.putDraft.mockImplementation(async (_id, payload, revision) => ({ payload, revision: revision + 1 }))
  review = useReviewStore(); await review.start([1, 2])
})
afterEach(() => { wrapper?.unmount(); document.body.replaceChildren() })
it('输入框 Enter、Ctrl+V 不触发保存／归档，清空页码保持未知', async () => {
  wrapper = mount(ReviewScreen, { attachTo: document.body, global: { plugins: [pinia] } })
  const text = wrapper.get('#review-links')
  await text.setValue('one\ntwo')
  const event = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true })
  text.element.dispatchEvent(event)
  expect(event.defaultPrevented).toBe(false)
  await text.trigger('keydown', { key: 'v', ctrlKey: true })
  expect(api.saveReview).not.toHaveBeenCalled()
  expect(api.executeArchive).not.toHaveBeenCalled()
  const page = wrapper.get('input[aria-label="pixiv 页码"]')
  await page.setValue('')
  expect(review.draft.edits[1].page).toBe(null)
  expect(page.element.value).toBe('')
  await wrapper.get('select').setValue('confirmed')
  expect(wrapper.get('.saved-status').text()).toContain('待核查')
})
it('多选来源必须勾选范围确认，改输入使确认失效', async () => {
  Object.assign(review.bulk, { ids: [1, 2], text: '', revisions: {}, ready: true })
  wrapper = mount(OperationDialogs, { global: { plugins: [pinia] } })
  const submit = () => wrapper.findAll('button').find((b) => b.text() === '追加到每张所选图')
  await wrapper.get('#bulk-links').setValue('https://pixiv.net/artworks/123456789')
  expect(submit().element.disabled).toBe(true)
  await wrapper.get('input[type="checkbox"]').setValue(true)
  expect(submit().element.disabled).toBe(false)
  await wrapper.get('#bulk-links').setValue('changed')
  expect(submit().element.disabled).toBe(true)
})
it('归档混合缺项只显示错误，不能执行成功的子集', async () => {
  review.archivePlan = { ids: [1, 2], errors: [{ image_id: 2, reason: '缺来源' }], moves: [], force: false }
  wrapper = mount(OperationDialogs, { global: { plugins: [pinia] } })
  expect(wrapper.text()).toContain('整批尚未执行')
  const button = wrapper.findAll('button').find((b) => b.text() === '执行归档')
  expect(button.element.disabled).toBe(true)
  await button.trigger('click'); await flushPromises()
  expect(api.executeArchive).not.toHaveBeenCalled()
})
it('清单弹层捕获 Escape，不让背后的检查页或网格响应', async () => {
  Object.assign(review.bulk, { ids: [1, 2], text: 'draft', revisions: {}, ready: true })
  wrapper = mount(OperationDialogs, { attachTo: document.body, global: { plugins: [pinia] } })
  let background = 0
  const listener = () => { background++ }
  window.addEventListener('keydown', listener)
  const event = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true })
  document.body.dispatchEvent(event)
  window.removeEventListener('keydown', listener)
  expect(event.defaultPrevented).toBe(true)
  expect(background).toBe(0)
  expect(review.bulk.ready).toBe(false)
})

it('单图强制归档无需复选框，点击明确按钮才提交确认且等待期间不能重复提交', async () => {
  api.planArchive.mockResolvedValue({ errors: [], token: 'force-one', force: true, moves: [] })
  let finish
  api.executeArchive.mockImplementation(() => new Promise((resolve) => { finish = resolve }))
  wrapper = mount(OperationDialogs, { global: { plugins: [pinia] } })
  await review.prepareArchive([1], true)
  await nextTick()
  expect(wrapper.find('input[type="checkbox"]').exists()).toBe(false)
  expect(wrapper.text()).toContain('只放宽来源门槛')
  expect(api.executeArchive).not.toHaveBeenCalled()
  const submit = wrapper.findAll('button').find((b) => b.text() === '强制归档')
  expect(submit.element.disabled).toBe(false)
  await submit.trigger('click')
  expect(api.executeArchive).toHaveBeenCalledExactlyOnceWith({ ids: [1], token: 'force-one', force: true, confirmed: true }, 'lib')
  expect(submit.element.disabled).toBe(true)
  await submit.trigger('click')
  expect(api.executeArchive).toHaveBeenCalledTimes(1)
  finish({ status: 'done' })
  await flushPromises()
  expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
  expect(wrapper.emitted('changed')).toHaveLength(1)
})

it.each(['返回／取消', 'Escape'])('单图强制归档通过 %s 取消不会提交', async (action) => {
  review.archivePlan = { ids: [1], errors: [], moves: [], force: true }
  wrapper = mount(OperationDialogs, { attachTo: document.body, global: { plugins: [pinia] } })
  if (action === 'Escape') {
    document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }))
  } else {
    await wrapper.findAll('button').find((b) => b.text() === action).trigger('click')
  }
  await nextTick()
  expect(review.archivePlan).toBe(null)
  expect(api.executeArchive).not.toHaveBeenCalled()
})

it('单图强制归档遇到文件预检错误仍禁止执行', async () => {
  review.archivePlan = { ids: [1], errors: [{ image_id: 1, reason: '文件缺失' }], moves: [], force: true }
  wrapper = mount(OperationDialogs, { global: { plugins: [pinia] } })
  const submit = wrapper.findAll('button').find((b) => b.text() === '强制归档')
  expect(submit.element.disabled).toBe(true)
  await submit.trigger('click')
  expect(api.executeArchive).not.toHaveBeenCalled()
})

it.each([false, true])('多图归档仍须勾选范围确认（force=%s）', async (force) => {
  review.archivePlan = { ids: [1, 2], errors: [], moves: [], force, token: 'bulk' }
  api.executeArchive.mockResolvedValue({ status: 'done' })
  wrapper = mount(OperationDialogs, { global: { plugins: [pinia] } })
  const submit = wrapper.findAll('button').find((b) => b.text() === '执行归档')
  expect(submit.element.disabled).toBe(true)
  await submit.trigger('click')
  expect(api.executeArchive).not.toHaveBeenCalled()
  await wrapper.get('input[type="checkbox"]').setValue(true)
  expect(submit.element.disabled).toBe(false)
  await submit.trigger('click'); await flushPromises()
  expect(api.executeArchive).toHaveBeenCalledWith({ ids: [1, 2], token: 'bulk', force, confirmed: true }, 'lib')
})

it('已有来源的解除是独立动作，清空链接不解除来源', async () => {
  wrapper = mount(ReviewScreen, { global: { plugins: [pinia] } })
  await wrapper.get('#review-links').setValue('')
  expect(review.draft.edits).toEqual({})
  await wrapper.findAll('button').find((b) => b.text() === '解除这条来源').trigger('click')
  expect(review.draft.edits[1].remove).toBe(true)
  await nextTick()
  expect(wrapper.text()).toContain('证据仍保留')
})
