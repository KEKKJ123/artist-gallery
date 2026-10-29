<script setup>
import { computed, onMounted, ref } from 'vue'
import OperationDialogs from './components/OperationDialogs.vue'
import ReviewScreen from './components/ReviewScreen.vue'
import FilterBar from './components/FilterBar.vue'
import NavPanel from './components/NavPanel.vue'
import PreviewOverlay from './components/PreviewOverlay.vue'
import ShortcutHelp from './components/ShortcutHelp.vue'
import SidePanel from './components/SidePanel.vue'
import ThumbGrid from './components/ThumbGrid.vue'
import ToastNotice from './components/ToastNotice.vue'
import TopBar from './components/TopBar.vue'
import { useGalleryKeys } from './composables/use-gallery-keys.js'
import { useGalleryNavigation } from './composables/use-gallery-navigation.js'
import { useInboxStore } from './stores/inbox.js'
import { usePrefsStore } from './stores/prefs.js'
import { useReviewStore } from './stores/review.js'

const inbox = useInboxStore()
const prefs = usePrefsStore()
const review = useReviewStore()
const recoveryModal = ref(false)
const operationModal = computed(() => !!review.archivePlan || review.bulk.ready || recoveryModal.value)
onMounted(() => { review.refreshOperations().catch(() => {}) })
function inspect() {
  const selected = inbox.items.filter((i) => inbox.selected.has(i.id)).map((i) => i.id)
  const ids = selected.length ? selected : [...inbox.ids]
  const first = 0
  inbox.closePreview()
  review.start(ids, Math.max(0, first))
}
async function closeReview() { review.close(); await inbox.load() }
async function undo() { if (await review.undo()) await inbox.load() }
async function archiveSelected(force = false) {
  if (await review.prepareArchive([...inbox.selected], force)) await inbox.load()
}
const grid = ref(null)
const helpOpen = ref(false)

const { narrow, drawerOpen, go, setFilter } = useGalleryNavigation({
  getView: () => inbox.view,
  setView: inbox.setView,
  navOpen: () => prefs.navOpen,
  closeNav: () => (prefs.navOpen = false),
})
useGalleryKeys({
  helpOpen,
  suspended: () => review.open || operationModal.value,
  drawerOpen: () => drawerOpen.value,
  closeNav: () => (prefs.navOpen = false),
  getCols: () => grid.value?.cols ?? 1,
  selectAll: inbox.selectAll,
  clearSelection: inbox.clearSelection,
  moveFocus: inbox.moveFocus,
  openPreview: inbox.openPreview,
})

const emptyTitle = computed(() => {
  if (!inbox.isInbox) return '还没有已归档的图片'
  if (inbox.hintFilter === 'hint') return '收件箱里没有带来源建议的图'
  if (inbox.hintFilter === 'nohint') return '收件箱里没有"没建议"的图了'
  return '收件箱是空的'
})
</script>

<template>
  <div class="app">
    <TopBar v-if="!review.open" @help="helpOpen = !helpOpen" />
    <div class="workbar">
      <button v-if="!review.open" :disabled="!inbox.items.length || review.busy" @click="inspect">{{ inbox.selected.size ? `检查所选 ${inbox.selected.size} 张` : '开始逐图检查' }}</button>
      <button v-if="!review.open && inbox.selected.size" :disabled="review.busy" @click="review.prepareBulk([...inbox.selected])">给所选图追加来源</button>
      <button v-if="!review.open && inbox.isInbox && inbox.selected.size" :disabled="review.busy" @click="archiveSelected(false)">归档所选…</button>
      <button v-if="!review.open && inbox.isInbox && inbox.selected.size" :disabled="review.busy" @click="archiveSelected(true)">强制归档所选…</button>
      <button :disabled="review.busy || !review.operations.can_undo" :title="review.operations.message" @click="undo">撤销最近一次</button>
    </div>
    <div v-if="review.error" class="error" role="alert">{{ review.error }} <button @click="review.error = ''">收起提示</button></div>
    <OperationDialogs @changed="inbox.load()" @modal="recoveryModal = $event" />
    <ReviewScreen v-if="review.open" :suspended="helpOpen || operationModal" @changed="inbox.load()" @close="closeReview" />
    <template v-else>

    <div v-if="inbox.error" class="error" role="alert">
      <span>{{ inbox.error }}</span>
      <button @click="inbox.load()">重试</button>
    </div>

    <div v-if="inbox.view.legacy" class="error" role="status">旧文件夹视图已移除，已回到收件箱；平台来源不再按目录分类。</div>
    <!-- 收件箱专属筛选 -->
    <FilterBar v-if="inbox.isInbox" @change="setFilter" />

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
          <p v-if="inbox.isInbox && inbox.hintFilter !== 'all'">
            试试
            <button class="linkish" @click="setFilter('all')">查看全部</button>。
          </p>
          <p v-else-if="inbox.isInbox">
            用命令行导入图片：<code>artist-gallery import &lt;图库&gt; &lt;文件夹&gt;</code
            >，再点右上角的刷新。
          </p>
          <p v-else>
            归档后的图片会显示在这里，也可继续补充来源。现在可以回到
            <button class="linkish" @click="go({ kind: 'inbox' })">收件箱</button>。
          </p>
        </div>
      </section>

      <SidePanel v-if="prefs.panelOpen" class="side" />
    </main>

    <!-- 手机：导航抽屉 -->
    <div v-if="drawerOpen" class="drawer-mask" @click="prefs.navOpen = false" />
    <NavPanel v-if="drawerOpen" class="drawer" @navigate="go" />

    <PreviewOverlay :suspended="helpOpen || operationModal" />
    </template>
    <ShortcutHelp :open="helpOpen" @close="helpOpen = false" />
    <ToastNotice :message="review.notice" :seq="review.noticeSeq" />
  </div>
</template>

<style scoped>
.app {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.workbar { display: flex; flex-wrap: wrap; gap: 6px; padding: 6px var(--pad); border-bottom: 1px solid var(--border); align-items: center; }
.workbar button { min-height: 36px; }
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
