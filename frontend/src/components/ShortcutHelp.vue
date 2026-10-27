<script setup>
import { X } from '@lucide/vue'
import { onBeforeUnmount, onMounted } from 'vue'

const props = defineProps({ open: Boolean })
const emit = defineEmits(['close'])

// [按键, 说明, 是否已可用]。后续里程碑才有的先列出来但标灰，让人知道会有。
const groups = [
  {
    title: '选择',
    rows: [
      ['点击', '只选这一张', true],
      ['Ctrl + 点击', '增减一张', true],
      ['Shift + 点击', '选中起点到这里的一段', true],
      ['Ctrl + A', '全选', true],
      ['Esc', '取消选择', true],
      ['← → ↑ ↓', '移动焦点（同时选中）', true],
      ['Shift + 方向键', '扩展选择范围', true],
    ],
  },
  {
    title: '查看',
    rows: [
      ['空格 / 双击', '打开大图预览；预览中再按空格关闭', true],
      ['Ctrl + 滚轮', '调整缩略图大小', true],
      ['?', '显示本帮助', true],
    ],
  },
  {
    title: '大图预览',
    rows: [
      ['← →', '切换上一张 / 下一张（放大后改为平移）', true],
      ['滚轮', '以光标位置为中心缩放', true],
      ['拖动', '放大后平移', true],
      ['双击', '在"适应窗口"和 100% 之间切换', true],
      ['+ -', '放大 / 缩小一档', true],
      ['0', '回到适应窗口', true],
      ['Esc', '放大时先回到适应窗口；再按一次关闭', true],
      ['双指', '手机上捏合缩放、单指拖动平移', true],
    ],
  },
  {
    title: '整理（后续版本）',
    rows: [
      ['Ctrl + V', '粘贴链接，识别平台和作品', false],
      ['T', '聚焦 tag 输入框', false],
      ['Enter', '确认并跳到下一组', false],
    ],
  },
]

function onKey(e) {
  // 监听器在挂载时就注册了，所以必须自己判断"帮助框是否打开"。
  // 没打开时一定要放行：否则 Esc 会在这里被吞掉，网格永远收不到"取消选择"。
  if (!props.open) return
  if (e.key === 'Escape') {
    e.preventDefault()
    e.stopPropagation()
    emit('close')
  }
}
onMounted(() => window.addEventListener('keydown', onKey, true))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey, true))
</script>

<template>
  <div v-if="open" class="mask" @click.self="emit('close')">
    <div class="dialog" role="dialog" aria-label="快捷键">
      <header>
        <h2>快捷键</h2>
        <button class="icon" aria-label="关闭" @click="emit('close')"><X :size="16" /></button>
      </header>
      <section v-for="g in groups" :key="g.title">
        <h3>{{ g.title }}</h3>
        <ul>
          <li v-for="[key, desc, ready] in g.rows" :key="key" :class="{ later: !ready }">
            <span class="keys"><kbd v-for="k in key.split(' + ')" :key="k">{{ k }}</kbd></span>
            <span>{{ desc }}</span>
          </li>
        </ul>
      </section>
    </div>
  </div>
</template>

<style scoped>
.mask {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: rgba(0, 0, 0, 0.45);
}
.dialog {
  width: min(520px, 100%);
  max-height: 100%;
  overflow-y: auto;
  padding: 16px 20px;
  background: var(--bg-elev);
  border: 1px solid var(--border);
  border-radius: calc(var(--radius) + 2px);
}
header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
h2 {
  margin: 0;
  font-size: 16px;
}
h3 {
  margin: 14px 0 6px;
  font-size: 12px;
  color: var(--fg-dim);
  font-weight: 600;
}
ul {
  margin: 0;
  padding: 0;
  list-style: none;
}
li {
  display: grid;
  grid-template-columns: 150px 1fr;
  gap: 8px;
  padding: 3px 0;
  font-size: 13px;
}
.keys {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.later {
  opacity: 0.5;
}
</style>
