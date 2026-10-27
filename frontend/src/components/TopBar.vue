<script setup>
import {
  CircleHelp,
  Folder,
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
import Breadcrumb from './Breadcrumb.vue'

defineEmits(['help', 'navigate-folder'])
const prefs = usePrefsStore()
const inbox = useInboxStore()

const themeIcon = computed(() => ({ system: Monitor, light: Sun, dark: Moon })[prefs.theme])
const themeLabel = computed(
  () => ({ system: '主题：跟随系统', light: '主题：浅色', dark: '主题：深色' })[prefs.theme],
)
const folderPath = computed(() => (inbox.view.kind === 'folder' ? inbox.view.path : ''))
</script>

<template>
  <header class="top">
    <button
      class="icon"
      :aria-pressed="prefs.navOpen"
      title="显示/隐藏文件夹列表"
      aria-label="显示或隐藏文件夹列表"
      @click="prefs.navOpen = !prefs.navOpen"
    >
      <PanelLeft :size="16" />
    </button>

    <div v-if="inbox.isInbox" class="brand"><Inbox :size="18" /> 收件箱</div>
    <div v-else class="brand folder">
      <Folder :size="18" class="ico" />
      <Breadcrumb :path="folderPath" @navigate="(p) => $emit('navigate-folder', p)" />
    </div>
    <span class="count">
      <template v-if="inbox.loading && !inbox.items.length">加载中…</template>
      <template v-else>共 {{ inbox.total }} 张</template>
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
    <button class="icon" title="快捷键（?）" aria-label="快捷键" @click="$emit('help')">
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
.brand.folder {
  min-width: 0;
  flex: 0 1 auto;
  font-weight: 400;
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
  }
  .size {
    display: none;
  }
  /* 面包屑可能很长：手机上只显示最后一级，其余可以点导航栏里的文件夹到达 */
  .brand.folder :deep(li:not(:last-child)) {
    display: none;
  }
}
</style>
