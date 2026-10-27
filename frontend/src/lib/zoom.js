// 大图缩放与平移的计算（纯函数，不依赖 Vue / DOM，方便单独测试）。
//
// 约定：
//   状态 view = { scale, x, y }
//     scale  相对于"适应窗口"尺寸的倍数。1 = 刚好放进窗口；2 = 放大一倍。
//     x, y   图片中心相对于窗口中心的偏移（像素）。
//   尺寸 box = { w, h }   窗口里能放图的区域
//   尺寸 img = { w, h }   图片原始像素

export const MIN_SCALE = 1
export const MAX_SCALE = 16 // 相对"适应窗口"的倍数上限；再大也看不出更多细节

export const FIT = Object.freeze({ scale: 1, x: 0, y: 0 })

/** 图片"适应窗口"时的显示尺寸（只缩小，不放大小图）。 */
export function fitSize(img, box) {
  if (!img.w || !img.h || !box.w || !box.h) return { w: 0, h: 0 }
  const k = Math.min(1, box.w / img.w, box.h / img.h)
  return { w: img.w * k, h: img.h * k }
}

/** 100% 对应的 scale：图片 1 个像素 = 屏幕 1 个像素。小图适应窗口时本来就是 100%，返回 1。 */
export function actualScale(img, box) {
  const fit = fitSize(img, box)
  if (!fit.w) return 1
  return Math.max(1, img.w / fit.w)
}

export function clampScale(s) {
  if (!Number.isFinite(s)) return 1
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, s))
}

/**
 * 限制平移范围：图比窗口大的方向，不能拖出空白；图比窗口小的方向，固定居中。
 * 这样放大后怎么拖都不会"把图拖丢"。
 */
export function clampPan(view, img, box) {
  const fit = fitSize(img, box)
  const w = fit.w * view.scale
  const h = fit.h * view.scale
  const maxX = Math.max(0, (w - box.w) / 2)
  const maxY = Math.max(0, (h - box.h) / 2)
  return {
    scale: view.scale,
    x: bound(view.x, maxX),
    y: bound(view.y, maxY),
  }
}

// 把 v 限制在 [-max, max]。+ 0 把 -0 规整成 0：
// 否则"固定居中"时会得到 -0，严格比较和"是否已居中"的判断都会出意外。
function bound(v, max) {
  return Math.min(max, Math.max(-max, v)) + 0
}

/**
 * 以窗口内某一点（px, py，相对窗口中心）为不动点缩放到 nextScale。
 * 这是"光标指到哪里就放大哪里"的数学：缩放前后，光标下的那个图片点保持不动。
 * 缩回 1 倍（适应窗口）时直接居中，避免残留偏移。
 */
export function zoomAt(view, nextScale, px, py, img, box) {
  const s = clampScale(nextScale)
  if (s <= MIN_SCALE) return { ...FIT }
  const k = s / view.scale
  const next = { scale: s, x: px - (px - view.x) * k, y: py - (py - view.y) * k }
  return clampPan(next, img, box)
}

/** 滚轮一格对应的缩放倍率。deltaY 向上（<0）放大。用指数保证"放大再缩小"能回到原值。 */
export function wheelFactor(deltaY, deltaMode = 0) {
  // deltaMode 1 = 按"行"滚动（部分鼠标/浏览器），换算成像素量级
  const px = deltaMode === 1 ? deltaY * 16 : deltaY
  return Math.exp(-px * 0.0015)
}

/** 双指捏合：两指距离从 d0 变到 d1，倍率就是 d1/d0。 */
export function pinchFactor(d0, d1) {
  if (!(d0 > 0) || !(d1 > 0)) return 1
  return d1 / d0
}

export function distance(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y)
}

export function midpoint(a, b) {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }
}

/**
 * 双击 / 快捷键切换：当前接近"适应窗口" → 放大到 100%（若 100% 就是适应窗口则放大到 2 倍）；否则回到适应窗口。
 */
export function toggleFit(view, px, py, img, box) {
  if (view.scale > 1.01) return { ...FIT }
  const actual = actualScale(img, box)
  const target = actual > 1.05 ? actual : 2
  return zoomAt(view, target, px, py, img, box)
}

/** 按固定步进缩放（+ / - 键、按钮）：以窗口中心为准。 */
export function step(view, dir, img, box, ratio = 1.25) {
  return zoomAt(view, dir > 0 ? view.scale * ratio : view.scale / ratio, 0, 0, img, box)
}

/** 当前缩放对应的"屏幕像素比"（用于显示 100% / 250% 之类）。 */
export function percent(view, img, box) {
  const fit = fitSize(img, box)
  if (!fit.w || !img.w) return 100
  return Math.round(((fit.w * view.scale) / img.w) * 100)
}
