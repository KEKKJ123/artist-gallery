import { describe, expect, it } from 'vitest'
import {
  INBOX_VIEW,
  breadcrumbs,
  cleanPath,
  parentPath,
  parseView,
  sameView,
  viewToUrl,
} from '../src/lib/location.js'

describe('parseView', () => {
  it('没有参数 → 收件箱', () => {
    expect(parseView('')).toEqual(INBOX_VIEW)
    expect(parseView('?')).toEqual(INBOX_VIEW)
    expect(parseView(undefined)).toEqual(INBOX_VIEW)
    expect(parseView('?other=1')).toEqual(INBOX_VIEW)
  })

  it('folder=xxx → 文件夹', () => {
    expect(parseView('?folder=pixiv')).toEqual({ kind: 'folder', path: 'pixiv' })
  })

  it('folder 存在但为空 → 全部已归档', () => {
    expect(parseView('?folder=')).toEqual({ kind: 'folder', path: '' })
  })

  it('中文、空格、百分号能正确解码', () => {
    expect(parseView('?folder=' + encodeURIComponent('我的 收藏/红豆 100%'))).toEqual({
      kind: 'folder',
      path: '我的 收藏/红豆 100%',
    })
  })

  it('危险或畸形的路径被当作空（全部），不会原样带进去', () => {
    expect(parseView('?folder=..')).toEqual({ kind: 'folder', path: '' })
    expect(parseView('?folder=' + encodeURIComponent('a/../b'))).toEqual({ kind: 'folder', path: '' })
    expect(parseView('?folder=' + encodeURIComponent('a\\b'))).toEqual({ kind: 'folder', path: '' })
  })
})

describe('viewToUrl', () => {
  it('收件箱是根路径，不带参数', () => {
    expect(viewToUrl(INBOX_VIEW)).toBe('/')
  })

  it('文件夹转成 ?folder=，并正确转义', () => {
    expect(viewToUrl({ kind: 'folder', path: 'pixiv' })).toBe('/?folder=pixiv')
    expect(viewToUrl({ kind: 'folder', path: '' })).toBe('/?folder=')
    const u = viewToUrl({ kind: 'folder', path: '我的 收藏/100%' })
    expect(u).not.toMatch(/[ %]{2}/)
    expect(u).not.toContain(' ')
  })

  it('往返不变：parse(toUrl(v)) 等于 v', () => {
    for (const path of ['pixiv', '', '我的 收藏/红豆', 'a&b=c', '100%', 'x+y', '#tag', 'a?b']) {
      const v = { kind: 'folder', path }
      expect(parseView(viewToUrl(v).slice(1))).toEqual(v)
    }
    expect(parseView(viewToUrl(INBOX_VIEW).slice(1))).toEqual(INBOX_VIEW)
  })
})

describe('sameView', () => {
  it('同类才相同；路径规整后比较', () => {
    expect(sameView(INBOX_VIEW, { kind: 'inbox' })).toBe(true)
    expect(sameView(INBOX_VIEW, { kind: 'folder', path: '' })).toBe(false)
    expect(sameView({ kind: 'folder', path: 'a/b' }, { kind: 'folder', path: '/a/b/' })).toBe(true)
    expect(sameView({ kind: 'folder', path: 'a' }, { kind: 'folder', path: 'b' })).toBe(false)
  })
})

describe('cleanPath', () => {
  it('去首尾斜杠、空段和 .', () => {
    expect(cleanPath('/a//b/./c/')).toBe('a/b/c')
    expect(cleanPath('')).toBe('')
    expect(cleanPath(null)).toBe('')
    expect(cleanPath(undefined)).toBe('')
  })

  it('含 .. / 反斜杠 / NUL → 空', () => {
    expect(cleanPath('..')).toBe('')
    expect(cleanPath('a/../b')).toBe('')
    expect(cleanPath('a\\b')).toBe('')
    expect(cleanPath('a\0b')).toBe('')
  })
})

describe('breadcrumbs / parentPath', () => {
  it('逐级给出名称和累计路径', () => {
    expect(breadcrumbs('a/b/c')).toEqual([
      { name: 'a', path: 'a' },
      { name: 'b', path: 'a/b' },
      { name: 'c', path: 'a/b/c' },
    ])
    expect(breadcrumbs('')).toEqual([])
  })

  it('上一级', () => {
    expect(parentPath('a/b/c')).toBe('a/b')
    expect(parentPath('a')).toBe('')
    expect(parentPath('')).toBe('')
  })
})
