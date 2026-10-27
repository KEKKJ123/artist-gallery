<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import PreviewOverlay from './components/PreviewOverlay.vue'
import ShortcutHelp from './components/ShortcutHelp.vue'
import SidePanel from './components/SidePanel.vue'
import ThumbGrid from './components/ThumbGrid.vue'
import TopBar from './components/TopBar.vue'
import { useInboxStore } from './stores/inbox.js'
import { usePrefsStore } from './stores/prefs.js'

const inbox = useInboxStore()
const prefs = usePrefsStore()
const grid = ref(null)
const helpOpen = ref(false)

// 在输入框里打字时，不要把按键当快捷键
function typing(e) {
  const t = e.target
  return t instanceof HTMLElement && (t.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName))
}

function onKey(e) {
  if (typing(e) || e.altKey) return
  // 帮助框打开时，背后的网格不响应按键（Esc 由帮助框自己处理）
  if (helpOpen.value) return
  // 预览和帮助各自在捕获阶段接管了按键；走到这里说明它们没开
  const mod = e.ctrlKey || e.metaKey

  if (mod && e.key.toLowerCase() === 'a') {
    e.preventDefault()
    inbox.selectAll()
  } else if (e.key === 'Escape') {
    inbox.clearSelection()
  } else if (e.key.startsWith('Arrow') && !mod) {
    e.preventDefault()
    inbox.moveFocus(e.key, grid.value?.cols ?? 1, { shift: e.shiftKey })
  } else if (e.key === ' ' && !mod) {
    e.preventDefault() // 空格默认会滚动页面
    inbox.openPreview()
  } else if (e.key === '?') {
    helpOpen.value = true
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKey)
  inbox.load()
})
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="app">
    <TopBar @help="helpOpen = true" />

    <div v-if="inbox.error" class="error" role="alert">
      <span>{{ inbox.error }}</span>
      <button @click="inbox.load()">重试</button>
    </div>

    <main class="main" :class="{ 'panel-open': prefs.panelOpen }">
      <section class="content">
        <ThumbGrid v-if="inbox.items.length" ref="grid" />
        <div v-else-if="inbox.loading" class="state">加载中…</div>
        <div v-else-if="!inbox.error" class="state">
          <p><strong>收件箱是空的</strong></p>
          <p>
            用命令行导入图片：<code>artist-gallery import &lt;图库&gt; &lt;文件夹&gt;</code>，再点右上角的刷新。
          </p>
        </div>
      </section>
      <SidePanel v-if="prefs.panelOpen" class="side" />
    </main>

    <PreviewOverlay />
    <ShortcutHelp :open="helpOpen" @close="helpOpen = false" />
  </div>
</template>

<style scoped>
.app {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.error {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px var(--pad);
  background: var(--warn-soft);
  color: var(--fg);
  border-bottom: 1px solid var(--border);
}
.main {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 1fr;
}
.main.panel-open {
  grid-template-columns: 1fr minmax(240px, 300px);
}
.content {
  min-width: 0;
  min-height: 0;
}
.side {
  min-height: 0;
}
.state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 24px;
  text-align: center;
  color: var(--fg-dim);
}
.state p {
  margin: 0 0 6px;
}
code {
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--bg-sunken);
  font-size: 12px;
}

/* 窄屏（手机竖屏）：面板变成底部抽屉，不挤占网格宽度 */
@media (max-width: 720px) {
  .main.panel-open {
    grid-template-columns: 1fr;
    grid-template-rows: 1fr minmax(120px, 38%);
  }
  .side {
    border-left: none;
    border-top: 1px solid var(--border);
  }
}
</style>
