import { computed, ref } from 'vue'

/** 分页集合：只依赖取页函数，不认识视图、导航、选择或 Pinia。 */
export function useImageCollection(fetchPage) {
  const items = ref([])
  const total = ref(0)
  const loading = ref(false)
  const error = ref('')
  const ids = computed(() => items.value.map((item) => item.id))
  const hasMore = computed(() => items.value.length < total.value)
  let epoch = 0

  function reset() {
    ++epoch
    items.value = []
    total.value = 0
    loading.value = false
    error.value = ''
  }

  async function request(append) {
    if (append && (loading.value || !hasMore.value)) return false
    const mine = append ? epoch : ++epoch
    loading.value = true
    error.value = ''
    try {
      const page = await fetchPage(append ? items.value.length : 0)
      if (mine !== epoch) return false
      // 外部同时改库时，跨页可能重叠；每个 id 只保留一次。
      const have = new Set(append ? ids.value : [])
      const unique = page.items.filter((item) => {
        if (have.has(item.id)) return false
        have.add(item.id)
        return true
      })
      items.value = append ? items.value.concat(unique) : unique
      total.value = page.total
      return true
    } catch (e) {
      if (mine === epoch) error.value = e instanceof Error ? e.message : String(e)
      return false
    } finally {
      if (mine === epoch) loading.value = false
    }
  }

  return {
    items, total, ids, hasMore, loading, error, reset,
    load: () => request(false),
    loadMore: () => request(true),
  }
}
