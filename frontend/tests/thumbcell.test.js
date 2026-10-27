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
  source_hints: [],
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

  it('来源建议显示为左下角的站点标志（品牌色方块 + 首字母），不再是文字长条', () => {
    const a = mk({ source_hints: [{ platform: 'pixiv', post_id: '12345678', page: 0 }] })
    const logo = a.find('.hint-logo')
    expect(logo.exists()).toBe(true)
    expect(logo.find('.ch').text()).toBe('P')
    expect(a.find('.hint').exists()).toBe(false) // 旧的文字角标已移除
    expect(logo.attributes('title')).toBe('可能是 Pixiv:12345678') // ID 只在悬停提示里，不占格子
    expect(a.find('.name').text()).toBe('疑似 12345678_p0')
    expect(logo.find('.pbadge').classes()).not.toContain('uncertain')
  })

  it('只知道站点、缺具体作品（X 的 media key）：标志带"待补充"小点', () => {
    const b = mk({ source_hints: [{ platform: 'x', post_id: null, page: null }] })
    expect(b.find('.hint-logo .ch').text()).toBe('X')
    expect(b.find('.hint-logo .pbadge').classes()).toContain('uncertain')
    expect(b.find('.hint-logo').attributes('title')).toBe('可能来自 X，需补链接')
  })

  it('自定义平台：用平台显示名的首字母，颜色稳定', () => {
    const w = mount(ThumbCell, {
      props: {
        item: { ...base, source_hints: [{ platform: 'lofter', post_id: '1', page: 0 }] },
        platformNames: { lofter: '乐乎' },
      },
    })
    expect(w.find('.hint-logo .ch').text()).toBe('乐')
  })

  it('没有建议就没有标志', () => {
    expect(mk().find('.hint-logo').exists()).toBe(false)
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
