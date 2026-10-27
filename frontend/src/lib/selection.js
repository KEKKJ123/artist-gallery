// 多选逻辑（纯函数，不依赖 Vue，方便单独测试）。
//
// 数据约定：
//   ids      当前画面上所有图片的 id，按显示顺序排列（数组）
//   selected 已选中的 id 集合（Set）
//   anchor   最近一次"普通点击/Ctrl 点击"落下的 id，Shift 点击从它开始算范围
//
// 所有函数都返回新的 { selected, anchor }，不修改传入的对象。

/** 单击：只选这一张。 */
export function selectOnly(id) {
  return { selected: new Set([id]), anchor: id }
}

/** Ctrl（或手机上长按进入多选后的点按）：增减这一张，其余不变。 */
export function toggle(selected, id) {
  const next = new Set(selected)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  return { selected: next, anchor: id }
}

/**
 * Shift 点击：选中 anchor 到 id 之间（含两端）的所有图。
 * additive = true（Ctrl+Shift）时保留原来已选的，否则范围替换原选择。
 * 找不到 anchor（比如列表刷新后它不见了）时退化为单选。
 */
export function selectRange(ids, selected, anchor, id, additive = false) {
  const a = ids.indexOf(anchor)
  const b = ids.indexOf(id)
  if (b === -1) return { selected: new Set(selected), anchor }
  if (a === -1) return selectOnly(id)
  const [from, to] = a < b ? [a, b] : [b, a]
  const next = additive ? new Set(selected) : new Set()
  for (let i = from; i <= to; i++) next.add(ids[i])
  return { selected: next, anchor } // anchor 不动：连续 Shift 点击以同一起点伸缩
}

/** Ctrl+A：全选。 */
export function selectAll(ids) {
  return { selected: new Set(ids), anchor: ids[0] ?? null }
}

/** Esc：清空。 */
export function clear() {
  return { selected: new Set(), anchor: null }
}

/** 列表刷新后（比如归档了几张）去掉已经不存在的 id。 */
export function prune(ids, selected, anchor) {
  const alive = new Set(ids)
  const next = new Set([...selected].filter((i) => alive.has(i)))
  return { selected: next, anchor: alive.has(anchor) ? anchor : null }
}

/**
 * 方向键移动焦点。cols 是当前一行有几列（上下键按行跳）。
 * 到边界就停在边界，不循环。focus 为空时从第一张开始。
 */
export function moveFocus(ids, focus, key, cols) {
  if (ids.length === 0) return null
  let i = ids.indexOf(focus)
  if (i === -1) return ids[0]
  const step = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -cols, ArrowDown: cols }[key]
  if (step === undefined) return focus
  i = Math.min(ids.length - 1, Math.max(0, i + step))
  return ids[i]
}
