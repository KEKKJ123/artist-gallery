<script setup>
import { ChevronLeft, ChevronRight, Maximize, X, ZoomIn, ZoomOut } from '@lucide/vue'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { hintLabel, isVideo } from '../lib/format.js'
import { hintBadge } from '../lib/platforms.js'
import PlatformBadge from './PlatformBadge.vue'
import {
  FIT,
  clampPan,
  distance,
  fitSize,
  midpoint,
  percent,
  pinchFactor,
  pinchTo,
  step,
  toggleFit,
  wheelFactor,
  zoomAt,
} from '../lib/zoom.js'
import { zoomKeyAction } from '../lib/keys.js'
import { useInboxStore } from '../stores/inbox.js'

const inbox = useInboxStore()
const item = computed(() => inbox.previewItem)
const video = computed(() => item.value && isVideo(item.value.ext))
const badge = computed(() => (item.value ? hintBadge(item.value.source_hint, inbox.platformNames) : null))
const pos = computed(() => {
  const i = inbox.ids.indexOf(inbox.previewId)
  return i === -1 ? '' : `${i + 1} / ${inbox.ids.length}`
})

// ---- 缩放状态 ----
const stage = ref(null)
const view = reactive({ ...FIT })
const box = reactive({ w: 0, h: 0 }) // 舞台可用区域
const img = reactive({ w: 0, h: 0 }) // 当前图原始像素
const dragging = ref(false)
const zoomed = computed(() => view.scale > 1.001)
const canZoom = computed(() => !video.value && img.w > 0)
const pct = computed(() => percent(view, img, box))

function setView(v) {
  view.scale = v.scale
  view.x = v.x
  view.y = v.y
}
function resetView() {
  setView(FIT)
}
function measure() {
  if (!stage.value) return
  const r = stage.value.getBoundingClientRect()
  box.w = r.width
  box.h = r.height
  if (zoomed.value) setView(clampPan(view, img, box)) // 窗口变了（旋转手机），拖动范围跟着变
}
function onImgLoad(e) {
  img.w = e.target.naturalWidth
  img.h = e.target.naturalHeight
  measure()
}

// 切图时回到适应窗口，并把旧图的尺寸清掉（新图 load 之前不能用旧尺寸算）
watch(
  () => inbox.previewId,
  async () => {
    resetView()
    img.w = img.h = 0
    dragging.value = false
    pointers.clear()
    await nextTick()
    measure()
  },
)

// 图片显示尺寸：用适应窗口的尺寸做基准，再用 transform 缩放（GPU 合成，缩放时不重排）
const imgStyle = computed(() => {
  const fit = fitSize(img, box)
  return {
    width: fit.w ? `${fit.w}px` : undefined,
    height: fit.h ? `${fit.h}px` : undefined,
    transform: `translate3d(${view.x}px, ${view.y}px, 0) scale(${view.scale})`,
  }
})

// 把屏幕坐标换成"相对舞台中心"的坐标（zoom.js 的约定）
function toCenter(clientX, clientY) {
  const r = stage.value.getBoundingClientRect()
  return { x: clientX - (r.left + r.width / 2), y: clientY - (r.top + r.height / 2) }
}

// ---- 滚轮：缩放（以光标为中心）----
function onWheel(e) {
  if (!canZoom.value) return
  e.preventDefault()
  const p = toCenter(e.clientX, e.clientY)
  setView(zoomAt(view, view.scale * wheelFactor(e.deltaY, e.deltaMode), p.x, p.y, img, box))
}

// ---- 指针：单指/鼠标拖动，双指捏合 ----
const pointers = new Map() // pointerId -> {x, y}
let pinch = null // { d0, scale0, ... }
let moved = 0 // 本次按下后移动的距离：区分"点一下"和"拖动"
let lastTap = 0
// 本次按下是不是落在空白处。必须在"按下"那一刻记：之后为了拖动设置了指针捕获，
// 浏览器会把 pointerup / click 都改投给舞台，到 click 时 e.target 永远是舞台，
// 再拿它判断"点的是不是空白"就会把点图片也当成点空白、误关预览。
let downOnBackdrop = false
// 最近一次按下的是鼠标还是手指。浏览器在双击手指后还会补发一个 dblclick，它是普通的
// MouseEvent、没有 pointerType，没法从事件本身分辨；只能靠"刚才按下的是什么"来判断，
// 否则触屏双击会被处理两次（自己判断一次、dblclick 再一次），放大后立刻又缩回去。
let lastPointerType = 'mouse'

