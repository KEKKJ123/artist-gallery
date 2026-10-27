import { describe, expect, it } from 'vitest'
import {
  clear,
  moveFocus,
  prune,
  selectAll,
  selectOnly,
  selectRange,
  toggle,
} from '../src/lib/selection.js'

const ids = [10, 11, 12, 13, 14, 15]
const S = (...xs) => new Set(xs)

describe('selectOnly / toggle', () => {
  it('单击只选一张，并记为起点', () => {
    expect(selectOnly(12)).toEqual({ selected: S(12), anchor: 12 })
  })

  it('toggle 增加和取消，不影响其他已选', () => {
    let r = toggle(S(10), 12)
    expect(r.selected).toEqual(S(10, 12))
    expect(r.anchor).toBe(12)
    r = toggle(r.selected, 10)
    expect(r.selected).toEqual(S(12))
  })

  it('不修改传入的集合', () => {
    const before = S(10)
    toggle(before, 11)
    expect(before).toEqual(S(10))
  })
})

describe('selectRange（Shift 点击）', () => {
  it('从起点到目标，含两端', () => {
    expect(selectRange(ids, S(11), 11, 14).selected).toEqual(S(11, 12, 13, 14))
  })

  it('目标在起点前面也行', () => {
    expect(selectRange(ids, S(14), 14, 11).selected).toEqual(S(11, 12, 13, 14))
  })

  it('范围替换原选择；Ctrl+Shift（additive）保留原选择', () => {
    expect(selectRange(ids, S(10, 11), 11, 13).selected).toEqual(S(11, 12, 13))
    expect(selectRange(ids, S(10, 11), 11, 13, true).selected).toEqual(S(10, 11, 12, 13))
  })

  it('起点不动：连续 Shift 点击以同一起点伸缩', () => {
    const r1 = selectRange(ids, S(11), 11, 14)
    const r2 = selectRange(ids, r1.selected, r1.anchor, 12)
    expect(r2.anchor).toBe(11)
    expect(r2.selected).toEqual(S(11, 12))
  })

  it('起点已经不在列表里（刷新后消失），退化为单选目标', () => {
    expect(selectRange(ids, S(99), 99, 13)).toEqual({ selected: S(13), anchor: 13 })
  })

  it('目标不在列表里，什么也不改', () => {
    const r = selectRange(ids, S(11), 11, 999)
    expect(r.selected).toEqual(S(11))
    expect(r.anchor).toBe(11)
  })
})

describe('selectAll / clear / prune', () => {
  it('全选与清空', () => {
    expect(selectAll(ids).selected.size).toBe(6)
    expect(selectAll([]).anchor).toBeNull()
    expect(clear()).toEqual({ selected: S(), anchor: null })
  })

  it('刷新后去掉不存在的 id，起点没了就置空', () => {
    const r = prune([10, 11], S(10, 12, 13), 12)
    expect(r.selected).toEqual(S(10))
    expect(r.anchor).toBeNull()
  })

  it('起点还在就保留', () => {
    expect(prune([10, 11], S(10), 10).anchor).toBe(10)
  })
})

describe('moveFocus（方向键，一行 3 列）', () => {
  it('左右一格，上下一行', () => {
    expect(moveFocus(ids, 11, 'ArrowRight', 3)).toBe(12)
    expect(moveFocus(ids, 11, 'ArrowLeft', 3)).toBe(10)
    expect(moveFocus(ids, 10, 'ArrowDown', 3)).toBe(13)
    expect(moveFocus(ids, 13, 'ArrowUp', 3)).toBe(10)
  })

  it('到边界就停住，不循环', () => {
    expect(moveFocus(ids, 10, 'ArrowLeft', 3)).toBe(10)
    expect(moveFocus(ids, 15, 'ArrowRight', 3)).toBe(15)
    expect(moveFocus(ids, 11, 'ArrowUp', 3)).toBe(10) // 第一行再往上，停在第一张
    expect(moveFocus(ids, 14, 'ArrowDown', 3)).toBe(15) // 最后一行再往下，停在最后一张
  })

  it('没有焦点时从第一张开始；空列表返回 null；其他键不动', () => {
    expect(moveFocus(ids, null, 'ArrowRight', 3)).toBe(10)
    expect(moveFocus([], null, 'ArrowRight', 3)).toBeNull()
    expect(moveFocus(ids, 12, 'a', 3)).toBe(12)
  })
})
