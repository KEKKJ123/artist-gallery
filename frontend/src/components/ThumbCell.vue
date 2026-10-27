<script setup>
import { Check, Film, Image, ImageOff } from '@lucide/vue'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { aspectRatio, extLabel, isVideo, imageCaption } from '../lib/format.js'
import { hintBadge } from '../lib/platforms.js'
import PlatformBadge from './PlatformBadge.vue'

const props = defineProps({
  item: { type: Object, required: true },
  selected: Boolean,
  focused: Boolean,
  square: Boolean,
  multiMode: Boolean, // 触屏多选模式：始终显示勾选圈
  platformNames: { type: Object, default: () => ({}) }, // 自定义平台的显示名
  badgeSize: { type: Number, default: 22 },
})
const emit = defineEmits(['click', 'dblclick', 'longpress'])

const failed = ref(false) // 缩略图加载失败（文件丢了、损坏）
const loaded = ref(false)

const ratio = computed(() => (props.square ? 1 : aspectRatio(props.item)))
const badge = computed(() => hintBadge(props.item.source_hints?.[0], props.platformNames))
const video = computed(() => isVideo(props.item.ext))
const noThumb = computed(() => !props.item.thumb_url || failed.value)
const displayUnassigned = computed(() => props.item.display_status === 'unassigned')
watch(() => props.item.thumb_url, () => {
  failed.value = false
  loaded.value = false
})

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
onBeforeUnmount(cancel)
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
    :title="item.orig_name || item.rel_path || `图片 #${item.id}`"
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
        <ImageOff v-else-if="displayUnassigned || item.missing || failed" :size="28" />
        <Image v-else :size="28" />
        <span class="ext">{{ extLabel(item.ext) }}</span>
        <span v-if="displayUnassigned" class="gone">展示文件待设置</span>
        <span v-else-if="item.missing" class="gone">文件丢失</span>
      </div>

      <!-- 来源建议：左下角站点标志（品牌色方块 + 首字母）。ID 不放在格子里，看右侧面板或大图预览 -->
      <span v-if="badge" class="hint-logo" :title="badge.tooltip">
        <PlatformBadge :platform="badge.platform" :uncertain="!badge.certain" :size="badgeSize" />
      </span>
      <span v-if="item.source_hints?.length > 1" class="badge">{{ item.source_hints.length }} 条建议</span>
      <span class="check" aria-hidden="true"><Check :size="14" /></span>
      <span v-if="!noThumb && (video || item.ext === '.gif')" class="badge">{{ extLabel(item.ext) }}</span>
    </div>
    <div class="name">{{ imageCaption(item) }}</div>
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

/* 来源建议：收件箱里常驻，因为这是整理时最关键的信息。
   只占左下角一小块，不再用横跨整个格子的半透明长条（它在浅色图上几乎看不清，还盖住画面） */
.hint-logo {
  position: absolute;
  left: 6px;
  bottom: 6px;
  display: inline-flex;
  line-height: 0;
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

/* 固定一行，选中／悬停不改变高度。 */
.name { display: block; height: 20px; line-height: 20px; padding: 0 2px; font-size: 12px; color: var(--fg-dim); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
