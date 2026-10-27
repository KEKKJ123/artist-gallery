import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { beforeEach, expect, it } from 'vitest'
import PreviewOverlay from '../src/components/PreviewOverlay.vue'
import SidePanel from '../src/components/SidePanel.vue'
import ThumbCell from '../src/components/ThumbCell.vue'
import { useInboxStore } from '../src/stores/inbox.js'

const unavailable = {
  id: 42, state: 'inbox', file_id: null, orig_name: null, rel_path: null,
  file_url: null, thumb_url: null, ext: '', width: null, height: null,
  missing: false, display_status: 'unassigned', display_message: '展示文件待设置',
  source_hints: [], sources: [], tags: [], artist: null,
}
const normal = {
  ...unavailable, file_id: 7, orig_name: 'a.png', rel_path: 'images/_inbox/a.png',
  file_url: '/images/_inbox/a.png', thumb_url: '/thumbs/hash', ext: '.png',
  display_status: 'ok', display_message: null,
}
beforeEach(() => setActivePinia(createPinia()))

it('无展示文件仍有可选卡片和清楚提示，不加载空媒体', async () => {
  const wrapper = mount(ThumbCell, { props: { item: unavailable } })
  expect(wrapper.attributes('data-id')).toBe('42')
  expect(wrapper.find('.gone').text()).toBe('展示文件待设置')
  expect(wrapper.find('.name').text()).toBe('图片 #42')
  expect(wrapper.find('img').exists()).toBe(false)
  await wrapper.trigger('click')
  expect(wrapper.emitted('click')).toHaveLength(1)
  wrapper.unmount()
})

it('异常图详情不隐藏现有资料，也不声称文件已删除', () => {
  const store = useInboxStore()
  store.items = [{ ...unavailable, tags: [{ ns: 'character', name: '红豆' }] }]
  store.click(42)
  const wrapper = mount(SidePanel)
  expect(wrapper.text()).toContain('展示文件待设置')
  expect(wrapper.text()).toContain('未自动选择其他版本')
  expect(wrapper.text()).toContain('character:红豆')
  expect(wrapper.text()).not.toContain('文件丢失')
  wrapper.unmount()
})

it('预览未分配展示版本时无媒体元素和缩放，仍能关闭或切图', async () => {
  const store = useInboxStore()
  store.items = [unavailable, { ...normal, id: 43 }]
  store.openPreview(42)
  const wrapper = mount(PreviewOverlay)
  expect(wrapper.find('[role="status"]').text()).toContain('展示文件待设置')
  expect(wrapper.find('img').exists()).toBe(false)
  expect(wrapper.find('video').exists()).toBe(false)
  expect(wrapper.find('button[aria-label="放大"]').exists()).toBe(false)
  await wrapper.find('button[aria-label="下一张"]').trigger('click')
  expect(store.previewId).toBe(43)
  expect(wrapper.find('img').attributes('src')).toBe(normal.file_url)
  await wrapper.find('button[aria-label="关闭预览"]').trigger('click')
  expect(store.previewId).toBeNull()
  wrapper.unmount()
})

it('相同图片从正常版本变成未设置时清掉旧缩放和媒体', async () => {
  const store = useInboxStore()
  store.items = [normal]
  store.openPreview(42)
  const wrapper = mount(PreviewOverlay)
  const image = wrapper.find('img')
  Object.defineProperty(image.element, 'naturalWidth', { value: 800 })
  Object.defineProperty(image.element, 'naturalHeight', { value: 600 })
  await image.trigger('load')
  expect(wrapper.find('button[aria-label="放大"]').exists()).toBe(true)
  store.items = [unavailable]
  await flushPromises()
  expect(wrapper.find('img').exists()).toBe(false)
  expect(wrapper.find('button[aria-label="放大"]').exists()).toBe(false)
  expect(wrapper.find('[role="status"]').exists()).toBe(true)
  wrapper.unmount()
})

it('缩略图恢复或切换版本后，旧加载失败不永久遮住新图', async () => {
  const wrapper = mount(ThumbCell, { props: { item: normal } })
  await wrapper.find('img').trigger('error')
  expect(wrapper.find('img').exists()).toBe(false)
  await wrapper.setProps({ item: { ...normal, file_id: 8, thumb_url: '/thumbs/new-hash' } })
  await nextTick()
  expect(wrapper.find('img').attributes('src')).toBe('/thumbs/new-hash')
  wrapper.unmount()
})
