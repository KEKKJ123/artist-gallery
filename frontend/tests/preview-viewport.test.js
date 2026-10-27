import { mount } from '@vue/test-utils'
import { nextTick, ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { usePreviewViewport } from '../src/composables/use-preview-viewport.js'

let wrapper, viewport, mediaId, video, close
const rect = { left: 0, top: 0, width: 800, height: 600 }
let now
beforeEach(() => {
  mediaId = ref(1)
  video = ref(false)
  close = vi.fn()
  now = 1000
  vi.spyOn(performance, 'now').mockImplementation(() => now)
  wrapper = mount({
    setup() {
      viewport = usePreviewViewport({ mediaId, video, onClose: close })
      return { stage: viewport.stage }
    },
    template: '<div ref="stage"><img /></div>',
  })
  viewport.stage.value.getBoundingClientRect = () => rect
  viewport.stage.value.setPointerCapture = vi.fn()
  viewport.onImgLoad({ target: { naturalWidth: 1600, naturalHeight: 1200 } })
})
afterEach(() => {
  wrapper.unmount()
  vi.restoreAllMocks()
})
function pointer(id, x, y, type = 'mouse', backdrop = false) {
  return {
    pointerId: id, clientX: x, clientY: y, pointerType: type, button: 0,
    target: backdrop ? viewport.stage.value : wrapper.get('img').element,
    currentTarget: viewport.stage.value,
  }
}

describe('独立预览舞台（无需 Pinia 或图库 API）', () => {
  it('读取原始尺寸并生成适应窗口样式与百分比', () => {
    expect(viewport.imgStyle.value.width).toBe('800px')
    expect(viewport.imgStyle.value.height).toBe('600px')
    expect(viewport.pct.value).toBe(50)
    viewport.toggleZoom()
    expect(viewport.pct.value).toBe(100)
    viewport.resetView()
    expect(viewport.view).toEqual({ scale: 1, x: 0, y: 0 })
  })

  it('鼠标滚轮放大；未加载尺寸或视频不接管滚轮', async () => {
    const event = { clientX: 400, clientY: 300, deltaY: -300, deltaMode: 0, preventDefault: vi.fn() }
    viewport.onWheel(event)
    expect(viewport.view.scale).toBeGreaterThan(1)
    expect(event.preventDefault).toHaveBeenCalledTimes(1)
    mediaId.value = 2
    await nextTick()
    viewport.onWheel(event)
    expect(event.preventDefault).toHaveBeenCalledTimes(1)
    viewport.onImgLoad({ target: { naturalWidth: 800, naturalHeight: 600 } })
    video.value = true
    viewport.onWheel(event)
    viewport.zoomIn()
    expect(viewport.view.scale).toBe(1)
  })

  it('点图片不会当成点背景，点空白才通过回调关闭', () => {
    const p = pointer(1, 400, 300)
    viewport.onPointerDown(p)
    viewport.onPointerUp(p)
    viewport.onBackdropClick()
    expect(close).not.toHaveBeenCalled()
    const b = pointer(2, 10, 10, 'mouse', true)
    viewport.onPointerDown(b)
    viewport.onPointerUp(b)
    viewport.onBackdropClick()
    expect(close).toHaveBeenCalledTimes(1)
  })

  it('放大后拖动并夹住边界；拖完即使背景发 click 也不关闭', () => {
    viewport.toggleZoom()
    viewport.onPointerDown(pointer(1, 400, 300, 'mouse', true))
    viewport.onPointerMove(pointer(1, 2400, 2300))
    expect(viewport.dragging.value).toBe(true)
    expect(viewport.view).toEqual({ scale: 2, x: 400, y: 300 })
    viewport.onPointerUp(pointer(1, 2400, 2300))
    viewport.onBackdropClick()
    expect(viewport.dragging.value).toBe(false)
    expect(close).not.toHaveBeenCalled()
  })

  it('双指同时缩放和平移；抬一指后继续拖动', () => {
    viewport.onPointerDown(pointer(1, 300, 300, 'touch'))
    viewport.onPointerDown(pointer(2, 500, 300, 'touch'))
    viewport.onPointerMove(pointer(1, 250, 350, 'touch'))
    viewport.onPointerMove(pointer(2, 650, 350, 'touch'))
    expect(viewport.view).toEqual({ scale: 2, x: 50, y: 50 })
    viewport.onPointerUp(pointer(2, 650, 350, 'touch'))
    viewport.onPointerMove(pointer(1, 270, 370, 'touch'))
    expect(viewport.view.x).toBe(70)
    expect(viewport.view.y).toBe(70)
    viewport.onPointerUp(pointer(1, 270, 370, 'touch'))
    expect(viewport.view.scale).toBe(2) // 不误当双击切回适应窗口
  })

  it('触屏双击只处理一次，浏览器补发的 dblclick 被忽略', () => {
    for (let n = 0; n < 2; n++) {
      const p = pointer(1, 400, 300, 'touch')
      viewport.onPointerDown(p)
      viewport.onPointerUp(p)
      now += 100
    }
    expect(viewport.view.scale).toBe(2)
    viewport.onDblClick({ clientX: 400, clientY: 300 })
    expect(viewport.view.scale).toBe(2)
  })

  it('切图清掉缩放、尺寸、未完成手势和上一张的双击计时', async () => {
    const p = pointer(1, 400, 300, 'touch')
    viewport.onPointerDown(p)
    viewport.onPointerUp(p) // 第一张图上轻点一次
    mediaId.value = 2
    await nextTick()
    expect(viewport.canZoom.value).toBe(false)
    expect(viewport.view.scale).toBe(1)
    viewport.onImgLoad({ target: { naturalWidth: 1600, naturalHeight: 1200 } })
    now += 100
    viewport.onPointerDown(p)
    viewport.onPointerUp(p) // 第二张图第一次轻点不能接上上一张，误认成双击
    expect(viewport.view.scale).toBe(1)
    viewport.onPointerDown(p)
    mediaId.value = 3
    await nextTick()
    viewport.onPointerMove(pointer(1, 900, 900, 'touch'))
    expect(viewport.dragging.value).toBe(false)
    expect(viewport.view).toEqual({ scale: 1, x: 0, y: 0 })
  })

  it('卸载时移除 resize 监听器', () => {
    const remove = vi.spyOn(window, 'removeEventListener')
    wrapper.unmount()
    expect(remove).toHaveBeenCalledWith('resize', expect.any(Function))
  })
})
