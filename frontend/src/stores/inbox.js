import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { ApiError, fetchFolder, fetchFolders, fetchInbox } from '../lib/api.js'
import { INBOX_VIEW, sameView } from '../lib/location.js'
import * as sel from '../lib/selection.js'

const PAGE = 200

// 这个 store 管"当前在看的那一组图"：收件箱，或某个文件夹。
// 选择、预览、键盘移动对两者完全一样，所以共用；只有"从哪取数据"不同（见 fetchPage）。
// （store 仍叫 inbox 是历史原因，改名会牵动一堆文件，没有收益。）
export const useInboxStore = defineStore('inbox', () => {
  const view = ref({ ...INBOX_VIEW }) // { kind:'inbox' } | { kind:'folder', path }
  const items = ref([])
  const total = ref(0)
  const loading = ref(false)
  const error = ref('')
  const selected = ref(new Set())
  const anchor = ref(null)
  const focus = ref(null) // 键盘焦点所在的图
  const previewId = ref(null) // 正在预览的图（空格）

  // 左侧导航的数据：收件箱张数、已归档总数、文件夹树
  const nav = ref({ inbox: 0, archived: 0, folders: [] })

  const ids = computed(() => items.value.map((i) => i.id))
  const hasMore = computed(() => items.value.length < total.value)
  const selectedItems = computed(() => items.value.filter((i) => selected.value.has(i.id)))
  const previewItem = computed(() => items.value.find((i) => i.id === previewId.value) ?? null)
  const isInbox = computed(() => view.value.kind === 'inbox')

  // 防止"慢请求覆盖新结果"：快速切换文件夹时，先发出的请求可能后返回。
  // 每次换视图 / 刷新都 +1，返回时发现自己已过期就丢弃。
  let epoch = 0

  function apply(r) {
    selected.value = r.selected
    anchor.value = r.anchor
  }

  function fetchPage(offset) {
    const v = view.value
    return v.kind === 'folder' ? fetchFolder(v.path, offset, PAGE) : fetchInbox(offset, PAGE)
  }

  async function loadNav() {
    try {
      nav.value = await fetchFolders()
    } catch {
      /* 导航加载失败不影响看图；错误会在主区域的请求里体现 */
    }
  }

  /** 切换视图。相同视图只刷新；不同视图先清空旧内容，避免短暂显示上一个文件夹的图。 */
  async function setView(next, { force = false } = {}) {
    if (!force && sameView(view.value, next) && (items.value.length || loading.value)) return
    const changed = !sameView(view.value, next)
    view.value = next.kind === 'folder' ? { kind: 'folder', path: next.path } : { ...INBOX_VIEW }
    if (changed) {
      items.value = []
      total.value = 0
      apply(sel.clear())
      focus.value = null
      previewId.value = null
    }
    await load()
  }

  async function load() {
    const mine = ++epoch
    loading.value = true
    error.value = ''
    try {
      const [page] = await Promise.all([fetchPage(0), loadNav()])
      if (mine !== epoch) return // 期间用户又切走了
      items.value = page.items
      total.value = page.total
      apply(sel.prune(ids.value, selected.value, anchor.value))
      if (!ids.value.includes(focus.value)) focus.value = null
      if (previewId.value !== null && !ids.value.includes(previewId.value)) previewId.value = null
    } catch (e) {
      if (mine !== epoch) return
      error.value = e instanceof ApiError ? e.message : String(e)
    } finally {
      if (mine === epoch) loading.value = false
    }
  }

  async function loadMore() {
    if (loading.value || !hasMore.value) return
    const mine = epoch
    loading.value = true
    try {
      const page = await fetchPage(items.value.length)
      if (mine !== epoch) return
      // 防御：别的地方同时在改库时，不要把同一张图加进去两次
      const have = new Set(ids.value)
      items.value = items.value.concat(page.items.filter((i) => !have.has(i.id)))
      total.value = page.total
    } catch (e) {
      if (mine !== epoch) return
      error.value = e instanceof ApiError ? e.message : String(e)
    } finally {
      if (mine === epoch) loading.value = false
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
    view,
    nav,
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
    isInbox,
    selectedItems,
    previewItem,
    setView,
    load,
    loadNav,
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
