<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useReviewStore } from '../stores/review.js'
const emit = defineEmits(['changed', 'modal'])
const review = useReviewStore()
const confirmed = ref(false)
const recovery = ref(null)
const modalOpen = computed(() => !!review.archivePlan || review.bulk.ready || !!recovery.value)
let previousFocus
watch(modalOpen, async (opened) => {
  if (opened) {
    previousFocus = document.activeElement
    await nextTick()
    document.querySelector('.operation-dialog button:not(:disabled)')?.focus()
  } else previousFocus?.focus?.()
})
function onModalKey(e) {
  if (!modalOpen.value || document.querySelector('.dialog[aria-label="快捷键"]')) return
  const dialog = document.querySelector('.operation-dialog')
  if (!dialog) return
  if (e.key === 'Tab') {
    const focusable = [...dialog.querySelectorAll('button:not(:disabled), textarea:not(:disabled), input:not(:disabled), a[href]')]
    const first = focusable[0], last = focusable.at(-1)
    if (e.shiftKey && (document.activeElement === first || !dialog.contains(document.activeElement))) { e.preventDefault(); last?.focus() }
    else if (!e.shiftKey && (document.activeElement === last || !dialog.contains(document.activeElement))) { e.preventDefault(); first?.focus() }
  }
  if (e.key === 'Escape' && !review.busy) {
    e.preventDefault()
    if (review.archivePlan) review.archivePlan = null
    else if (review.bulk.ready) review.bulk.ready = false
    else recovery.value = null
  }
  // 不吞输入本身，只隔离全局快捷键，避免操作背后的选择、预览或检查队列。
  e.stopPropagation()
}
onMounted(() => window.addEventListener('keydown', onModalKey, true))
onBeforeUnmount(() => window.removeEventListener('keydown', onModalKey, true))
watch(() => [review.archivePlan, review.bulk.ready, recovery.value], () => {
  confirmed.value = false
  emit('modal', !!review.archivePlan || review.bulk.ready || !!recovery.value)
}, { immediate: true })
async function archive() { if (await review.archive(confirmed.value)) emit('changed') }
async function saveBulk() { if (confirmed.value && await review.saveBulk()) emit('changed') }
async function recover(action) {
  if (confirmed.value && await review.recover(recovery.value.id, action)) {
    recovery.value = null
    emit('changed')
  }
}
</script>

