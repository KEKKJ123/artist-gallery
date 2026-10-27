import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { useImageCollection } from '../composables/use-image-collection.js'
import { useImageSelection } from '../composables/use-image-selection.js'
import { fetchArchived, fetchInbox } from '../lib/api.js'
import { INBOX_VIEW, sameView } from '../lib/location.js'
import { useLibraryStore } from './library.js'

const PAGE = 200

// 只负责把当前视图、取图和图片交互接起来；具体职责各自可单独测试。
// 保留 inbox 这个入口名，组件不用因内部模块调整而整体改名。
export const useInboxStore = defineStore('inbox', () => {
  const view = ref({ ...INBOX_VIEW })
  const library = useLibraryStore()
  const collection = useImageCollection((offset) => {
    const v = view.value
    return v.kind === 'archived'
      ? fetchArchived(offset, PAGE)
      : fetchInbox(offset, PAGE, v.filter ?? 'all')
  })
  const selection = useImageSelection(collection.items)
  const isInbox = computed(() => view.value.kind === 'inbox')
  const hintFilter = computed(() => (isInbox.value ? (view.value.filter ?? 'all') : 'all'))

  async function load() {
    await Promise.all([
      collection.load().then((replaced) => {
        if (replaced) selection.prune()
      }),
      library.refresh(),
    ])
  }

  /** 相同视图不重复请求；强制刷新保留仍存在的选择，换视图则先清空旧内容。 */
  async function setView(next, { force = false } = {}) {
    const changed = !sameView(view.value, next)
    if (!force && !changed && (collection.items.value.length || collection.loading.value)) return
    view.value = next.kind === 'archived'
      ? { kind: 'archived' }
      : { kind: 'inbox', filter: next.filter ?? 'all', ...(next.legacy ? { legacy: true } : {}) }
    if (changed) {
      collection.reset()
      selection.reset()
    }
    await load()
  }

  // 显式列出界面契约：模块新增内部方法时不会顺带泄漏到 store 上。
  return {
    view, isInbox, hintFilter, setView, load,
    items: collection.items,
    total: collection.total,
    ids: collection.ids,
    hasMore: collection.hasMore,
    loading: collection.loading,
    error: collection.error,
    loadMore: collection.loadMore,
    selected: selection.selected,
    anchor: selection.anchor,
    focus: selection.focus,
    previewId: selection.previewId,
    selectedItems: selection.selectedItems,
    previewItem: selection.previewItem,
    click: selection.click,
    tapToggle: selection.tapToggle,
    selectAll: selection.selectAll,
    clearSelection: selection.clearSelection,
    moveFocus: selection.moveFocus,
    openPreview: selection.openPreview,
    closePreview: selection.closePreview,
    stepPreview: selection.stepPreview,
  }
})
