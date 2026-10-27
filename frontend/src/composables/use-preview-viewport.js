import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import {
  FIT,
  clampPan,
  distance,
  fitSize,
  midpoint,
  panByKey,
  percent,
  pinchFactor,
  pinchTo,
  step,
  toggleFit,
  wheelFactor,
  zoomAt,
} from '../lib/zoom.js'

/** 预览舞台：只管理尺寸、缩放和指针，不知道 store、帮助弹层或来源资料。 */
export function usePreviewViewport({ mediaId, video, onClose, zoomDisabled = () => false }) {
  // ---- 缩放状态 ----
  const stage = ref(null)
  const view = reactive({ ...FIT })
  const box = reactive({ w: 0, h: 0 }) // 舞台可用区域
  const img = reactive({ w: 0, h: 0 }) // 当前图原始像素
  const dragging = ref(false)
  const zoomed = computed(() => view.scale > 1.001)
  const canZoom = computed(() => !video.value && !zoomDisabled() && img.w > 0)
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
    mediaId,
    async () => {
      resetView()
      img.w = img.h = 0
      dragging.value = false
      pointers.clear()
      pinch = null
      moved = 0
      lastTap = 0
      downOnBackdrop = false
      lastPointerType = 'mouse'
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
    onClose()
  }

  // ---- 按钮 / 键盘 ----
  const zoomIn = () => canZoom.value && setView(step(view, 1, img, box))
  const zoomOut = () => canZoom.value && setView(step(view, -1, img, box))

  const toggleZoom = () => setView(toggleFit(view, 0, 0, img, box))
  const pan = (key) => setView(panByKey(view, key, img, box))

  onMounted(() => window.addEventListener('resize', measure))
  onBeforeUnmount(() => window.removeEventListener('resize', measure))

  return {
    stage, view, dragging, zoomed, canZoom, pct, imgStyle,
    resetView, zoomIn, zoomOut, toggleZoom, pan,
    onImgLoad, onWheel, onPointerDown, onPointerMove, onPointerUp,
    onDblClick, onBackdropClick,
  }
}
