import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchNavigation, fetchPlatforms } from '../lib/api.js'

/** 图库级资料不属于某一组图片；各视图共享，失败时保留已有资料。 */
export const useLibraryStore = defineStore('library', () => {
  const nav = ref({ inbox: 0, inbox_hinted: 0, archived: 0 })
  const platformNames = ref({})
  const platforms = ref([])
  let navEpoch = 0
  let platformsLoaded = false
  let platformsPending = null

  async function loadNav() {
    const mine = ++navEpoch
    try {
      const next = await fetchNavigation()
      if (mine === navEpoch) nav.value = next
    } catch {
      // 导航失败不妨碍看图；旧统计继续保留。
    }
  }

  function loadPlatforms() {
    if (platformsLoaded) return Promise.resolve()
    if (platformsPending) return platformsPending
    platformsPending = (async () => {
      try {
        const list = await fetchPlatforms()
        platforms.value = list
        platformNames.value = Object.fromEntries(list.map((p) => [p.id, p.name]))
        platformsLoaded = true // 空列表也是成功，不能靠对象是否为空判断。
      } catch {
        // 失败后允许下次重试；暂时只用内置平台的显示信息。
      } finally {
        platformsPending = null
      }
    })()
    return platformsPending
  }

  async function refresh() {
    await Promise.all([loadNav(), loadPlatforms()])
  }

  return { nav, platformNames, platforms, loadNav, loadPlatforms, refresh }
})