<template>
  <div v-if="review.operations.pending?.length" class="recovery-banner" role="alert">
    有未完成的文件操作，已暂停图库整理，不会自动重试。
    <button v-for="record in review.operations.pending" :key="record.id" @click="recovery = record">检查恢复 #{{ record.id }}</button>
  </div>
  <div v-if="review.archivePlan" class="dialog-mask">
    <section class="operation-dialog" role="dialog" aria-modal="true" aria-label="归档清单">
      <h2>{{ review.archivePlan.force ? '强制归档' : '正常归档' }} · {{ review.archivePlan.ids.length }} 张</h2>
      <p>只依据已保存资料；不会保存草稿、伪造人工确认或修改其他图片。</p>
      <ul v-if="review.archivePlan.errors.length" class="problems" role="alert">
        <li v-for="(error, n) in review.archivePlan.errors" :key="n">图片 #{{ error.image_id }}：{{ error.reason }}</li>
      </ul>
      <p v-if="review.archivePlan.errors.length">整批尚未执行。请返回网格另选正常／强制范围，不会自动分流。</p>
      <ul class="file-list">
        <li v-for="move in review.archivePlan.moves" :key="move.file_id">图片 #{{ move.image_id }}<br />{{ move.from }} → {{ move.to }}</li>
      </ul>
      <label v-if="!review.archivePlan.errors.length && (review.archivePlan.force || review.archivePlan.ids.length > 1)" class="confirm">
        <input v-model="confirmed" type="checkbox" />
        我确认对以上 {{ review.archivePlan.ids.length }} 张执行{{ review.archivePlan.force ? '强制' : '正常' }}归档；{{ review.archivePlan.force ? '只放宽来源门槛，不伪造来源确认' : '不包含未选图片' }}。
      </label>
      <footer>
        <button :disabled="review.busy" @click="review.archivePlan = null">返回／取消</button>
        <button class="primary" :disabled="review.busy || review.archivePlan.errors.length > 0 || ((review.archivePlan.force || review.archivePlan.ids.length > 1) && !confirmed)" @click="archive">执行归档</button>
      </footer>
    </section>
  </div>
  <div v-else-if="review.bulk.ready" class="dialog-mask">
    <section class="operation-dialog" role="dialog" aria-modal="true" aria-label="多选追加来源">
      <h2>多选追加来源 · {{ review.bulk.ids.length }} 张</h2>
      <p>范围固定为以下图片，不会跟着背后选择变化。只追加待核查来源，不自动确认或归档。</p>
      <p class="scope">图片编号：{{ review.bulk.ids.join('、') }}</p>
      <label for="bulk-links">一行一个链接；坏行保留，有效链接添加给每张图</label>
      <textarea id="bulk-links" v-model="review.bulk.text" :disabled="review.busy" rows="6" maxlength="64000" @input="confirmed = false; review.bulkChanged()" />
      <button :disabled="review.busy" @click="review.parseBulk()">检查全部链接</button>
      <ol v-if="review.bulk.lines?.length" class="parse-results">
        <li v-for="line in review.bulk.lines" :key="line.line" :class="{ problems: line.error }">第 {{ line.line }} 行：{{ line.error || `${line.platform}:${line.post_id}` }}</li>
      </ol>
      <label class="confirm"><input v-model="confirmed" type="checkbox" />我确认：全部有效链接 × 每张所选图片（{{ review.bulk.ids.length }} 张），不是按行分配。</label>
      <footer>
        <button :disabled="review.busy" @click="review.bulk.ready = false">取消（不修改来源）</button>
        <button class="primary" :disabled="!confirmed || review.busy || !review.bulk.text.trim()" @click="saveBulk">追加到每张所选图</button>
      </footer>
    </section>
  </div>
  <div v-else-if="recovery" class="dialog-mask">
    <section class="operation-dialog" role="dialog" aria-modal="true" aria-label="文件操作恢复">
      <h2>核对文件操作 #{{ recovery.id }}</h2>
      <p>{{ recovery.error || '上次操作未登记完成，不能推定文件尚未移动。' }}</p>
      <ul class="file-list"><li v-for="move in recovery.moves" :key="move.file_id">{{ move.from }} → {{ move.to }}<br />SHA-256：{{ move.sha256 }}</li></ul>
      <p>继续完成或恢复操作前都会重新校验；目标占用或副本所有权不明时保留文件并报错，不强删。</p>
      <label class="confirm"><input v-model="confirmed" type="checkbox" />我已核对以上范围，明确选择下方一种恢复动作。</label>
      <footer>
        <button :disabled="review.busy" @click="recovery = null">稍后核对</button>
        <button :disabled="review.busy || !confirmed" @click="recover('rollback')">恢复操作前</button>
        <button class="primary" :disabled="review.busy || !confirmed || recovery.recovery === 'rollback'" @click="recover('finish')">继续完成</button>
      </footer>
    </section>
  </div>
</template>

<style scoped>
.dialog-mask { position: fixed; inset: 0; z-index: 55; background: rgba(0,0,0,.45); padding: 16px; display: flex; align-items: center; justify-content: center; }
.operation-dialog { width: min(650px, 100%); max-height: 90dvh; overflow: auto; background: var(--bg-elev); color: var(--fg); padding: 18px; border: 1px solid var(--border); border-radius: var(--radius); box-shadow: 0 8px 30px rgba(0,0,0,.2); }
h2 { margin: 0 0 10px; font-size: 18px; }
p { font-size: 13px; }
.file-list { overflow-wrap: anywhere; font-size: 12px; background: var(--bg-sunken); padding: 12px 12px 12px 30px; max-height: 35dvh; overflow: auto; }
.file-list li { margin-bottom: 8px; }
.problems { color: var(--danger); }
.confirm { display: flex; align-items: flex-start; gap: 8px; margin-top: 12px; font-size: 13px; }
.confirm input { flex: none; margin-top: 4px; }
textarea { width: 100%; margin-top: 8px; color: var(--fg); font: inherit; padding: 8px; background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius); }
footer { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; margin-top: 16px; }
button { min-height: 44px; }
.scope { overflow-wrap: anywhere; max-height: 15dvh; overflow: auto; }
.recovery-banner { padding: 8px var(--pad); background: var(--warn-soft); }
</style>
