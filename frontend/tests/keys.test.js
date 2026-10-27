import { describe, expect, it } from 'vitest'
import { isHelpKey, keyBelongsToControl, zoomKeyAction } from '../src/lib/keys.js'

const ev = (o) => ({ key: '', code: '', shiftKey: false, ctrlKey: false, metaKey: false, altKey: false, ...o })
const el = (tagName, extra = {}) => ({ tagName, isContentEditable: false, ...extra })

describe('isHelpKey：/ 和 ? 在各种输入状态下都要能认出来', () => {
  it('美式键盘 Shift+/ → ?', () => {
    expect(isHelpKey(ev({ key: '?', code: 'Slash', shiftKey: true }))).toBe(true)
  })

  it('中文输入法"中文标点"状态 → 全角 ？（线上 bug 的原因之一）', () => {
    expect(isHelpKey(ev({ key: '？', code: 'Slash', shiftKey: true }))).toBe(true)
  })

  it('输入法接管按键时 key 是 Process，只能靠物理键 Slash + Shift（线上 bug 的另一个原因）', () => {
    expect(isHelpKey(ev({ key: 'Process', code: 'Slash', shiftKey: true }))).toBe(true)
  })

  it('其他布局把 ? 放在别的物理键上：只要 key 是 ? 就行', () => {
    expect(isHelpKey(ev({ key: '?', code: 'Minus', shiftKey: true }))).toBe(true)
  })

  it('不带 Shift 的 / 单键也打开帮助，输入法吞键时仍认物理键', () => {
    expect(isHelpKey(ev({ key: '/', code: 'Slash' }))).toBe(true)
    expect(isHelpKey(ev({ key: 'Process', code: 'Slash' }))).toBe(true)
    expect(isHelpKey(ev({ key: '／', code: 'Slash' }))).toBe(true)
  })

  it('带 Ctrl / Alt / Meta 的组合不算，避免抢浏览器和系统的快捷键', () => {
    expect(isHelpKey(ev({ key: '?', code: 'Slash', shiftKey: true, ctrlKey: true }))).toBe(false)
    expect(isHelpKey(ev({ key: '?', code: 'Slash', shiftKey: true, altKey: true }))).toBe(false)
    expect(isHelpKey(ev({ key: '?', code: 'Slash', shiftKey: true, metaKey: true }))).toBe(false)
  })

  it('无关的键不算', () => {
    expect(isHelpKey(ev({ key: 'a', code: 'KeyA' }))).toBe(false)
    expect(isHelpKey(ev({ key: 'Process', code: 'KeyA', shiftKey: true }))).toBe(false)
  })
})

describe('zoomKeyAction：+ - 0 同样兼顾输入法与小键盘', () => {
  it.each([
    [{ key: '+', code: 'Equal', shiftKey: true }, 'in'],
    [{ key: '=', code: 'Equal' }, 'in'],
    [{ key: 'Process', code: 'Equal' }, 'in'],
    [{ key: '+', code: 'NumpadAdd' }, 'in'],
    [{ key: '-', code: 'Minus' }, 'out'],
    [{ key: '_', code: 'Minus', shiftKey: true }, 'out'],
    [{ key: 'Process', code: 'Minus' }, 'out'],
    [{ key: '-', code: 'NumpadSubtract' }, 'out'],
    [{ key: '0', code: 'Digit0' }, 'fit'],
    [{ key: 'Process', code: 'Digit0' }, 'fit'],
    [{ key: '0', code: 'Numpad0' }, 'fit'],
  ])('%j → %s', (o, want) => {
    expect(zoomKeyAction(ev(o))).toBe(want)
  })

  it('Ctrl+= / Ctrl+- / Ctrl+0 是浏览器自己的页面缩放，不接管', () => {
    expect(zoomKeyAction(ev({ key: '=', code: 'Equal', ctrlKey: true }))).toBeNull()
    expect(zoomKeyAction(ev({ key: '-', code: 'Minus', ctrlKey: true }))).toBeNull()
    expect(zoomKeyAction(ev({ key: '0', code: 'Digit0', metaKey: true }))).toBeNull()
  })

  it('其他键返回 null', () => {
    expect(zoomKeyAction(ev({ key: 'a', code: 'KeyA' }))).toBeNull()
    expect(zoomKeyAction(ev({ key: 'ArrowLeft', code: 'ArrowLeft' }))).toBeNull()
  })
})

describe('keyBelongsToControl：焦点在控件上时，这个键归谁', () => {
  it('文本输入框：所有键都归它', () => {
    for (const type of ['text', 'search', 'number', 'email']) {
      expect(keyBelongsToControl(el('INPUT', { type }), '?')).toBe(true)
      expect(keyBelongsToControl(el('INPUT', { type }), 'ArrowLeft')).toBe(true)
    }
    expect(keyBelongsToControl(el('TEXTAREA'), ' ')).toBe(true)
    expect(keyBelongsToControl(el('SELECT'), 'ArrowDown')).toBe(true)
    expect(keyBelongsToControl(el('DIV', { isContentEditable: true }), 'a')).toBe(true)
  })

  it('没写 type 的 input 按 text 处理', () => {
    expect(keyBelongsToControl(el('INPUT', { type: '' }), 'a')).toBe(true)
    expect(keyBelongsToControl(el('INPUT'), 'a')).toBe(true)
  })

  it('滑块：只有方向键等归它，? / 空格 / Esc 照常当快捷键（线上 bug 的第三个原因）', () => {
    const slider = el('INPUT', { type: 'range' })
    expect(keyBelongsToControl(slider, 'ArrowLeft')).toBe(true)
    expect(keyBelongsToControl(slider, 'ArrowUp')).toBe(true)
    expect(keyBelongsToControl(slider, 'Home')).toBe(true)
    expect(keyBelongsToControl(slider, 'PageDown')).toBe(true)
    expect(keyBelongsToControl(slider, '?')).toBe(false)
    expect(keyBelongsToControl(slider, ' ')).toBe(false)
    expect(keyBelongsToControl(slider, 'Escape')).toBe(false)
    expect(keyBelongsToControl(slider, 'a')).toBe(false)
  })

  it('按钮、复选框、页面本身：不拦', () => {
    expect(keyBelongsToControl(el('BUTTON'), '?')).toBe(false)
    expect(keyBelongsToControl(el('INPUT', { type: 'checkbox' }), '?')).toBe(false)
    expect(keyBelongsToControl(el('BODY'), '?')).toBe(false)
  })

  it('目标缺失或不是元素时不崩溃', () => {
    expect(keyBelongsToControl(null, 'a')).toBe(false)
    expect(keyBelongsToControl(undefined, 'a')).toBe(false)
    expect(keyBelongsToControl(window, 'a')).toBe(false)
  })
})
