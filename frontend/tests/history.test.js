import { describe, expect, it, vi } from 'vitest'
import { readInitialView, syncHistory } from '../src/lib/history.js'
import { INBOX_VIEW } from '../src/lib/location.js'

// 一个最小的假 window：够 history.js 用，并且能模拟"用户点后退"
function fakeWindow(url = '/') {
  const stack = [url]
  let i = 0
  const listeners = new Set()
  const w = {
    get location() {
      const u = new URL(stack[i], 'http://localhost')
      return { pathname: u.pathname, search: u.search }
    },
    history: {
      pushState: (_s, _t, u) => {
        stack.splice(i + 1)
        stack.push(u)
        i++
      },
      replaceState: (_s, _t, u) => {
        stack[i] = u
      },
    },
    addEventListener: (t, fn) => t === 'popstate' && listeners.add(fn),
    removeEventListener: (t, fn) => t === 'popstate' && listeners.delete(fn),
    // 测试用：模拟浏览器的后退 / 前进
    back() {
      if (i > 0) {
        i--
        listeners.forEach((fn) => fn())
      }
    },
    forward() {
      if (i < stack.length - 1) {
        i++
        listeners.forEach((fn) => fn())
      }
    },
    _stack: stack,
    _listeners: listeners,
  }
  return w
}

describe('readInitialView', () => {
  it('从地址栏读出视图', () => {
    expect(readInitialView(fakeWindow('/'))).toEqual(INBOX_VIEW)
    expect(readInitialView(fakeWindow('/?folder=pixiv'))).toEqual({ kind: 'folder', path: 'pixiv' })
  })
})

describe('syncHistory', () => {
  it('push 写入历史；相同视图不重复写', () => {
    const w = fakeWindow('/')
    const h = syncHistory(() => INBOX_VIEW, vi.fn(), w)
    h.push({ kind: 'folder', path: 'pixiv' })
    h.push({ kind: 'folder', path: 'pixiv' })
    h.push({ kind: 'folder', path: '/pixiv/' }) // 规整后相同
    expect(w._stack).toEqual(['/', '/?folder=pixiv'])
  })

  it('后退 / 前进时通知上层，视图取自当时的地址栏', () => {
    const w = fakeWindow('/')
    const nav = vi.fn()
    const h = syncHistory(() => INBOX_VIEW, nav, w)
    h.push({ kind: 'folder', path: 'a' })
    h.push({ kind: 'folder', path: 'a/b' })
    w.back()
    expect(nav).toHaveBeenLastCalledWith({ kind: 'folder', path: 'a' })
    w.back()
    expect(nav).toHaveBeenLastCalledWith(INBOX_VIEW)
    w.forward()
    expect(nav).toHaveBeenLastCalledWith({ kind: 'folder', path: 'a' })
  })

  it('后退之后再 push，会丢掉"前进"那一段（和浏览器一致）', () => {
    const w = fakeWindow('/')
    const h = syncHistory(() => INBOX_VIEW, vi.fn(), w)
    h.push({ kind: 'folder', path: 'a' })
    w.back()
    h.push({ kind: 'folder', path: 'b' })
    expect(w._stack).toEqual(['/', '/?folder=b'])
  })

  it('align：把不规整的地址换成干净写法，且不新增历史', () => {
    const w = fakeWindow('/?folder=a//b/')
    const h = syncHistory(() => ({ kind: 'folder', path: 'a/b' }), vi.fn(), w)
    h.align()
    expect(w._stack).toEqual(['/?folder=a%2Fb'])
  })

  it('align：已经一致时什么也不做', () => {
    const w = fakeWindow('/')
    const rs = vi.spyOn(w.history, 'replaceState')
    syncHistory(() => INBOX_VIEW, vi.fn(), w).align()
    expect(rs).not.toHaveBeenCalled()
  })

  it('stop 之后不再收到后退通知（组件卸载时要清理）', () => {
    const w = fakeWindow('/')
    const nav = vi.fn()
    const h = syncHistory(() => INBOX_VIEW, nav, w)
    h.push({ kind: 'folder', path: 'a' })
    h.stop()
    expect(w._listeners.size).toBe(0)
    w.back()
    expect(nav).not.toHaveBeenCalled()
  })
})
