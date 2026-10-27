import { mount } from '@vue/test-utils'
import { flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { useGalleryNavigation } from '../src/composables/use-gallery-navigation.js'

let wrapper, navigation, view, navOpen, mq, setView
beforeEach(() => {
  window.history.replaceState(null, '', '/')
  mq = { matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }
  vi.stubGlobal('matchMedia', () => mq)
  view = ref({ kind: 'inbox', filter: 'all' })
  navOpen = ref(true)
  setView = vi.fn(async (next) => { view.value = next })
})
afterEach(() => {
  wrapper?.unmount()
  window.history.replaceState(null, '', '/')
  vi.unstubAllGlobals()
})
function start() {
  wrapper = mount({
    setup() {
      navigation = useGalleryNavigation({
        getView: () => view.value,
        setView,
        navOpen: () => navOpen.value,
        closeNav: () => (navOpen.value = false),
      })
      return () => null
    },
  })
}

it('启动读取并规整地址栏，显式 force 加载；没有图库 store 也能导航', async () => {
  window.history.replaceState(null, '', '/?view=archived&junk=1')
  start()
  await flushPromises()
  expect(setView).toHaveBeenCalledWith({ kind: 'archived' }, { force: true })
  expect(window.location.search).toBe('?view=archived')
})

it('手机选目录会关抽屉，桌面不会；筛选同样进地址栏', async () => {
  start()
  await flushPromises()
  expect(navigation.drawerOpen.value).toBe(true)
  navigation.go({kind:'archived'})
  expect(navOpen.value).toBe(false)
  expect(window.location.search).toBe('?view=archived')
  mq.matches = false
  mq.addEventListener.mock.calls[0][1]()
  navOpen.value = true
  navigation.setFilter('hint')
  expect(navOpen.value).toBe(true)
  expect(window.location.search).toBe('?filter=hint')
})

it('popstate 只切换视图，不新增历史；卸载清掉两个监听器', async () => {
  const remove = vi.spyOn(window, 'removeEventListener')
  start()
  await flushPromises()
  const push = vi.spyOn(window.history, 'pushState')
  window.history.replaceState(null, '', '/?view=archived')
  window.dispatchEvent(new PopStateEvent('popstate'))
  expect(setView).toHaveBeenLastCalledWith({ kind: 'archived' })
  expect(push).not.toHaveBeenCalled()
  wrapper.unmount()
  expect(mq.removeEventListener).toHaveBeenCalledWith('change', expect.any(Function))
  expect(remove).toHaveBeenCalledWith('popstate', expect.any(Function))
  vi.restoreAllMocks()
})

it('首次加载尚未完成就卸载，不再改新页面的地址栏', async () => {
  let release
  setView.mockImplementationOnce(() => new Promise((r) => (release = r)))
  start()
  wrapper.unmount()
  window.history.replaceState(null, '', '/?folder=next')
  release()
  await flushPromises()
  expect(window.location.search).toBe('?folder=next')
})
