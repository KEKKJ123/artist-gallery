// 只表达收件箱和已归档，不把磁盘目录误当作平台分类。
export const HINT_FILTERS = ['all', 'hint', 'nohint']
export const INBOX_VIEW = Object.freeze({ kind: 'inbox', filter: 'all' })
export function cleanFilter(f) {
  return HINT_FILTERS.includes(f) ? f : 'all'
}
export function parseView(search) {
  const q = new URLSearchParams(search || '')
  if (q.has('folder')) return { ...INBOX_VIEW, legacy: true }
  if (q.get('view') === 'archived') return { kind: 'archived' }
  return { kind: 'inbox', filter: cleanFilter(q.get('filter')) }
}
export function viewToUrl(view) {
  if (view.kind === 'archived') return '/?view=archived'
  const f = cleanFilter(view.filter)
  return f === 'all' ? '/' : `/?filter=${f}`
}
export function sameView(a, b) {
  return a.kind === b.kind && (a.kind === 'archived' || cleanFilter(a.filter) === cleanFilter(b.filter))
}
