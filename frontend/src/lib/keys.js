// 键盘事件的判断（纯函数，不依赖 Vue / DOM，方便测试）。
//
// 为什么不能只看 e.key：
//   - 中文输入法的"中文标点"状态下，Shift+/ 产生的是全角的 "？"，不是 "?"。
//   - 有些输入法即使在"英文模式"下也会接管按键，这时 e.key 是 "Process"（keyCode 229），
//     但 e.code 仍然是物理按键的名字（"Slash"）。
//   所以快捷键要同时看 e.key 和 e.code：e.key 管"字符对了"，e.code 管"物理键对了"。

/** 帮助开关键：/ 单键或 Shift+/；兼容全角标点和被输入法接管的物理 Slash 键。
 * 是否正在文本框里输入，由调用方用 keyBelongsToControl 判断，不能抢走输入框中的斜杠。
 * 长按产生的 repeat 事件仍属于帮助键，但调用方必须吞掉它而不反复开关。
 */
export function isHelpKey(e) {
  if (e.ctrlKey || e.metaKey || e.altKey) return false
  return ['/', '?', '／', '？'].includes(e.key) || e.code === 'Slash'
}

/**
 * 预览里的缩放键。返回 'in' | 'out' | 'fit' | null。
 * 同样兼顾输入法：e.key 不可靠时用 e.code（Equal=+/=，Minus=-/_，Digit0 / Numpad0=0）。
 * 小键盘的 + - 也认。
 */
export function zoomKeyAction(e) {
  if (e.ctrlKey || e.metaKey || e.altKey) return null
  const k = e.key
  const c = e.code
  if (k === '+' || k === '=' || c === 'Equal' || c === 'NumpadAdd') return 'in'
  if (k === '-' || k === '_' || c === 'Minus' || c === 'NumpadSubtract') return 'out'
  if (k === '0' || c === 'Digit0' || c === 'Numpad0') return 'fit'
  return null
}

// 这些 input 类型是"打字"的：按键应该留给输入框。滑块、复选框、按钮等不算。
const TEXT_INPUT_TYPES = new Set([
  'text',
  'search',
  'url',
  'tel',
  'email',
  'password',
  'number',
  'date',
  'datetime-local',
  'month',
  'time',
  'week',
])

/**
 * 当前按键是否应该留给页面上正在操作的控件，而不是当快捷键。
 *   el  事件目标（e.target）
 *   key e.key（用来区分滑块上的方向键）
 *
 * - 文本输入框 / textarea / select / contenteditable：所有键都留给它。
 * - 滑块（range）：只有方向键 / Home / End / PageUp / PageDown 留给它（用来调整数值），
 *   其他键（? 空格 Esc Ctrl+A……）照常当快捷键——否则用过一次滑块后，快捷键就全失效了。
 * - 其他（按钮、复选框、页面本身）：不拦。
 */
export function keyBelongsToControl(el, key) {
  if (!el || typeof el !== 'object') return false
  if (el.isContentEditable) return true
  const tag = el.tagName
  if (tag === 'TEXTAREA' || tag === 'SELECT') return true
  if (tag === 'INPUT') {
    const type = (el.type || 'text').toLowerCase()
    if (type === 'range') {
      return ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End', 'PageUp', 'PageDown'].includes(key)
    }
    return TEXT_INPUT_TYPES.has(type)
  }
  return false
}
