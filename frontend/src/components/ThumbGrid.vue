<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useInboxStore } from '../stores/inbox.js'
import { usePrefsStore } from '../stores/prefs.js'
import ThumbCell from './ThumbCell.vue'

const inbox = useInboxStore()
const prefs = usePrefsStore()

const root = ref(null)
const cols = ref(1)
const multiMode = ref(false) // 触屏多选模式：长按进入，选空了自动退出

// 列宽下限 = 用户设的大小，但不超过屏幕宽度的 44%：
// 手机上（390px）始终至少两列，而不是一张图占满一屏。
const gridStyle = computed(() => ({
  gridTemplateColumns: `repeat(auto-fill, minmax(min(${prefs.thumbSize}px, 44vw), 1fr))`,
}))

// 上下方向键要知道一行有几列：直接读浏览器算出来的实际列数
function measureCols() {
  if (!root.value) return
  const tpl = getComputedStyle(root.value).gridTemplateColumns
  cols.value = Math.max(1, tpl.split(' ').filter(Boolean).length)
}
let ro
onMounted(() => {
  measureCols()
  ro = new ResizeObserver(measureCols)
  ro.observe(root.value)
})
onBeforeUnmount(() => ro?.disconnect())
watch(() => prefs.thumbSize, () => nextTick(measureCols))

// 选空了就退出多选模式
watch(
  () => inbox.selected.size,
  (n) => {
    if (n === 0) multiMode.value = false
  },
)

// 切换到另一个文件夹 / 收件箱：滚回顶部（否则会停在上一个文件夹的滚动位置，看起来像"少了图"）
const scroller = ref(null)
watch(
  () => JSON.stringify(inbox.view),
  () => scroller.value?.scrollTo({ top: 0 }),
)

function onClick(item, e) {
  if (multiMode.value) {
    lastMultiAt = performance.now()
    inbox.tapToggle(item.id)
  } else {
    inbox.click(item.id, { ctrl: e.ctrlKey || e.metaKey, shift: e.shiftKey })
  }
}
function onLongPress(item) {
  lastMultiAt = performance.now()
  multiMode.value = true
  if (!inbox.selected.has(item.id)) inbox.tapToggle(item.id)
}

// 双击 → 打开大图。但在"多选"期间，连续快速的点击是在勾选，不是想打开大图。
// 浏览器会把"快速点两下同一张"合成一个 dblclick，所以要在这里拦住。
//
// 只判断"现在是不是多选模式"不够：多选里点掉最后一张，选择变空 → 自动退出多选模式 →
// 紧接着的第二下点击落在"非多选"状态，随后合成的 dblclick 就会误开大图。
// 所以改为记录"最近一次多选操作的时间"：这之后的一小段时间内，dblclick 一律不算。
const MULTI_GRACE_MS = 700
let lastMultiAt = -Infinity
function onCellDblClick(item) {
  if (multiMode.value || performance.now() - lastMultiAt < MULTI_GRACE_MS) return
  inbox.openPreview(item.id)
}

// Ctrl+滚轮调缩略图大小（浏览器默认是整页缩放，这里接管）
function onWheel(e) {
  if (!e.ctrlKey) return
  e.preventDefault()
  prefs.nudgeThumbSize(e.deltaY < 0 ? 20 : -20)
}

// 滚到焦点那张（键盘移动后保证看得见）
watch(
  () => inbox.focus,
  async (id) => {
    if (id === null) return
    await nextTick()
    root.value?.querySelector(`[data-id="${id}"]`)?.scrollIntoView({ block: 'nearest' })
  },
)

// 翻到底自动加载下一页
const sentinel = ref(null)
let io
onMounted(() => {
  io = new IntersectionObserver(
    (entries) => {
      if (entries.some((e) => e.isIntersecting)) inbox.loadMore()
    },
    { rootMargin: '600px' },
  )
  if (sentinel.value) io.observe(sentinel.value)
})
onBeforeUnmount(() => io?.disconnect())

defineExpose({ cols, multiMode })
</script>

<template>
  <div ref="scroller" class="scroller" @wheel="onWheel" @click.self="inbox.clearSelection()">
    <div
      ref="root"
      class="grid"
      role="listbox"
      aria-multiselectable="true"
      aria-label="收件箱图片"
      :style="gridStyle"
    >
      <ThumbCell
        v-for="item in inbox.items"
        :key="item.id"
        :item="item"
        :selected="inbox.selected.has(item.id)"
        :focused="inbox.focus === item.id"
        :square="prefs.square"
        :multi-mode="multiMode"
        @click="onClick(item, $event)"
        @dblclick="onCellDblClick(item)"
        @longpress="onLongPress(item)"
      />
    </div>
    <div ref="sentinel" class="sentinel">
      <span v-if="inbox.loading && inbox.items.length">加载中…</span>
      <span v-else-if="inbox.hasMore">向下滚动加载更多</span>
    </div>
  </div>
</template>

<style scoped>
.scroller {
  height: 100%;
  overflow-y: auto;
  padding: var(--pad);
}
.grid {
  display: grid;
  gap: var(--gap);
  align-items: start;
}
.sentinel {
  min-height: 40px;
  padding: 12px;
  text-align: center;
  color: var(--fg-dim);
  font-size: 12px;
}
</style>
