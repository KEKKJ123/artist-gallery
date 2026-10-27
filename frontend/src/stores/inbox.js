import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { ApiError, fetchInbox } from '../lib/api.js'
import * as sel from '../lib/selection.js'

const PAGE = 200

export const useInboxStore = defineStore('inbox', () => {
  const items = ref([])
  const total = ref(0)
  const loading = ref(false)
  const error = ref('')
  const selected = ref(new Set())
  const anchor = ref(null)
  const focus = ref(null) // 键盘焦点所在的图
  const previewId = ref(null) // 正在预览的图（空格）

  const ids = computed(() => items.value.map((i) => i.id))
  const hasMore = computed(() => items.value.length < total.value)
  const selectedItems = computed(() => items.value.filter((i) => selected.value.has(i.id)))
  const previewItem = computed(() => items.value.find((i) => i.id === previewId.value) ?? null)

  function apply(r) {
    selected.value = r.selected
    anchor.value = r.anchor
  }

  async function load() {
    loading.value = true
    error.value = ''
    try {
      const page = await fetchInbox(0, PAGE)
      items.value = page.items
      total.value = page.total
      apply(sel.prune(ids.value, selected.value, anchor.value))
      if (!ids.value.includes(focus.value)) focus.value = null
      if (previewId.value !== null && !ids.value.includes(previewId.value)) previewId.value = null
    } catch (e) {
      error.value = e instanceof ApiError ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  async function loadMore() {
    if (loading.value || !hasMore.value) return
    loading.value = true
    try {
      const page = await fetchInbox(items.value.length, PAGE)
      // 防御：别的地方同时在改库时，不要把同一张图加进去两次
      const have = new Set(ids.value)
      items.value = items.value.concat(page.items.filter((i) => !have.has(i.id)))
      total.value = page.total
    } catch (e) {
      error.value = e instanceof ApiError ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  // ---- 选择 ----
  // 鼠标点击：普通=只选这张；Ctrl/⌘=增减；Shift=范围；Ctrl+Shift=在原选择上追加范围
  function click(id, { ctrl = false, shift = false } = {}) {
    focus.value = id
    if (shift) apply(sel.selectRange(ids.value, selected.value, anchor.value, id, ctrl))
    else if (ctrl) apply(sel.toggle(selected.value, id))
    else apply(sel.selectOnly(id))
  }
  // 触屏"多选模式"下的点按：每次点都是增减
  function tapToggle(id) {
    focus.value = id
    apply(sel.toggle(selected.value, id))
  }
  function selectAll() {
    apply(sel.selectAll(ids.value))
  }
  function clearSelection() {
    apply(sel.clear())
  }
  function moveFocus(key, cols, { shift = false } = {}) {
    const next = sel.moveFocus(ids.value, focus.value, key, cols)
    if (next === null) return
    const first = focus.value === null // 第一次按方向键只是落下焦点
    focus.value = next
    if (shift && !first) apply(sel.selectRange(ids.value, selected.value, anchor.value ?? next, next))
    else if (!shift) apply(sel.selectOnly(next))
  }

  // ---- 预览 ----
  function openPreview(id = focus.value) {
    if (id !== null && id !== undefined) previewId.value = id
  }
  function closePreview() {
    previewId.value = null
  }
  function stepPreview(dir) {
    const i = ids.value.indexOf(previewId.value)
    if (i === -1) return
    const j = Math.min(ids.value.length - 1, Math.max(0, i + dir))
    previewId.value = ids.value[j]
    focus.value = ids.value[j]
  }

  return {
    items,
    total,
    loading,
    error,
    selected,
    anchor,
    focus,
    previewId,
    ids,
    hasMore,
    selectedItems,
    previewItem,
    load,
    loadMore,
    click,
    tapToggle,
    selectAll,
    clearSelection,
    moveFocus,
    openPreview,
    closePreview,
    stepPreview,
  }
})
