import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it } from 'vitest'
import { SIZE_MAX, SIZE_MIN, usePrefsStore } from '../src/stores/prefs.js'

const KEY = 'artist-gallery:prefs'

function fresh() {
  setActivePinia(createPinia())
  return usePrefsStore()
}

beforeEach(() => {
  localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
  // jsdom 没有 matchMedia；store 用它判断手机/电脑
  window.matchMedia = (q) => ({ matches: true, media: q, addEventListener() {}, removeEventListener() {} })
})

describe('默认值', () => {
  it('跟随系统、原比例、宽屏默认展开面板', () => {
    const p = fresh()
    expect(p.theme).toBe('system')
    expect(p.square).toBe(false)
    expect(p.panelOpen).toBe(true)
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false)
  })

  it('窄屏默认收起面板', () => {
    window.matchMedia = (q) => ({ matches: false, media: q })
    expect(fresh().panelOpen).toBe(false)
  })
})

describe('缩略图大小', () => {
  it('限制在上下限之内，非数字回到默认', () => {
    const p = fresh()
    p.setThumbSize(5)
    expect(p.thumbSize).toBe(SIZE_MIN)
    p.setThumbSize(99999)
    expect(p.thumbSize).toBe(SIZE_MAX)
    p.setThumbSize('abc')
    expect(p.thumbSize).toBe(180)
  })

  it('Ctrl+滚轮的步进也受限制', () => {
    const p = fresh()
    p.setThumbSize(SIZE_MAX)
    p.nudgeThumbSize(20)
    expect(p.thumbSize).toBe(SIZE_MAX)
  })
})

describe('主题', () => {
  it('依次切换 system → light → dark → system，并写到 <html>', async () => {
    const p = fresh()
    p.cycleTheme()
    await nextTick()
    expect(p.theme).toBe('light')
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
    p.cycleTheme()
    await nextTick()
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
    p.cycleTheme()
    await nextTick()
    expect(p.theme).toBe('system')
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false)
  })
})

describe('持久化', () => {
  it('改动写进 localStorage，新实例能读回来', async () => {
    const p = fresh()
    p.setThumbSize(260)
    p.square = true
    p.theme = 'dark'
    await nextTick()
    const q = fresh()
    expect(q.thumbSize).toBe(260)
    expect(q.square).toBe(true)
    expect(q.theme).toBe('dark')
  })

  it('存档损坏时用默认值，不报错', () => {
    localStorage.setItem(KEY, '{坏的json')
    const p = fresh()
    expect(p.theme).toBe('system')
    expect(p.thumbSize).toBe(180)
  })

  it('存档里有非法值时回到合法值', () => {
    localStorage.setItem(KEY, JSON.stringify({ theme: 'neon', thumbSize: 99999 }))
    const p = fresh()
    expect(p.theme).toBe('system')
    expect(p.thumbSize).toBe(SIZE_MAX)
  })
})
