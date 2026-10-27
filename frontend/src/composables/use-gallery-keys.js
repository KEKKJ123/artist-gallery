import { onBeforeUnmount, onMounted } from 'vue'
import { isHelpKey, keyBelongsToControl } from '../lib/keys.js'

/** 网格层快捷键；动作由调用者提供，弹层仍在捕获阶段处理自己的键盘。 */
export function useGalleryKeys({
  helpOpen, drawerOpen, closeNav, getCols,
  selectAll, clearSelection, moveFocus, openPreview,
}) {
  function onKey(e) {
    // 焦点在文本框里时按键归它；滑块只拿走方向键（见 lib/keys.js）。
    // 以前把 INPUT 一律拦住，结果拖过一次"缩略图大小"滑块后，? 空格 Esc 等快捷键全部失效。
    if (keyBelongsToControl(e.target, e.key) || e.altKey) return
    // / 和 Shift+/ 都是帮助开关键。长按只处理第一次，不随着自动重复不断闪开闪关。
    if (isHelpKey(e)) {
      e.preventDefault()
      if (!e.repeat) helpOpen.value = !helpOpen.value
      return
    }
    // 帮助框打开时，背后的网格不响应按键（Esc 由帮助框自己处理）
    if (helpOpen.value) return
    // 预览和帮助各自在捕获阶段接管了按键；走到这里说明它们没开
    const mod = e.ctrlKey || e.metaKey

    if (mod && e.key.toLowerCase() === 'a') {
      e.preventDefault()
      selectAll()
    } else if (e.key === 'Escape') {
      // 手机上导航抽屉盖在图上：先关它
      if (drawerOpen()) closeNav()
      else clearSelection()
    } else if (e.key.startsWith('Arrow') && !mod) {
      e.preventDefault()
      moveFocus(e.key, getCols(), { shift: e.shiftKey })
    } else if (e.key === ' ' && !mod) {
      e.preventDefault() // 空格默认会滚动页面
      openPreview()
    }
  }

  onMounted(() => window.addEventListener('keydown', onKey))
  onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
}
