<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import NavPanel from './components/NavPanel.vue'
import PreviewOverlay from './components/PreviewOverlay.vue'
import ShortcutHelp from './components/ShortcutHelp.vue'
import SidePanel from './components/SidePanel.vue'
import ThumbGrid from './components/ThumbGrid.vue'
import TopBar from './components/TopBar.vue'
import { readInitialView, syncHistory } from './lib/history.js'
import { isHelpKey, keyBelongsToControl } from './lib/keys.js'
import { useInboxStore } from './stores/inbox.js'
import { usePrefsStore } from './stores/prefs.js'

const inbox = useInboxStore()
const prefs = usePrefsStore()
const grid = ref(null)
const helpOpen = ref(false)

// ---- 视图 ⇄ 地址栏 ----
// 用户点导航/面包屑 → go()：切换视图并往历史里记一条；点浏览器后退/前进 → 只切换视图。
const history = syncHistory(
  () => inbox.view,
  (view) => inbox.setView(view),
)

function go(view) {
  history.push(view)
  inbox.setView(view)
  // 手机上导航是盖在图上的抽屉：选完就收起，露出图
  if (window.matchMedia('(max-width: 720px)').matches) prefs.navOpen = false
}
const goFolder = (path) => go({ kind: 'folder', path })

function onKey(e) {
  // 焦点在文本框里时按键归它；滑块只拿走方向键（见 lib/keys.js）。
  // 以前把 INPUT 一律拦住，结果拖过一次"缩略图大小"滑块后，? 空格 Esc 等快捷键全部失效。
  if (keyBelongsToControl(e.target, e.key) || e.altKey) return
  // 帮助框打开时，背后的网格不响应按键（Esc 由帮助框自己处理）
  if (helpOpen.value) return
  // 预览和帮助各自在捕获阶段接管了按键；走到这里说明它们没开
  const mod = e.ctrlKey || e.metaKey

  if (mod && e.key.toLowerCase() === 'a') {
    e.preventDefault()
    inbox.selectAll()
  } else if (e.key === 'Escape') {
    // 手机上导航抽屉盖在图上：先关它
    if (drawerOpen.value) prefs.navOpen = false
    else inbox.clearSelection()
  } else if (e.key.startsWith('Arrow') && !mod) {
    e.preventDefault()
    inbox.moveFocus(e.key, grid.value?.cols ?? 1, { shift: e.shiftKey })
  } else if (e.key === ' ' && !mod) {
    e.preventDefault() // 空格默认会滚动页面
    inbox.openPreview()
  } else if (isHelpKey(e)) {
    // 中文输入法下 Shift+/ 可能是全角"？"，甚至被输入法吞成 "Process"；isHelpKey 都认
    e.preventDefault()
    helpOpen.value = true
  }
}

// 窄屏下导航以抽屉形式覆盖在内容上
const narrow = ref(false)
let mq
const onMq = () => (narrow.value = mq.matches)
const drawerOpen = computed(() => narrow.value && prefs.navOpen)

onMounted(async () => {
  mq = window.matchMedia('(max-width: 720px)')
  onMq()
  mq.addEventListener('change', onMq)
  window.addEventListener('keydown', onKey)

  const first = readInitialView()
  await inbox.setView(first, { force: true })
  history.align() // 地址栏里写得不规整时（如 //、末尾 /）换成干净写法，不新增历史
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
  mq?.removeEventListener('change', onMq)
  history.stop()
})

const emptyTitle = computed(() => (inbox.isInbox ? '收件箱是空的' : '这个文件夹里还没有图'))
</script>

<template>
  <div class="app">
    <TopBar @help="helpOpen = true" @navigate-folder="goFolder" />

    <div v-if="inbox.error" class="error" role="alert">
      <span>{{ inbox.error }}</span>
      <button @click="inbox.load()">重试</button>
    </div>

    <main
      class="main"
      :class="{ 'panel-open': prefs.panelOpen, 'nav-open': prefs.navOpen && !narrow }"
    >
      <NavPanel v-if="prefs.navOpen && !narrow" class="nav-col" @navigate="go" />

      <section class="content">
        <ThumbGrid v-if="inbox.items.length" ref="grid" />
        <div v-else-if="inbox.loading" class="state">加载中…</div>
        <div v-else-if="!inbox.error" class="state">
          <p>
            <strong>{{ emptyTitle }}</strong>
          </p>
          <p v-if="inbox.isInbox">
            用命令行导入图片：<code>artist-gallery import &lt;图库&gt; &lt;文件夹&gt;</code
            >，再点右上角的刷新。
          </p>
          <p v-else>
            可以从左侧选别的文件夹，或回到
            <button class="linkish" @click="go({ kind: 'inbox' })">收件箱</button>。
          </p>
        </div>
      </section>

      <SidePanel v-if="prefs.panelOpen" class="side" />
    </main>

    <!-- 手机：导航抽屉 -->
    <div v-if="drawerOpen" class="drawer-mask" @click="prefs.navOpen = false" />
    <NavPanel v-if="drawerOpen" class="drawer" @navigate="go" />

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
.main.nav-open {
  grid-template-columns: minmax(180px, 240px) 1fr;
}
.main.panel-open {
  grid-template-columns: 1fr minmax(240px, 300px);
}
.main.nav-open.panel-open {
  grid-template-columns: minmax(180px, 240px) 1fr minmax(240px, 300px);
}
.content {
  min-width: 0;
  min-height: 0;
}
.nav-col,
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
.linkish {
  padding: 0 2px;
  border: none;
  background: none;
  color: var(--accent);
  text-decoration: underline;
}

/* 窄屏（手机竖屏）：右侧面板变成底部抽屉；左侧导航变成从左边滑出的抽屉，盖在图上 */
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
.drawer-mask {
  position: fixed;
  inset: 0;
  z-index: 30;
  background: rgba(0, 0, 0, 0.45);
}
.drawer {
  position: fixed;
  top: 0;
  bottom: 0;
  left: 0;
  z-index: 31;
  width: min(300px, 82vw);
  box-shadow: 4px 0 16px rgba(0, 0, 0, 0.3);
}
</style>
