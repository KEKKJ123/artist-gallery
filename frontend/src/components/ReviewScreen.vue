<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { usePreviewViewport } from '../composables/use-preview-viewport.js'
import { isVideo } from '../lib/format.js'
import { formatBytes } from '../lib/review-drafts.js'
import { useReviewStore } from '../stores/review.js'
import SourceEditor from './SourceEditor.vue'

const props = defineProps({ suspended: Boolean })
const emit = defineEmits(['changed', 'close'])
const review = useReviewStore()
const video = computed(() => isVideo(review.item?.ext ?? ''))
const unavailable = computed(() => !review.item?.file_url || review.item?.display_status !== 'ok')
const imageError = ref(false)
watch(() => `${review.item?.id}:${review.item?.file_id}`, () => { imageError.value = false })
const {
  stage, canZoom, pct, imgStyle, zoomIn, zoomOut, resetView, onImgLoad,
  onWheel, onPointerDown, onPointerMove, onPointerUp, onDblClick,
} = usePreviewViewport({
  mediaId: () => `${review.item?.id}:${review.item?.file_id}:${review.item?.file_url}`,
  video, zoomDisabled: () => unavailable.value, onClose: () => {},
})
async function save(next) { if (await review.save(next)) emit('changed') }
async function archive(force = false) {
  if (await review.prepareArchive([review.item.id], force)) emit('changed')
}
function onKey(e) {
  if (props.suspended || !review.open) return
  // 帮助开关键交给全局；其他键不再穿透至背后的网格。输入框 Enter 不触发保存。
  if (e.key === 'Escape' && !review.busy) {
    e.preventDefault()
    emit('close')
  }
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <section class="review-screen" aria-label="逐图检查">
    <header class="review-header">
      <button :disabled="review.busy" @click="emit('close')">返回网格／多选</button>
      <strong>逐图检查</strong>
      <span>{{ review.index + 1 }} / {{ review.queue.length }}</span>
      <span class="queue-note">当前检查队列，不自动扩选</span>
    </header>
    <div v-if="review.loading" class="review-state">读取图片与草稿…</div>
    <div v-else-if="!review.item" class="review-state">
      无法读取当前图片。<button @click="review.show(review.index)">重新读取</button>
    </div>
    <div v-else class="review-body">
      <section class="picture" aria-label="当前图片">
        <div class="picture-tools">
          <span :title="review.item.orig_name">{{ review.item.orig_name || `图片 #${review.item.id}` }}</span>
          <template v-if="canZoom">
            <button aria-label="检查图缩小" @click="zoomOut">−</button>
            <button @click="resetView">{{ pct }}% · 适应</button>
            <button aria-label="检查图放大" @click="zoomIn">＋</button>
          </template>
        </div>
        <div ref="stage" class="review-stage" @wheel="onWheel" @pointerdown="onPointerDown"
          @pointermove="onPointerMove" @pointerup="onPointerUp" @pointercancel="onPointerUp" @dblclick="onDblClick">
          <p v-if="unavailable">{{ review.item.display_message || '展示文件缺失，未自动选择其他版本。' }}</p>
          <video v-else-if="video" :key="review.item.id" :src="review.item.file_url" controls playsinline />
          <img v-else :key="`${review.item.id}:${review.item.file_id}`" :src="review.item.file_url" :style="imgStyle"
            alt="待核查图片" draggable="false" @load="onImgLoad($event); imageError = false" @error="imageError = true" />
          <p v-if="imageError && !unavailable" class="media-error">图片读取失败；请核对文件或网络。</p>
        </div>
        <div class="file-info">
          <span>{{ review.item.width ? `${review.item.width} × ${review.item.height}` : '尺寸未知' }}</span>
          <span>{{ review.size != null ? formatBytes(review.size) : (review.sizeError || '文件大小读取中…') }}</span>
          <span>状态：{{ review.item.state === 'archived' ? '已归档' : '收件箱' }} · 大小不代表原图证明</span>
        </div>
      </section>
      <section class="editor" aria-label="来源资料">
        <p class="draft-status" role="status">{{ review.active?.message }}</p>
        <div v-if="review.stale" class="warning" role="alert">
          正式资料已改变，旧草稿不能覆盖。可先复制需要保留的输入，再放弃草稿并重新核对。
        </div>
        <fieldset :disabled="review.busy || !review.draft || review.active?.failed">
          <SourceEditor />
          <label class="links-label" for="review-links">追加来源链接（一行一个）</label>
          <textarea id="review-links" v-model="review.draft.text" rows="4" maxlength="64000"
            placeholder="粘贴具体发布链接，只追加；清空不会删除已有来源。" @input="review.changed()" />
          <button @click="review.parse()">检查链接</button>
          <ol v-if="review.lines.length" class="parsed-lines">
            <li v-for="line in review.lines" :key="line.line" :class="{ invalid: line.error }">
              第 {{ line.line }} 行：{{ line.error || `${line.platform}:${line.post_id}${line.page == null ? ' · 页码未知' : ` · p${line.page}`}` }}
            </li>
          </ol>
          <p class="muted">新链接先作为待核查来源保存；不会自动猜画师、发布时间或 p0。</p>
        </fieldset>
        <div class="save-actions">
          <button class="primary" :disabled="review.busy || review.stale || review.active?.failed" @click="save(false)">保存资料</button>
          <button :disabled="review.busy || review.stale || review.active?.failed" @click="save(true)">保存并下一张</button>
          <button :disabled="review.busy" @click="review.discard()">放弃草稿</button>
          <button v-if="review.active?.failed" :disabled="review.busy" @click="review.reloadDraft()">读取最新草稿（放弃本页输入）</button>
        </div>
        <p class="muted">保存不会归档。上一张／跳过只切图，未保存内容作为草稿保留。</p>
        <div class="queue-actions">
          <button :disabled="review.busy || review.index === 0" @click="review.step(-1)">上一张</button>
          <button :disabled="review.busy || review.index + 1 >= review.queue.length" @click="review.step(1)">跳过／下一张</button>
        </div>
        <div v-if="review.item.state === 'inbox'" class="archive-actions">
          <button :disabled="review.busy" @click="archive(false)">正常归档</button>
          <button :disabled="review.busy" @click="archive(true)">强制归档…</button>
          <p class="muted">只依据已保存资料；草稿中的“已确认”不算归档条件。</p>
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.review-screen { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.review-header, .picture-tools { display: flex; align-items: center; gap: 8px; padding: 8px var(--pad); border-bottom: 1px solid var(--border); }
.review-header { flex-wrap: wrap; }
.queue-note, .muted, .file-info, .draft-status { color: var(--fg-dim); font-size: 12px; }
.review-body { flex: 1; min-height: 0; display: grid; grid-template-columns: minmax(0, 1fr) minmax(320px, 420px); }
.picture { min-width: 0; min-height: 0; display: flex; flex-direction: column; }
.picture-tools > span { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.picture-tools button { flex: none; }
.review-stage { position: relative; flex: 1; min-height: 100px; display: flex; align-items: center; justify-content: center; overflow: hidden; touch-action: none; background: var(--bg-sunken); }
.review-stage img { max-width: 100%; max-height: 100%; object-fit: contain; flex: none; user-select: none; }
.review-stage video { max-width: 100%; max-height: 100%; }
.file-info { display: flex; flex-wrap: wrap; gap: 4px 12px; padding: 8px var(--pad); }
.editor { min-width: 0; overflow: auto; padding: var(--pad); border-left: 1px solid var(--border); background: var(--bg-elev); }
fieldset { border: 0; padding: 0; margin: 0; min-width: 0; }
textarea { width: 100%; resize: vertical; padding: 8px; font: inherit; color: var(--fg); background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius); }
.links-label { display: block; margin-top: 16px; font-weight: 600; }
.save-actions, .queue-actions, .archive-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.archive-actions { padding-top: 12px; border-top: 1px solid var(--border); }
.archive-actions p { width: 100%; }
.warning { background: var(--warn-soft); padding: 8px; margin-bottom: 10px; }
.invalid { color: var(--danger); }
.parsed-lines { padding-left: 20px; overflow-wrap: anywhere; font-size: 12px; }
.review-state { padding: 40px; text-align: center; }
.media-error { position: absolute; bottom: 10px; background: var(--warn-soft); padding: 8px; }
button { min-height: 40px; }
@media (max-width: 720px) {
  .review-body { display: flex; flex-direction: column; overflow: auto; }
  .picture { flex: none; height: min(52dvh, 460px); }
  .editor { overflow: visible; border-left: 0; border-top: 1px solid var(--border); }
  .queue-note { display: none; }
  button { min-height: 44px; }
}
</style>
