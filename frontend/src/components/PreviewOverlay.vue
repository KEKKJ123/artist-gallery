<script setup>
import { ChevronLeft, ChevronRight, X } from '@lucide/vue'
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { hintLabel, isVideo } from '../lib/format.js'
import { useInboxStore } from '../stores/inbox.js'

const inbox = useInboxStore()
const item = computed(() => inbox.previewItem)
const video = computed(() => item.value && isVideo(item.value.ext))
const pos = computed(() => {
  const i = inbox.ids.indexOf(inbox.previewId)
  return i === -1 ? '' : `${i + 1} / ${inbox.ids.length}`
})

// 预览打开时，键盘由这里接管：Esc/空格 关闭，左右键切图
function onKey(e) {
  if (!item.value) return
  if (e.key === 'Escape' || e.key === ' ') {
    inbox.closePreview()
  } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
    inbox.stepPreview(-1)
  } else if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
    inbox.stepPreview(1)
  } else {
    return
  }
  e.preventDefault()
  e.stopPropagation()
}
// 捕获阶段：抢在网格的快捷键之前处理
onMounted(() => window.addEventListener('keydown', onKey, true))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey, true))
</script>

<template>
  <div v-if="item" class="overlay" role="dialog" aria-label="大图预览" @click.self="inbox.closePreview()">
    <div class="bar">
      <span class="title">{{ item.orig_name || item.rel_path }}</span>
      <span v-if="hintLabel(item.source_hint)" class="hint">{{ hintLabel(item.source_hint) }}</span>
      <span class="pos">{{ pos }}</span>
      <button class="icon" aria-label="关闭预览" @click="inbox.closePreview()"><X :size="18" /></button>
    </div>

    <button class="nav left" aria-label="上一张" @click="inbox.stepPreview(-1)">
      <ChevronLeft :size="28" />
    </button>
    <button class="nav right" aria-label="下一张" @click="inbox.stepPreview(1)">
      <ChevronRight :size="28" />
    </button>

    <div class="stage" @click.self="inbox.closePreview()">
      <!-- key：切图时强制重建，避免上一张的画面残留 -->
      <video v-if="video" :key="item.id" :src="item.file_url" controls autoplay muted loop playsinline />
      <img v-else :key="item.id" :src="item.file_url" alt="" draggable="false" />
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
  gap: 12px;
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
  padding: 0 8px;
  border-radius: 4px;
  background: rgba(138, 146, 230, 0.3);
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
  color: #e8e9ee;
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.2);
}
.bar button:hover,
.nav:hover {
  background: rgba(255, 255, 255, 0.2);
}
.stage {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px 56px;
}
.stage img,
.stage video {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  user-select: none;
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
  .stage {
    padding: 8px 4px;
  }
  .nav {
    opacity: 0.7;
  }
}
</style>
