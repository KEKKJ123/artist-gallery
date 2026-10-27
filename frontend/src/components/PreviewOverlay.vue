<script setup>
import { ChevronLeft, ChevronRight, Maximize, X, ZoomIn, ZoomOut } from '@lucide/vue'
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { usePreviewViewport } from '../composables/use-preview-viewport.js'
import { hintLabel, isVideo } from '../lib/format.js'
import { zoomKeyAction } from '../lib/keys.js'
import { hintBadge } from '../lib/platforms.js'
import { useInboxStore } from '../stores/inbox.js'
import { useLibraryStore } from '../stores/library.js'
import PlatformBadge from './PlatformBadge.vue'

// 帮助盖在大图预览上时，预览保持原状，但键盘必须交给最上层的帮助。
const props = defineProps({ suspended: Boolean })
const inbox = useInboxStore()
const library = useLibraryStore()
const item = computed(() => inbox.previewItem)
const video = computed(() => item.value && isVideo(item.value.ext))
const badge = computed(() => (item.value ? hintBadge(item.value.source_hint, library.platformNames) : null))
const pos = computed(() => {
  const i = inbox.ids.indexOf(inbox.previewId)
  return i === -1 ? '' : `${i + 1} / ${inbox.ids.length}`
})

const {
  stage, view, dragging, zoomed, canZoom, pct, imgStyle,
  resetView, zoomIn, zoomOut, toggleZoom, pan,
  onImgLoad, onWheel, onPointerDown, onPointerMove, onPointerUp,
  onDblClick, onBackdropClick,
} = usePreviewViewport({ mediaId: () => inbox.previewId, video, onClose: inbox.closePreview })

// 预览打开时，键盘由这里接管
function onKey(e) {
  if (!item.value || props.suspended) return
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
      pan(e.key)
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
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey, true)
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
          @click="toggleZoom"
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
