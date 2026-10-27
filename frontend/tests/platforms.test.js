import { describe, expect, it } from 'vitest'
import { hintBadge, platformInfo } from '../src/lib/platforms.js'

describe('platformInfo', () => {
  it('内置平台：固定的名称、颜色、首字母', () => {
    expect(platformInfo('pixiv')).toMatchObject({ name: 'Pixiv', letter: 'P', color: '#0096fa' })
    expect(platformInfo('x')).toMatchObject({ name: 'X', letter: 'X' })
    expect(platformInfo('zerochan')).toMatchObject({ name: 'Zerochan', letter: 'Z' })
  })

  it('没有平台就返回 null（不画标志）', () => {
    expect(platformInfo(null)).toBeNull()
    expect(platformInfo('')).toBeNull()
    expect(platformInfo(undefined)).toBeNull()
  })

  it('自定义平台：首字母取显示名第一个字，没有显示名就用 id', () => {
    expect(platformInfo('lofter', { lofter: '乐乎' }).letter).toBe('乐')
    expect(platformInfo('lofter').letter).toBe('L')
    expect(platformInfo('lofter', { lofter: '乐乎' }).name).toBe('乐乎')
  })

  it('首字母按码点取，不会把 emoji 劈成乱码', () => {
    expect(platformInfo('e', { e: '🎨画廊' }).letter).toBe('🎨')
    expect(platformInfo('e', { e: '   ' }).letter).toBe('E') // 全空白的显示名按 id 兜底（名称为空白时 || 取 id）
  })

  it('自定义平台的颜色：同一个 id 永远同一种颜色，不同 id 大概率不同', () => {
    const a1 = platformInfo('lofter').color
    const a2 = platformInfo('lofter').color
    expect(a1).toBe(a2)
    const colors = new Set(['lofter', 'bilibili', 'fanbox', 'danbooru', 'twitter2', 'weibo', 'xhs'].map((i) => platformInfo(i).color))
    expect(colors.size).toBeGreaterThanOrEqual(6)
  })

  it('自定义平台的颜色固定亮度（hsl 的 L=38%），白色字母永远看得清', () => {
    for (const id of ['a', 'b', 'lofter', '中文平台', 'x'.repeat(50)]) {
      const c = platformInfo(id + '_custom').color
      expect(c).toMatch(/^hsl\(\d{1,3}, 55%, 38%\)$/)
    }
  })
})

describe('hintBadge', () => {
  it('有具体作品：certain，提示里带 ID', () => {
    const b = hintBadge({ platform: 'pixiv', post_id: '12345678', page: 0 })
    expect(b.certain).toBe(true)
    expect(b.platform.letter).toBe('P')
    expect(b.tooltip).toBe('可能是 Pixiv:12345678')
  })

  it('只知道站点：not certain，提示"需补链接"', () => {
    const b = hintBadge({ platform: 'x', post_id: null, page: null })
    expect(b.certain).toBe(false)
    expect(b.tooltip).toBe('可能来自 X，需补链接')
  })

  it('没有建议 / 建议残缺：返回 null', () => {
    expect(hintBadge(null)).toBeNull()
    expect(hintBadge(undefined)).toBeNull()
    expect(hintBadge({})).toBeNull()
    expect(hintBadge({ platform: '' })).toBeNull()
  })

  it('自定义平台用传入的显示名', () => {
    const b = hintBadge({ platform: 'lofter', post_id: '9', page: 0 }, { lofter: '乐乎' })
    expect(b.platform.name).toBe('乐乎')
    expect(b.tooltip).toBe('可能是 乐乎:9')
  })
})
