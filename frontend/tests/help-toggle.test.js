import { createPinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../src/App.vue'
import PreviewOverlay from '../src/components/PreviewOverlay.vue'
import { useInboxStore } from '../src/stores/inbox.js'

vi.mock('../src/lib/api.js', async () => {
  const actual = await vi.importActual('../src/lib/api.js')
  return {
    ...actual,
    fetchInbox: vi.fn(),
    fetchFolder: vi.fn(),
    fetchFolders: vi.fn(),
    fetchPlatforms: vi.fn(),
  }
})
import { fetchFolders, fetchInbox, fetchPlatforms } from '../src/lib/api.js'

const items = [1, 2].map((id) => ({
  id,
  rel_path: `images/_inbox/${id}.png`,
  orig_name: `${id}.png`,
  ext: '.png',
  file_url: `/images/_inbox/${id}.png`,
  thumb_url: `/thumbs/${id}`,
  source_hint: null,
  width: 800,
  height: 600,
}))
const SLASH = { key: '/', code: 'Slash' }
const QUESTION = { key: '?', code: 'Slash', shiftKey: true }
let wrapper
let inbox

beforeEach(async () => {
  localStorage.clear()
  window.history.replaceState(null, '', '/')
  vi.stubGlobal('matchMedia', vi.fn((query) => ({
    matches: query.includes('min-width'),
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })))
  fetchInbox.mockResolvedValue({ total: items.length, items })
  fetchFolders.mockResolvedValue({ inbox: 2, inbox_hinted: 0, archived: 0, folders: [] })
  fetchPlatforms.mockResolvedValue([])
  const pinia = createPinia()
  wrapper = mount(App, {
    attachTo: document.body,
    global: {
      plugins: [pinia],
      // 网格的布局观测与本测试无关；帮助、预览、顶栏和真正的全局键盘监听器都不替换。
      stubs: { ThumbGrid: { template: '<div class="test-grid" />' } },
    },
  })
  inbox = useInboxStore(pinia)
  await flushPromises()
})

afterEach(() => {
  wrapper.unmount()
  document.body.replaceChildren()
  window.history.replaceState(null, '', '/')
  localStorage.clear()
  vi.unstubAllGlobals()
})

const isOpen = () => wrapper.find('.dialog[aria-label="快捷键"]').exists()
async function press(options, target = document.body) {
  const e = new KeyboardEvent('keydown', { bubbles: true, cancelable: true, ...options })
  target.dispatchEvent(e)
  await nextTick()
  return e
}
async function selectImage() {
  inbox.click(1)
  await nextTick()
}

// 不能只测试 isHelpKey：必须把 App 和帮助组件放在一起，验证捕获/冒泡的事件顺序，
// 否则“刚关闭又被父组件重新打开”和“帮助上按 Esc 顺带把预览关了”都会漏掉。
describe('帮助键实际开关行为', () => {
  it.each([
    ['斜杠单键', SLASH],
    ['Shift+/', QUESTION],
    ['全角问号', { key: '？', code: 'Slash', shiftKey: true }],
    ['全角斜杠', { key: '／', code: 'Slash' }],
    ['输入法接管的物理 Slash 键', { key: 'Process', code: 'Slash', keyCode: 229 }],
  ])('%s：按一下开、再按一下关、第三下再开', async (_name, key) => {
    expect(isOpen()).toBe(false)
    expect((await press(key)).defaultPrevented).toBe(true)
    expect(isOpen()).toBe(true)
    await press(key)
    expect(isOpen()).toBe(false)
    await press(key)
    expect(isOpen()).toBe(true)
  })

  it('两种操作可以混用：/ 打开，Shift+/ 关闭，反过来也一样', async () => {
    await press(SLASH)
    await press(QUESTION)
    expect(isOpen()).toBe(false)
    await press(QUESTION)
    await press(SLASH)
    expect(isOpen()).toBe(false)
  })

  it('鼠标点顶栏打开后，可以用 / 关闭', async () => {
    await wrapper.get('button[aria-label="快捷键"]').trigger('click')
    expect(isOpen()).toBe(true)
    await press(SLASH)
    expect(isOpen()).toBe(false)
  })

  it('键盘打开后，鼠标点关闭；再按 / 仍能打开', async () => {
    await press(SLASH)
    await wrapper.get('.dialog button[aria-label="关闭"]').trigger('click')
    expect(isOpen()).toBe(false)
    await press(SLASH)
    expect(isOpen()).toBe(true)
  })

  it('长按时的重复 keydown 不会反复开关', async () => {
    await press(SLASH)
    for (let i = 0; i < 4; i++) await press({ ...SLASH, repeat: true })
    expect(isOpen()).toBe(true)
    await press(SLASH)
    expect(isOpen()).toBe(false)
    for (let i = 0; i < 4; i++) await press({ ...SLASH, repeat: true })
    expect(isOpen()).toBe(false)
  })

  it('帮助没有打开时，Esc 仍能取消选择；打开时 Esc 只关帮助，不取消选择', async () => {
    await selectImage()
    await press(SLASH)
    await press({ key: 'Escape' })
    expect(isOpen()).toBe(false)
    expect([...inbox.selected]).toEqual([1])
    await press({ key: 'Escape' })
    expect(inbox.selected.size).toBe(0)
  })

  it('帮助打开后，方向键和全选不会影响背后的图片', async () => {
    await selectImage()
    await press(SLASH)
    await press({ key: 'ArrowRight', code: 'ArrowRight' })
    await press({ key: 'a', code: 'KeyA', ctrlKey: true })
    expect([...inbox.selected]).toEqual([1])
    expect(inbox.focus).toBe(1)
  })

  it('滑块有焦点时也能按 / 开关，保留原有的焦点', async () => {
    const slider = wrapper.get('input[type="range"]').element
    slider.focus()
    await press(SLASH, slider)
    expect(isOpen()).toBe(true)
    await press(SLASH, slider)
    expect(isOpen()).toBe(false)
    expect(document.activeElement).toBe(slider)
  })

  it.each(['text', 'search', 'url'])('type=%s 输入框中的 / 和 ? 保持正常输入，不开关帮助', async (type) => {
    const input = document.createElement('input')
    input.type = type
    document.body.append(input)
    input.focus()
    expect((await press(SLASH, input)).defaultPrevented).toBe(false)
    expect(isOpen()).toBe(false)
    // 即使已有帮助显示，正在编辑的控件也不能被帮助快捷键抢走输入。
    await wrapper.get('button[aria-label="快捷键"]').trigger('click')
    expect(isOpen()).toBe(true)
    expect((await press(QUESTION, input)).defaultPrevented).toBe(false)
    expect(isOpen()).toBe(true)
  })

  it('textarea 和 contenteditable 中的 / 不触发帮助', async () => {
    const textarea = document.createElement('textarea')
    const editable = document.createElement('div')
    editable.contentEditable = 'true'
    // jsdom 没有实现 isContentEditable，补上浏览器本来就有的只读属性。
    Object.defineProperty(editable, 'isContentEditable', { value: true })
    document.body.append(textarea, editable)
    for (const target of [textarea, editable]) {
      expect((await press(SLASH, target)).defaultPrevented).toBe(false)
      expect(isOpen()).toBe(false)
    }
  })

  it('Ctrl/Alt/Meta + / 不抢浏览器和系统快捷键', async () => {
    for (const mod of ['ctrlKey', 'altKey', 'metaKey']) {
      expect((await press({ ...SLASH, [mod]: true })).defaultPrevented).toBe(false)
      expect(isOpen()).toBe(false)
    }
  })

  it('大图预览上按 / 可以开关帮助；Esc 先关帮助，再关预览', async () => {
    await selectImage()
    inbox.openPreview(1)
    await nextTick()
    expect(wrapper.find('.overlay').exists()).toBe(true)
    await press(SLASH)
    await press(SLASH)
    expect(isOpen()).toBe(false)
    expect(inbox.previewId).toBe(1)
    await press(SLASH)
    await press({ key: 'ArrowRight', code: 'ArrowRight' })
    await press({ key: '+', code: 'Equal' })
    expect(inbox.previewId).toBe(1)
    expect(wrapper.findComponent(PreviewOverlay).vm.view.scale).toBe(1)
    await press({ key: 'Escape', code: 'Escape' })
    expect(isOpen()).toBe(false)
    expect(inbox.previewId).toBe(1)
    await press({ key: 'Escape', code: 'Escape' })
    expect(inbox.previewId).toBeNull()
  })
})
