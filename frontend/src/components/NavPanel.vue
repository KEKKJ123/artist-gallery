<script setup>
import { ChevronDown, ChevronRight, Folder, FolderOpen, Images, Inbox } from '@lucide/vue'
import { computed, ref } from 'vue'
import { cleanPath, sameView } from '../lib/location.js'
import { useInboxStore } from '../stores/inbox.js'

const emit = defineEmits(['navigate'])
const inbox = useInboxStore()

// 展开状态：记住用户手动展开/收起的文件夹。当前所在文件夹的所有祖先自动视为展开。
const toggled = ref(new Set())
const current = computed(() => (inbox.view.kind === 'folder' ? cleanPath(inbox.view.path) : null))

function ancestorsOfCurrent() {
  if (current.value === null || current.value === '') return new Set()
  const segs = current.value.split('/')
  return new Set(segs.slice(0, -1).map((_, i) => segs.slice(0, i + 1).join('/')))
}
function isOpen(f) {
  if (ancestorsOfCurrent().has(f.path)) return true
  return toggled.value.has(f.path)
}
function toggle(f) {
  const next = new Set(toggled.value)
  if (isOpen(f) && !ancestorsOfCurrent().has(f.path)) next.delete(f.path)
  else next.add(f.path)
  toggled.value = next
}

// 只显示"所有祖先都展开了"的行
const visible = computed(() => {
  const open = new Map(inbox.nav.folders.map((f) => [f.path, isOpen(f)]))
  return inbox.nav.folders.filter((f) => {
    const segs = f.path.split('/')
    for (let i = 1; i < segs.length; i++) if (!open.get(segs.slice(0, i).join('/'))) return false
    return true
  })
})

const isCurrentInbox = computed(() => inbox.view.kind === 'inbox')
const isCurrentAll = computed(() => current.value === '')
const go = (view) => emit('navigate', view)
const here = (path) => sameView(inbox.view, { kind: 'folder', path })
</script>

<template>
  <nav class="nav" aria-label="文件夹导航">
    <button class="row top" :class="{ active: isCurrentInbox }" @click="go({ kind: 'inbox' })">
      <Inbox :size="16" />
      <span class="label">收件箱</span>
      <span class="count" :class="{ attention: inbox.nav.inbox > 0 }">{{ inbox.nav.inbox }}</span>
    </button>

    <div class="section-title">已归档</div>
    <button class="row top" :class="{ active: isCurrentAll }" @click="go({ kind: 'folder', path: '' })">
      <Images :size="16" />
      <span class="label">全部</span>
      <span class="count">{{ inbox.nav.archived }}</span>
    </button>

    <div v-for="f in visible" :key="f.path" class="folder" :style="{ '--depth': f.depth }">
      <button
        v-if="f.has_children"
        class="twisty"
        :aria-label="isOpen(f) ? `收起 ${f.name}` : `展开 ${f.name}`"
        :aria-expanded="isOpen(f)"
        @click.stop="toggle(f)"
      >
        <component :is="isOpen(f) ? ChevronDown : ChevronRight" :size="14" />
      </button>
      <span v-else class="twisty spacer" />
      <button class="row" :class="{ active: here(f.path) }" :title="f.path" @click="go({ kind: 'folder', path: f.path })">
        <component :is="here(f.path) ? FolderOpen : Folder" :size="16" />
        <span class="label">{{ f.name }}</span>
        <span class="count">{{ f.count }}</span>
      </button>
    </div>

    <p v-if="!inbox.nav.folders.length" class="hint">
      还没有归档的图。整理收件箱里的图之后，这里会出现按来源（pixiv、x……）分好的文件夹。
    </p>
  </nav>
</template>

<style scoped>
.nav {
  display: flex;
  flex-direction: column;
  gap: 1px;
  height: 100%;
  padding: 8px;
  overflow-y: auto;
  background: var(--bg-elev);
  border-right: 1px solid var(--border);
}
.section-title {
  flex: none;
  margin: 12px 8px 4px;
  font-size: 12px;
  color: var(--fg-dim);
}
.row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
  padding: 5px 8px;
  text-align: left;
  border: none;
  background: transparent;
  border-radius: var(--radius);
}
.row:hover {
  background: var(--bg-sunken);
}
.row.active {
  background: var(--accent-soft);
  color: var(--fg);
  font-weight: 600;
}
/* 顶层几行（收件箱、全部）直接放在纵向排列的 .nav 里。.row 上的 flex: 1 是给文件夹行用的
   （在横向的 .folder 里让按钮占满剩余宽度），放到纵向容器里就会变成"纵向平分整个高度"，
   把它们拉得老高、把文件夹列表挤到底部。所以这里必须取消。 */
.row.top {
  flex: none;
  width: 100%;
}
.label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.count {
  font-size: 12px;
  color: var(--fg-dim);
  font-variant-numeric: tabular-nums;
}
.count.attention {
  padding: 0 6px;
  border-radius: 8px;
  background: var(--warn-soft);
  color: var(--fg);
}
.folder {
  flex: none;
  display: flex;
  align-items: center;
  /* 每深一层缩进 14px；三角的位置固定占 20px，保证同级文字对齐 */
  padding-left: calc(var(--depth) * 14px);
}
.twisty {
  flex: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  min-width: 20px;
  height: 24px;
  min-height: 24px;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--fg-dim);
}
.twisty.spacer {
  pointer-events: none;
}
.hint {
  margin: 12px 8px;
  font-size: 12px;
  color: var(--fg-dim);
}
@media (pointer: coarse) {
  .row {
    min-height: var(--touch);
  }
  .twisty {
    width: 32px;
    min-width: 32px;
    min-height: var(--touch);
  }
}
</style>
