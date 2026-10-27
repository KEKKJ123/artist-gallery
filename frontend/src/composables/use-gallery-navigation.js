import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { readInitialView, syncHistory } from '../lib/history.js'

/** 导航只通过回调读写视图；不认识图片、选择或 Pinia store。 */
export function useGalleryNavigation({ getView, setView, navOpen, closeNav }) {
  const narrow = ref(false)
  const drawerOpen = computed(() => narrow.value && navOpen())
  const history = syncHistory(getView, setView)
  let mq
  let stopped = false
  const onMq = () => (narrow.value = mq.matches)

  function go(view) {
    history.push(view)
    setView(view)
    if (narrow.value) closeNav()
  }

  onMounted(async () => {
    mq = window.matchMedia('(max-width: 720px)')
    onMq()
    mq.addEventListener('change', onMq)
    await setView(readInitialView(), { force: true })
    // 首次加载在途时组件可能已被卸载，不能再改新页面的地址栏。
    if (!stopped) history.align()
  })
  onBeforeUnmount(() => {
    stopped = true
    mq?.removeEventListener('change', onMq)
    history.stop()
  })

  return {
    narrow, drawerOpen, go,
    goFolder: (path) => go({ kind: 'folder', path }),
    setFilter: (filter) => go({ kind: 'inbox', filter }),
  }
}
