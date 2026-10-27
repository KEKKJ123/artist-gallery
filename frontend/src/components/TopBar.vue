<script setup>
import {
  CircleHelp,
  Images,
  Inbox,
  LayoutGrid,
  Monitor,
  Moon,
  PanelLeft,
  PanelRight,
  RefreshCw,
  Square,
  Sun,
} from '@lucide/vue'
import { computed } from 'vue'
import { useInboxStore } from '../stores/inbox.js'
import { SIZE_MAX, SIZE_MIN, usePrefsStore } from '../stores/prefs.js'

defineEmits(['help'])
const prefs = usePrefsStore()
const inbox = useInboxStore()

const themeIcon = computed(() => ({ system: Monitor, light: Sun, dark: Moon })[prefs.theme])
const themeLabel = computed(
  () => ({ system: '主题：跟随系统', light: '主题：浅色', dark: '主题：深色' })[prefs.theme],
)
</script>

<template>
  <header class="top">
    <button
      class="icon"
      :aria-pressed="prefs.navOpen"
      title="显示/隐藏图库导航"
      aria-label="显示或隐藏图库导航"
      @click="prefs.navOpen = !prefs.navOpen"
    >
      <PanelLeft :size="16" />
    </button>

    <div v-if="inbox.isInbox" class="brand"><Inbox :size="18" /> 收件箱</div>
    <div v-else class="brand">
      <Images :size="18" class="ico" />
      已归档
    </div>
    <span class="count" :title="`共 ${inbox.total} 张`">
      <template v-if="inbox.loading && !inbox.items.length">加载中…</template>
      <template v-else>
        <span class="long">共 {{ inbox.total }} 张</span>
        <span class="short">{{ inbox.total }}</span>
      </template>
    </span>

    <div class="spacer" />

    <label class="size" title="缩略图大小（也可 Ctrl+滚轮）">
      <span class="sr">缩略图大小</span>
      <input
        type="range"
        :min="SIZE_MIN"
        :max="SIZE_MAX"
        step="10"
        :value="prefs.thumbSize"
        @input="prefs.setThumbSize($event.target.value)"
      />
    </label>

    <button
      class="icon"
      :aria-pressed="prefs.square"
      :title="prefs.square ? '当前：方形裁切（点击切换为原比例）' : '当前：原比例（点击切换为方形）'"
      @click="prefs.square = !prefs.square"
    >
      <component :is="prefs.square ? Square : LayoutGrid" :size="16" />
    </button>
    <button class="icon" :title="themeLabel" :aria-label="themeLabel" @click="prefs.cycleTheme()">
      <component :is="themeIcon" :size="16" />
    </button>
    <button class="icon" title="刷新" aria-label="刷新" :disabled="inbox.loading" @click="inbox.load()">
      <RefreshCw :size="16" />
    </button>
    <button class="icon" title="快捷键帮助（/ 或 Shift+/，再按一次关闭）" aria-label="快捷键" @click="$emit('help')">
      <CircleHelp :size="16" />
    </button>
    <button
      class="icon"
      :aria-pressed="prefs.panelOpen"
      title="显示/隐藏右侧面板"
      aria-label="显示或隐藏右侧面板"
      @click="prefs.panelOpen = !prefs.panelOpen"
    >
      <PanelRight :size="16" />
    </button>
  </header>
</template>

<style scoped>
.top {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px var(--pad);
  background: var(--bg-elev);
  border-bottom: 1px solid var(--border);
}
.brand {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  white-space: nowrap;
}
.count .short {
  display: none;
}
.brand .ico {
  flex: none;
  color: var(--fg-dim);
}
.count {
  color: var(--fg-dim);
  font-size: 13px;
  white-space: nowrap;
}
.spacer {
  flex: 1;
}
.size input {
  width: clamp(70px, 14vw, 140px);
  accent-color: var(--accent);
}
.sr {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}
button[aria-pressed='true'] {
  background: var(--accent-soft);
  border-color: var(--accent);
}
button:disabled {
  opacity: 0.5;
  cursor: default;
}
.top button {
  flex: none;
}

/* 手机宽度：顶栏放不下所有东西。缩略图大小在手机上由屏幕宽度决定（见 ThumbGrid），
   滑块没有用处，藏起来；间距收紧，保证右侧按钮不被裁掉。 */
@media (max-width: 520px) {
  .top {
    gap: 4px;
    padding-inline: 8px;
    /* 兜底：无论里面放什么，顶栏自己不能比屏幕宽。宽了会把整个页面撑宽，
       手机浏览器随后会缩放或出现横向滚动，触摸坐标和页面坐标也会错位 */
    min-width: 0;
    overflow: hidden;
  }
  .size {
    display: none;
  }
  /* "共 N 张"在手机上缩成一个数字（完整文字放在 title 里），腾出约 35px */
  .count .long {
    display: none;
  }
  .count .short {
    display: inline;
  }
  .brand {
    flex: 0 1 auto;
    min-width: 0;
  }
}
</style>
