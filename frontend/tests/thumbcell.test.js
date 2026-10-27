import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ThumbCell from '../src/components/ThumbCell.vue'

const base = {
  id: 1,
  rel_path: 'images/_inbox/a.png',
  orig_name: 'a.png',
  ext: '.png',
  thumb_url: '/thumbs/abc',
  width: 800,
  height: 400,
  source_hint: null,
  missing: false,
}
const mk = (over = {}, props = {}) =>
  mount(ThumbCell, { props: { item: { ...base, ...over }, ...props } })

describe('ThumbCell 显示', () => {
  it('静态图显示缩略图，占位比例取自宽高', () => {
    const w = mk()
    expect(w.find('img').attributes('src')).toBe('/thumbs/abc')
    expect(w.find('.frame').attributes('style')).toContain('aspect-ratio: 2')
  })

  it('方形模式比例固定为 1', () => {
    expect(mk({}, { square: true }).find('.frame').attributes('style')).toContain('aspect-ratio: 1')
  })

  it('来源建议常驻显示；只知平台时用警示色', () => {
    const a = mk({ source_hint: { platform: 'pixiv', post_id: '12345678', page: 0 } })
    expect(a.find('.hint').text()).toBe('Pixiv 12345678')
    expect(a.find('.hint').classes()).not.toContain('weak')
    const b = mk({ source_hint: { platform: 'x', post_id: null, page: null } })
    expect(b.find('.hint').text()).toBe('X?')
    expect(b.find('.hint').classes()).toContain('weak')
  })

  it('没有建议就没有角标', () => {
    expect(mk().find('.hint').exists()).toBe(false)
  })

  it('视频没有缩略图：显示占位和格式名', () => {
    const w = mk({ ext: '.mp4', thumb_url: null, width: null, height: null })
    expect(w.find('img').exists()).toBe(false)
    expect(w.find('.placeholder').text()).toContain('MP4')
  })

  it('GIF 没有缩略图：显示占位，不是"文件丢失"', () => {
    const w = mk({ ext: '.gif', thumb_url: null })
    expect(w.find('.placeholder').text()).toContain('GIF')
    expect(w.find('.gone').exists()).toBe(false)
  })

  it('文件丢失时提示出来', () => {
    const w = mk({ thumb_url: null, missing: true })
    expect(w.find('.gone').text()).toBe('文件丢失')
  })

  it('缩略图加载失败后改显占位', async () => {
    const w = mk()
    await w.find('img').trigger('error')
    expect(w.find('img').exists()).toBe(false)
    expect(w.find('.placeholder').exists()).toBe(true)
  })
})

describe('ThumbCell 状态与事件', () => {
  it('选中和焦点体现在 class 与 aria 上', () => {
    const w = mk({}, { selected: true, focused: true })
    expect(w.classes()).toEqual(expect.arrayContaining(['selected', 'focused']))
    expect(w.attributes('aria-selected')).toBe('true')
  })

  it('点击和双击向上抛事件', async () => {
    const w = mk()
    await w.trigger('click')
    await w.trigger('dblclick')
    expect(w.emitted('click')).toHaveLength(1)
    expect(w.emitted('dblclick')).toHaveLength(1)
  })

  it('触屏长按 500ms 触发 longpress，且抬手那一下不算点击', async () => {
    const { vi } = await import('vitest')
    vi.useFakeTimers()
    const w = mk()
    await w.trigger('pointerdown', { pointerType: 'touch' })
    vi.advanceTimersByTime(520)
    expect(w.emitted('longpress')).toHaveLength(1)
    await w.trigger('pointerup', { pointerType: 'touch' })
    await w.trigger('click')
    expect(w.emitted('click')).toBeUndefined()
    vi.useRealTimers()
  })

  it('手指移动则取消长按；鼠标按下不触发长按', async () => {
    const { vi } = await import('vitest')
    vi.useFakeTimers()
    const w = mk()
    await w.trigger('pointerdown', { pointerType: 'touch' })
    await w.trigger('pointermove', { pointerType: 'touch' })
    vi.advanceTimersByTime(800)
    expect(w.emitted('longpress')).toBeUndefined()
    await w.trigger('pointerdown', { pointerType: 'mouse' })
    vi.advanceTimersByTime(800)
    expect(w.emitted('longpress')).toBeUndefined()
    vi.useRealTimers()
  })
})
