import { ref } from 'vue'
import { describe, expect, it } from 'vitest'
import { useImageSelection } from '../src/composables/use-image-selection.js'

describe('独立图片交互（不访问 API）', () => {
  it('只在调用方接纳新集合后 prune；仍存在的选择和预览保留', () => {
    const items = ref([1, 2, 3].map((id) => ({ id })))
    const s = useImageSelection(items)
    s.click(1)
    s.click(3, { ctrl: true })
    s.openPreview(3)
    items.value = [{ id: 3 }]
    s.prune()
    expect([...s.selected.value]).toEqual([3])
    expect(s.previewItem.value).toEqual({ id: 3 })
    items.value = []
    s.prune()
    expect(s.focus.value).toBeNull()
    expect(s.previewId.value).toBeNull()
    expect(s.anchor.value).toBeNull()
  })

  it('reset 同时清空选择、焦点和预览，但不修改输入集合', () => {
    const items = ref([{ id: 1 }])
    const s = useImageSelection(items)
    s.click(1)
    s.openPreview()
    s.reset()
    expect(s.selected.value.size).toBe(0)
    expect(s.previewId.value).toBeNull()
    expect(s.focus.value).toBeNull()
    expect(items.value).toEqual([{ id: 1 }])
  })
})
