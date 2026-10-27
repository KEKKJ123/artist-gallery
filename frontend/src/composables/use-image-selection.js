import { computed, ref } from 'vue'
import * as sel from '../lib/selection.js'

/** 图片交互状态：数据由调用者传入，不知道 API、视图或图库资料。 */
export function useImageSelection(items) {
  const selected = ref(new Set())
  const anchor = ref(null)
  const focus = ref(null)
  const previewId = ref(null)
  const ids = computed(() => items.value.map((item) => item.id))
  const selectedItems = computed(() => items.value.filter((item) => selected.value.has(item.id)))
  const previewItem = computed(() => items.value.find((item) => item.id === previewId.value) ?? null)

  function apply(result) {
    selected.value = result.selected
    anchor.value = result.anchor
  }

  function reset() {
    apply(sel.clear())
    focus.value = null
    previewId.value = null
  }

  function prune() {
    apply(sel.prune(ids.value, selected.value, anchor.value))
    if (!ids.value.includes(focus.value)) focus.value = null
    if (!ids.value.includes(previewId.value)) previewId.value = null
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
    selected, anchor, focus, previewId, selectedItems, previewItem,
    click, tapToggle, selectAll, clearSelection, moveFocus,
    openPreview, closePreview, stepPreview, reset, prune,
  }
}
