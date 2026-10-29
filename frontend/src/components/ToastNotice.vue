<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'

// 只负责显示与计时，不读 store：内容由上层传入。seq 每次递增即重新显示，相同文字也会重新计时。
const props = defineProps({
  message: { type: String, default: '' },
  seq: { type: Number, default: 0 },
  duration: { type: Number, default: 3000 },
})
const visible = ref(false)
let timer = null

function stop() {
  clearTimeout(timer)
  timer = null
}
function restart() {
  stop()
  timer = setTimeout(() => { visible.value = false }, props.duration)
}
watch(() => props.seq, () => {
  visible.value = !!props.message
  if (visible.value) restart()
  else stop()
})
// 悬停期间暂停；移开后重新计满，不接着剩余时间。
function onLeave() {
  if (visible.value) restart()
}
onBeforeUnmount(stop)
</script>

<template>
  <!-- 外层常驻：aria-live 节点须先存在，读屏器才会播报；本身不接收指针事件 -->
  <div class="toast-region" role="status" aria-live="polite">
    <Transition name="toast">
      <div v-if="visible" class="toast" @mouseenter="stop" @mouseleave="onLeave">{{ message }}</div>
    </Transition>
  </div>
</template>

<style scoped>
.toast-region {
  position: fixed;
  top: 56px;
  right: 12px;
  z-index: 58;
  max-width: min(360px, calc(100vw - 24px));
  pointer-events: none;
}
.toast {
  pointer-events: auto;
  padding: 10px 14px;
  font-size: 13px;
  overflow-wrap: anywhere;
  background: var(--bg-elev);
  color: var(--fg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.18);
}
/* 窄屏工作栏按钮换行铺满，提示会压在按钮上；触屏也没有悬停。这两种情况整体放行点击，放弃悬停暂停。 */
@media (max-width: 520px), (hover: none) {
  .toast {
    pointer-events: none;
  }
}
.toast-enter-active,
.toast-leave-active {
  transition: opacity var(--dur), transform var(--dur);
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
@media (prefers-reduced-motion: reduce) {
  .toast-enter-active,
  .toast-leave-active {
    transition: none;
  }
}
</style>
