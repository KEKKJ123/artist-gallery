import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import SidePanel from '../src/components/SidePanel.vue'
import { useInboxStore } from '../src/stores/inbox.js'
import * as api from '../src/lib/api.js'
vi.mock('../src/lib/api.js', async () => ({ ...(await vi.importActual('../src/lib/api.js')), fetchFileSize: vi.fn() }))
let wrapper, inbox, pinia
beforeEach(() => {
  vi.resetAllMocks(); pinia = createPinia(); setActivePinia(pinia); inbox = useInboxStore()
  inbox.items = [1, 2].map((id) => ({ id, file_id: id, orig_name: `${id}.png`, tags: [], sources: [], source_hints: [] }))
})
afterEach(() => wrapper?.unmount())
it('未单选不读取；切图即清旧大小，旧请求返回不能覆盖新图', async () => {
  let resolveOld
  api.fetchFileSize.mockImplementation((id) => id === 1 ? new Promise((r) => { resolveOld = r }) : Promise.resolve({ file_id: 2, bytes: 2048 }))
  wrapper = mount(SidePanel, { global: { plugins: [pinia] } })
  expect(api.fetchFileSize).not.toHaveBeenCalled()
  inbox.click(1); await flushPromises()
  inbox.click(2); await flushPromises()
  expect(wrapper.text()).toContain('2.00 KiB')
  resolveOld({ file_id: 1, bytes: 99999 }); await flushPromises()
  expect(wrapper.text()).toContain('2.00 KiB')
  expect(wrapper.text()).not.toContain('99,999')
})
it('读取失败显示原因，不误报为零字节', async () => {
  api.fetchFileSize.mockRejectedValue(new Error('文件缺失'))
  wrapper = mount(SidePanel, { global: { plugins: [pinia] } })
  inbox.click(1); await flushPromises()
  expect(wrapper.text()).toContain('文件缺失')
  expect(wrapper.text()).not.toContain('0 字节')
})
