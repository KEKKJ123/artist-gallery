import { describe, expect, it } from 'vitest'
import {
  FIT,
  MAX_SCALE,
  actualScale,
  clampPan,
  clampScale,
  distance,
  fitSize,
  midpoint,
  percent,
  pinchFactor,
  step,
  toggleFit,
  wheelFactor,
  zoomAt,
} from '../src/lib/zoom.js'

const box = { w: 1000, h: 600 }
const big = { w: 4000, h: 3000 } // 比窗口大：适应窗口时会缩小
const small = { w: 200, h: 100 } // 比窗口小：适应窗口时保持原大小

describe('fitSize / actualScale', () => {
  it('大图按窗口缩小，保持比例', () => {
    // 4000x3000 放进 1000x600：被高度限制，k = 0.2
    expect(fitSize(big, box)).toEqual({ w: 800, h: 600 })
  })

  it('小图不放大', () => {
    expect(fitSize(small, box)).toEqual({ w: 200, h: 100 })
  })

  it('100% 对应的倍数：大图是 4000/800 = 5，小图就是 1', () => {
    expect(actualScale(big, box)).toBe(5)
    expect(actualScale(small, box)).toBe(1)
  })

  it('尺寸缺失时不崩溃', () => {
    expect(fitSize({ w: 0, h: 0 }, box)).toEqual({ w: 0, h: 0 })
    expect(actualScale({ w: 0, h: 0 }, box)).toBe(1)
  })
})

describe('clampScale', () => {
  it('限制在 1 到上限之间，非数字回到 1', () => {
    expect(clampScale(0.3)).toBe(1)
    expect(clampScale(999)).toBe(MAX_SCALE)
    expect(clampScale(NaN)).toBe(1)
    expect(clampScale(Infinity)).toBe(1)
  })
})

describe('clampPan：拖动不能把图拖丢', () => {
  it('图在某方向比窗口小：固定居中', () => {
    // 小图放大到 2 倍仍是 400x200，比 1000x600 的窗口小，不允许偏移
    const v = clampPan({ scale: 2, x: 300, y: -200 }, small, box)
    expect(v).toEqual({ scale: 2, x: 0, y: 0 })
  })

  it('图比窗口大：最多拖到图边缘贴住窗口边缘', () => {
    // 大图适应后 800x600，放大 2 倍 = 1600x1200；窗口 1000x600
    // 水平可拖 (1600-1000)/2 = 300，垂直可拖 (1200-600)/2 = 300
    const v = clampPan({ scale: 2, x: 9999, y: -9999 }, big, box)
    expect(v.x).toBe(300)
    expect(v.y).toBe(-300)
  })

  it('范围内的偏移原样保留', () => {
    expect(clampPan({ scale: 2, x: 100, y: -50 }, big, box)).toEqual({ scale: 2, x: 100, y: -50 })
  })
})

describe('zoomAt：以光标为不动点', () => {
  // 图片上某点相对窗口中心的位置：p = center + offset + (点在图中的坐标 * scale)
  // 不动点的含义：缩放前后，"光标下的图片点"屏幕位置不变。
  const pointUnder = (view, px, py) => ({
    u: (px - view.x) / view.scale, // 光标下的点，在"适应窗口尺寸图"中的坐标
    v: (py - view.y) / view.scale,
  })

  it('放大后光标下仍是同一个图片点', () => {
    const start = { scale: 2, x: 40, y: -30 }
    const px = 150
    const py = 80
    const before = pointUnder(start, px, py)
    const after = zoomAt(start, 4, px, py, big, box)
    const now = pointUnder(after, px, py)
    expect(now.u).toBeCloseTo(before.u, 6)
    expect(now.v).toBeCloseTo(before.v, 6)
  })

  it('缩回 1 倍：直接居中，不残留偏移', () => {
    expect(zoomAt({ scale: 3, x: 120, y: 80 }, 1, 50, 50, big, box)).toEqual(FIT)
    expect(zoomAt({ scale: 3, x: 120, y: 80 }, 0.2, 50, 50, big, box)).toEqual(FIT)
  })

  it('不超过倍数上限', () => {
    expect(zoomAt(FIT, 999, 0, 0, big, box).scale).toBe(MAX_SCALE)
  })

  it('放大结果始终落在可拖动范围内', () => {
    const v = zoomAt(FIT, 3, 480, 280, big, box) // 在窗口右下角附近放大
    const c = clampPan(v, big, box)
    expect(v).toEqual(c)
  })

  it('放大再缩回同一倍数：位置回到原处（指数滚轮保证可逆）', () => {
    const f = wheelFactor(-120)
    const a = zoomAt(FIT, f, 0, 0, big, box)
    const back = zoomAt(a, a.scale * (1 / f), 0, 0, big, box)
    expect(back).toEqual(FIT)
  })
})