function onPointerDown(e) {
  lastPointerType = e.pointerType
  downOnBackdrop = e.target === e.currentTarget
  moved = 0
  if (!canZoom.value || (e.pointerType === 'mouse' && e.button !== 0)) return
  stage.value.setPointerCapture?.(e.pointerId)
  pointers.set(e.pointerId, { x: e.clientX, y: e.clientY })
  if (pointers.size === 1) moved = 0
  if (pointers.size === 2) beginPinch()
  dragging.value = pointers.size === 1 && zoomed.value
}

// 双指手势开始（或从三指退回两指）：以"此刻"的视图和两指位置为基准。
// 之后每一帧都从这个基准算（见 zoom.js 的 pinchTo），所以不会累积误差。
function beginPinch() {
  const [a, b] = [...pointers.values()]
  pinch = {
    d0: distance(a, b),
    m0: toCenter(midpoint(a, b).x, midpoint(a, b).y), // 起始两指中点（相对舞台中心）
    start: { scale: view.scale, x: view.x, y: view.y },
  }
}

function onPointerMove(e) {
  const prev = pointers.get(e.pointerId)
  if (!prev) return
  const cur = { x: e.clientX, y: e.clientY }
  pointers.set(e.pointerId, cur)

  if (pointers.size === 2 && pinch) {
    const [a, b] = [...pointers.values()]
    const mid = midpoint(a, b)
    const m1 = toCenter(mid.x, mid.y)
    // 缩放（两指距离变化）和平移（两指中点移动）一起处理：起始中点下的图片点跟着当前中点走
    setView(pinchTo(pinch.start, pinch.m0, m1, pinchFactor(pinch.d0, distance(a, b)), img, box))
    moved = 99
    return
  }
  if (pointers.size === 1) {
    moved += Math.abs(cur.x - prev.x) + Math.abs(cur.y - prev.y)
    if (zoomed.value) {
      setView(clampPan({ scale: view.scale, x: view.x + cur.x - prev.x, y: view.y + cur.y - prev.y }, img, box))
    }
  }
}

function onPointerUp(e) {
  const wasSingle = pointers.size === 1
  pointers.delete(e.pointerId)
  if (pointers.size < 2) pinch = null
  else if (pointers.size === 2) beginPinch() // 三指退回两指：重新以此刻为基准，避免跳变
  if (pointers.size === 0) dragging.value = false
  // 捏合后抬起一根手指、另一根继续拖：pointermove 里按"上一次位置"算增量，天然接得上。
  // 但这时 moved 是 99（捏合过），所以松手不会被误判成"点一下"。

  // 触屏双击：没有 dblclick 事件的可靠保证（尤其是 touch-action 打开时），自己判断
  if (wasSingle && e.pointerType !== 'mouse' && moved < 10) {
    const now = performance.now()
    if (now - lastTap < 300) {
      lastTap = 0
      doubleTap(e.clientX, e.clientY)
    } else {
      lastTap = now
    }
  }
}

function doubleTap(cx, cy) {
  if (!canZoom.value) return
  const p = toCenter(cx, cy)
  setView(toggleFit(view, p.x, p.y, img, box))
}
function onDblClick(e) {
  // 只处理鼠标双击；触屏双击已在 onPointerUp 里处理过
  if (lastPointerType !== 'mouse' || !canZoom.value) return
  doubleTap(e.clientX, e.clientY)
}
// 点空白处关闭。条件：按下时就在空白处（见 downOnBackdrop），且没有拖动
function onBackdropClick() {
  if (!downOnBackdrop || moved > 5) return
  inbox.closePreview()
}

// ---- 按钮 / 键盘 ----
const zoomIn = () => canZoom.value && setView(step(view, 1, img, box))
const zoomOut = () => canZoom.value && setView(step(view, -1, img, box))

// 预览打开时，键盘由这里接管
function onKey(e) {
  if (!item.value) return
  if (e.key === 'Escape') {
    // 放大状态下，Esc 先回到适应窗口；再按一次才关闭
    if (zoomed.value) resetView()
    else inbox.closePreview()
  } else if (e.key === ' ') {
    inbox.closePreview()
  } else if (zoomKeyAction(e) === 'in') {
    zoomIn()
  } else if (zoomKeyAction(e) === 'out') {
    zoomOut()
  } else if (zoomKeyAction(e) === 'fit') {
    resetView()
  } else if (e.key.startsWith('Arrow')) {
    if (zoomed.value) {
      // 放大后方向键平移（每次 15% 窗口），不切图
      const k = { ArrowLeft: [1, 0], ArrowRight: [-1, 0], ArrowUp: [0, 1], ArrowDown: [0, -1] }[e.key]
      setView(clampPan({ scale: view.scale, x: view.x + k[0] * box.w * 0.15, y: view.y + k[1] * box.h * 0.15 }, img, box))
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      inbox.stepPreview(-1)
    } else {
      inbox.stepPreview(1)
    }
  } else {
    return
  }
  e.preventDefault()
  e.stopPropagation()
}
// 捕获阶段：抢在网格的快捷键之前处理
onMounted(() => {
  window.addEventListener('keydown', onKey, true)
  window.addEventListener('resize', measure)
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey, true)
  window.removeEventListener('resize', measure)
})

