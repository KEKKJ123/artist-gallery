import { describe, expect, it } from 'vitest'
import { aspectRatio, extLabel, hintLabel, hintShort, isVideo } from '../src/lib/format.js'

describe('hintLabel / hintShort', () => {
  it('有作品 ID：给出具体建议', () => {
    const h = { platform: 'pixiv', post_id: '12345678', page: 0 }
    expect(hintLabel(h)).toBe('可能是 Pixiv:12345678')
    expect(hintShort(h)).toBe('Pixiv 12345678')
  })

  it('只知道平台（X 的 media key）：提示需补链接', () => {
    const h = { platform: 'x', post_id: null, page: null }
    expect(hintLabel(h)).toBe('可能来自 X，需补链接')
    expect(hintShort(h)).toBe('X?')
  })

  it('自定义平台直接显示 id', () => {
    expect(hintLabel({ platform: 'lofter', post_id: '1' })).toBe('可能是 lofter:1')
  })

  it('没有建议返回 null', () => {
    expect(hintLabel(null)).toBeNull()
    expect(hintLabel({})).toBeNull()
    expect(hintShort(undefined)).toBeNull()
  })
})

describe('aspectRatio', () => {
  it('用真实宽高', () => {
    expect(aspectRatio({ width: 800, height: 400 })).toBe(2)
  })

  it('没有宽高（视频）用 4:3', () => {
    expect(aspectRatio({ width: null, height: null })).toBeCloseTo(4 / 3)
  })

  it('极端比例被限制，不会把网格撑坏', () => {
    expect(aspectRatio({ width: 10000, height: 100 })).toBe(2.5)
    expect(aspectRatio({ width: 100, height: 10000 })).toBe(0.4)
  })
})

describe('extLabel / isVideo', () => {
  it('扩展名大写去点', () => {
    expect(extLabel('.mp4')).toBe('MP4')
    expect(extLabel('')).toBe('')
  })

  it('GIF 不算视频', () => {
    expect(isVideo('.mp4')).toBe(true)
    expect(isVideo('.MOV')).toBe(true)
    expect(isVideo('.gif')).toBe(false)
    expect(isVideo('.png')).toBe(false)
  })
})
