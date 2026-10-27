// 视图 ⇄ 网址 的转换（纯函数，不碰 window，方便测试）。
//
// 视图只有两种：
//   收件箱            → /                     （全部）
//                       /?filter=hint         （只看有来源建议的）
//                       /?filter=nohint       （只看没有建议的）
//   某文件夹          → /?folder=pixiv/子目录
//   全部已归档        → /?folder=              （folder 存在但为空）
//
// 为什么用查询参数而不是 /folder/pixiv：服务端对所有未知路径都返回同一个页面（见 server/app.py
// 的 spa_fallback），两种写法都能工作；但文件夹名可以含中文、空格、% 等字符，放在查询参数里
// 由 URLSearchParams 统一编解码，比手工处理路径转义不容易出错。

/** 收件箱的筛选项，与后端 core/inbox.py 的 HINT_FILTERS 一致。 */
export const HINT_FILTERS = ['all', 'hint', 'nohint']

/** 视图：{ kind: 'inbox', filter } 或 { kind: 'folder', path }（path 为空 = 全部已归档） */
export const INBOX_VIEW = Object.freeze({ kind: 'inbox', filter: 'all' })

/** 不认识的筛选值一律当 all（地址栏可能被手改、或来自旧链接），不报错。 */
export function cleanFilter(f) {
  return HINT_FILTERS.includes(f) ? f : 'all'
}

/** 从 location.search 解析出视图。无法识别的内容一律当作收件箱，不报错。 */
export function parseView(search) {
  const params = new URLSearchParams(search || '')
  if (params.has('folder')) return { kind: 'folder', path: cleanPath(params.get('folder')) }
  return { kind: 'inbox', filter: cleanFilter(params.get('filter')) }
}

/** 把视图写成要放进地址栏的相对网址（含开头的 `/`）。 */
export function viewToUrl(view) {
  if (view.kind === 'folder') {
    const q = new URLSearchParams()
    q.set('folder', cleanPath(view.path))
    return `/?${q.toString()}`
  }
  const f = cleanFilter(view.filter)
  return f === 'all' ? '/' : `/?filter=${f}`
}

/** 两个视图是否相同（用来避免重复往历史里压同一条）。 */
export function sameView(a, b) {
  if (a.kind !== b.kind) return false
  if (a.kind === 'inbox') return cleanFilter(a.filter) === cleanFilter(b.filter)
  return cleanPath(a.path) === cleanPath(b.path)
}

/**
 * 规整文件夹路径：去掉首尾 `/`，丢掉空段和 `.`；遇到 `..` 或反斜杠时整体当作空（= 全部）。
 * 这里只是为了让网址干净、不让奇怪的输入把界面搞坏；真正的安全校验在后端（BadFolderPath）。
 */
export function cleanPath(path) {
  const p = String(path ?? '')
  if (p.includes('\\') || p.includes('\0')) return ''
  const segs = p.split('/').filter((s) => s !== '' && s !== '.')
  if (segs.includes('..')) return ''
  return segs.join('/')
}

/** 面包屑：'a/b/c' → [{name:'a', path:'a'}, {name:'b', path:'a/b'}, {name:'c', path:'a/b/c'}] */
export function breadcrumbs(path) {
  const segs = cleanPath(path).split('/').filter(Boolean)
  return segs.map((name, i) => ({ name, path: segs.slice(0, i + 1).join('/') }))
}

/** 上一级文件夹路径；顶层文件夹的上一级是 ''（全部已归档）。 */
export function parentPath(path) {
  const p = cleanPath(path)
  return p.includes('/') ? p.slice(0, p.lastIndexOf('/')) : ''
}