defineExpose({ view, pct })
</script>

<template>
  <div v-if="item" class="overlay" role="dialog" aria-label="大图预览">
    <div class="bar">
      <span class="title">{{ item.orig_name || item.rel_path }}</span>
      <span v-if="badge" class="hint">
        <PlatformBadge :platform="badge.platform" :uncertain="!badge.certain" :size="18" />
        {{ hintLabel(item.source_hint) }}
      </span>
      <span class="pos">{{ pos }}</span>
      <template v-if="canZoom">
        <button class="icon" aria-label="缩小" title="缩小（-）" :disabled="!zoomed" @click="zoomOut">
          <ZoomOut :size="18" />
        </button>
        <button
          class="pct"
          :title="zoomed ? '回到适应窗口（0）' : '放大到 100%（双击）'"
          @click="setView(toggleFit(view, 0, 0, img, box))"
        >
          {{ pct }}%
        </button>
        <button class="icon" aria-label="放大" title="放大（+）" @click="zoomIn"><ZoomIn :size="18" /></button>
        <button class="icon" aria-label="适应窗口" title="适应窗口（0）" :disabled="!zoomed" @click="resetView">
          <Maximize :size="18" />
        </button>
      </template>
      <button class="icon" aria-label="关闭预览" title="关闭（Esc）" @click="inbox.closePreview()">
        <X :size="18" />
      </button>
    </div>

    <button v-show="!zoomed" class="nav left" aria-label="上一张" @click="inbox.stepPreview(-1)">
      <ChevronLeft :size="28" />
    </button>
    <button v-show="!zoomed" class="nav right" aria-label="下一张" @click="inbox.stepPreview(1)">
      <ChevronRight :size="28" />
    </button>

    <div
      ref="stage"
      class="stage"
      :class="{ zoomed, dragging, zoomable: canZoom }"
      @click="onBackdropClick()"
      @wheel="onWheel"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerUp"
      @dblclick="onDblClick"
    >
      <!-- key：切图时强制重建，避免上一张的画面残留 -->
      <video v-if="video" :key="item.id" :src="item.file_url" controls autoplay muted loop playsinline />
      <img
        v-else
        :key="item.id"
        :src="item.file_url"
        :style="imgStyle"
        alt=""
        draggable="false"
        @load="onImgLoad"
      />
    </div>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  flex-direction: column;
  background: rgba(8, 9, 12, 0.92);
  color: #e8e9ee;
}
.bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: rgba(0, 0, 0, 0.4);
}
.title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hint {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 8px 2px 4px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.1);
  font-size: 12px;
  white-space: nowrap;
}
.pos {
  color: #a8aab6;
  font-size: 12px;
  white-space: nowrap;
}
.bar button,
.nav {
  flex: none;
  color: #e8e9ee;
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.2);
}
.bar button:hover:not(:disabled),
.nav:hover {
  background: rgba(255, 255, 255, 0.2);
}
.bar button:disabled {
  opacity: 0.35;
  cursor: default;
}
.pct {
  min-width: 56px;
  font-variant-numeric: tabular-nums;
}
.stage {
  flex: 1;
  min-height: 0;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  /* 接管触摸手势：否则浏览器会把双指捏合当成"整页缩放"、单指拖动当成滚动 */
  touch-action: none;
  user-select: none;
  -webkit-user-select: none;
}
.stage.zoomable {
  cursor: zoom-in;
}
.stage.zoomed {
  cursor: grab;
}
.stage.dragging {
  cursor: grabbing;
}
.stage img {
  flex: none;
  display: block;
  /* 缩放时以图片中心为原点（位置由 translate 控制）；不要过渡动画，否则跟手感很差 */
  transform-origin: center center;
  will-change: transform;
  /* 放大很多倍时保留像素感而不是糊成一团 */
  image-rendering: auto;
}
.stage.zoomed img {
  image-rendering: -webkit-optimize-contrast;
}
.stage video {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}
.nav {
  position: absolute;
  top: 50%;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 64px;
  padding: 0;
  transform: translateY(-50%);
}
.nav.left {
  left: 8px;
}
.nav.right {
  right: 8px;
}
@media (max-width: 600px) {
  .nav {
    opacity: 0.7;
  }
  .hint,
  .pos {
    display: none;
  }
}
</style>
