// 把"当前视图"同步到浏览器地址栏和历史记录，让后退键、刷新、收藏链接都能用。
// 只做两件事：① 启动时读地址栏；② 视图变化时 pushState，用户点后退/前进时通知回调。
// 不依赖 Vue，window 由调用方传入，测试里可以换成假的。

import { parseView, sameView, viewToUrl } from './location.js'

/** 读取启动时的视图。 */
export function readInitialView(win = window) {
  return parseView(win.location.search)
}

/**
 * 开始同步。
 *   getView()      返回当前视图（来自 store）
 *   onNavigate(v)  用户点浏览器后退/前进后，通知上层切换到视图 v
 * 返回 { push(view), stop() }：
 *   push 在"用户主动切换视图"时调用；如果视图没变就不会重复记一条历史。
 */
export function syncHistory(getView, onNavigate, win = window) {
  function onPop() {
    onNavigate(parseView(win.location.search))
  }
  win.addEventListener('popstate', onPop)

  return {
    push(view) {
      if (sameView(parseView(win.location.search), view)) return
      win.history.pushState(null, '', viewToUrl(view))
    },
    /** 用 replaceState 对齐地址栏（启动时把 `/?folder=a//b/` 规整成干净的写法，不产生新历史）。 */
    align() {
      const want = viewToUrl(getView())
      const have = win.location.pathname + win.location.search
      if (want !== have) win.history.replaceState(null, '', want)
    },
    stop() {
      win.removeEventListener('popstate', onPop)
    },
  }
}
