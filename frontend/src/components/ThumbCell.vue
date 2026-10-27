<script setup>
import { Check, Film, Image, ImageOff } from '@lucide/vue'
import { computed, ref } from 'vue'
import { aspectRatio, extLabel, hintShort, isVideo } from '../lib/format.js'

const props = defineProps({
  item: { type: Object, required: true },
  selected: Boolean,
  focused: Boolean,
  square: Boolean,
  multiMode: Boolean, // 触屏多选模式：始终显示勾选圈
})
const emit = defineEmits(['click', 'dblclick', 'longpress'])

const failed = ref(false) // 缩略图加载失败（文件丢了、损坏）
const loaded = ref(false)

const ratio = computed(() => (props.square ? 1 : aspectRatio(props.item)))
const hint = computed(() => hintShort(props.item.source_hint))
const video = computed(() => isVideo(props.item.ext))
const noThumb = computed(() => !props.item.thumb_url || failed.value)

// 长按（触屏）：500ms 不动算长按；期间手指移动或抬起则取消
let timer = null
let longFired = false
function down(e) {
  longFired = false
  if (e.pointerType === 'mouse') return
  timer = setTimeout(() => {
    longFired = true
    emit('longpress')
  }, 500)
}
function cancel() {
  clearTimeout(timer)
}
function onClick(e) {
  if (longFired) {
    longFired = false // 长按触发过，抬手那一下不再当作点击
    return
  }
  emit('click', e)
}
</script>

<template>
  <div
    class="cell"
    :class="{ selected, focused, 'multi-mode': multiMode }"
    role="option"
    :aria-selected="selected"
    :data-id="item.id"
    :title="item.orig_name || item.rel_path"
    @click="onClick"
    @dblclick="emit('dblclick', $event)"
    @pointerdown="down"
    @pointerup="cancel"
    @pointermove="cancel"
    @pointercancel="cancel"
    @contextmenu.prevent
  >
    <div class="frame" :style="{ aspectRatio: ratio }">
      <img
        v-if="!noThumb"
        :src="item.thumb_url"
        :class="{ loaded }"
        loading="lazy"
        decoding="async"
        draggable="false"
        alt=""
        @load="loaded = true"
        @error="failed = true"
      />
      <div v-else class="placeholder">
        <Film v-if="video" :size="28" />
        <!-- 破图图标只用于"本该有却加载失败/文件丢了"；GIF 没有缩略图是设计如此，用普通图片图标 -->
        <ImageOff v-else-if="item.missing || failed" :size="28" />
        <Image v-else :size="28" />
        <span class="ext">{{ extLabel(item.ext) }}</span>
        <span v-if="item.missing" class="gone">文件丢失</span>
      </div>

      <span v-if="hint" class="hint" :class="{ weak: item.source_hint && !item.source_hint.post_id }">
        {{ hint }}
      </span>
      <span class="check" aria-hidden="true"><Check :size="14" /></span>
      <span v-if="!noThumb && (video || item.ext === '.gif')" class="badge">{{ extLabel(item.ext) }}</span>
    </div>
    <div class="name">{{ item.orig_name || item.rel_path }}</div>
  </div>
</template>

<style scoped>
.cell {
  position: relative;
  min-width: 0;
  cursor: pointer;
  user-select: none;
  -webkit-user-select: none;
  touch-action: manipulation;
  border-radius: var(--radius);
}
.frame {
  position: relative;
  width: 100%;
  overflow: hidden;
  border-radius: var(--radius);
  background: var(--ph);
  outline: 2px solid transparent;
  outline-offset: -2px;
  transition: outline-color var(--dur);
}
img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0;
  transition: opacity var(--dur);
}
img.loaded {
  opacity: 1;
}
.placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  color: var(--fg-dim);
}
.ext {
  font-size: 12px;
  letter-spacing: 0.05em;
}
.gone {
  font-size: 12px;
  color: var(--danger);
}

/* 来源建议：收件箱里常驻，因为这是整理时最关键的信息 */
.hint {
  position: absolute;
  left: 4px;
  right: 4px;
  bottom: 4px;
  padding: 1px 6px;
  font-size: 12px;
  line-height: 1.5;
  border-radius: 4px;
  background: var(--accent-soft);
  color: var(--fg);
  backdrop-filter: blur(6px);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hint.weak {
  background: var(--warn-soft);
}
.badge {
  position: absolute;
  right: 4px;
  top: 4px;
  padding: 0 5px;
  font-size: 11px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
}

.check {
  position: absolute;
  left: 6px;
  top: 6px;
  display: none;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--accent);
  color: var(--accent-fg);
}
.multi-mode .check {
  display: flex;
  background: rgba(0, 0, 0, 0.4);
  border: 1.5px solid #fff;
  color: transparent;
}
.selected .check {
  display: flex;
  background: var(--accent);
  border-color: var(--accent);
  color: var(--accent-fg);
}
.selected .frame {
  outline-color: var(--accent);
}
.focused .frame {
  outline-color: var(--fg-dim);
  outline-style: dashed;
}
.selected.focused .frame {
  outline-color: var(--accent);
  outline-style: solid;
}

/* 文件名默认不显示；悬停或选中才出现。触屏没有悬停，只在选中时显示 */
.name {
  display: none;
  padding: 2px 2px 0;
  font-size: 12px;
  color: var(--fg-dim);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.selected .name {
  display: block;
}
@media (hover: hover) {
  .cell:hover .name {
    display: block;
  }
}
</style>