describe('wheelFactor / pinchFactor', () => {
  it('向上滚放大，向下滚缩小', () => {
    expect(wheelFactor(-100)).toBeGreaterThan(1)
    expect(wheelFactor(100)).toBeLessThan(1)
    expect(wheelFactor(0)).toBe(1)
  })

  it('一上一下互相抵消', () => {
    expect(wheelFactor(-80) * wheelFactor(80)).toBeCloseTo(1, 10)
  })

  it('按"行"滚动的鼠标换算成像素量级，不会慢十几倍', () => {
    expect(wheelFactor(-3, 1)).toBeCloseTo(wheelFactor(-48, 0), 10)
  })

  it('捏合倍率 = 距离之比；距离无效时不缩放', () => {
    expect(pinchFactor(100, 200)).toBe(2)
    expect(pinchFactor(200, 100)).toBe(0.5)
    expect(pinchFactor(0, 100)).toBe(1)
    expect(pinchFactor(100, 0)).toBe(1)
  })
})

describe('几何小工具', () => {
  it('两点距离和中点', () => {
    expect(distance({ x: 0, y: 0 }, { x: 3, y: 4 })).toBe(5)
    expect(midpoint({ x: 0, y: 0 }, { x: 10, y: 20 })).toEqual({ x: 5, y: 10 })
  })
})

describe('toggleFit（双击）', () => {
  it('在适应窗口时：放大到 100%', () => {
    const v = toggleFit(FIT, 0, 0, big, box)
    expect(percent(v, big, box)).toBe(100)
  })

  it('已放大时：回到适应窗口', () => {
    expect(toggleFit({ scale: 3, x: 10, y: 10 }, 0, 0, big, box)).toEqual(FIT)
  })

  it('小图（适应窗口本来就是 100%）：放大到 2 倍而不是原地不动', () => {
    expect(toggleFit(FIT, 0, 0, small, box).scale).toBe(2)
  })

  it('放大到 100% 时以点击位置为中心', () => {
    const px = 200
    const py = 100
    const v = toggleFit(FIT, px, py, big, box)
    // 点击点（相对中心）应仍在原处：偏移与点击位置方向相反，且在可拖动范围内
    expect(v.x).toBeLessThan(0)
    expect(v.y).toBeLessThan(0)
    expect(clampPan(v, big, box)).toEqual(v)
  })
})

describe('step（+ / - 键）', () => {
  it('放大一档、缩小一档，以中心为准', () => {
    const up = step(FIT, 1, big, box)
    expect(up.scale).toBeCloseTo(1.25, 10)
    expect(up.x).toBe(0)
    expect(step(up, -1, big, box)).toEqual(FIT)
  })

  it('已是适应窗口时再缩小，仍是适应窗口', () => {
    expect(step(FIT, -1, big, box)).toEqual(FIT)
  })
})

describe('percent', () => {
  it('适应窗口时显示实际缩小到的百分比', () => {
    expect(percent(FIT, big, box)).toBe(20) // 800/4000
  })

  it('小图适应窗口就是 100%', () => {
    expect(percent(FIT, small, box)).toBe(100)
  })

  it('缺少尺寸时给 100，不出现 NaN', () => {
    expect(percent(FIT, { w: 0, h: 0 }, box)).toBe(100)
  })
})
