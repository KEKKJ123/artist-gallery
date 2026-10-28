import { defineStore } from 'pinia'
import { computed, reactive, ref } from 'vue'
import {
  executeArchive, fetchDraft, fetchFileSize, fetchImage, fetchMetadata,
  parseLinks, planArchive, putDraft, recoverOperation, saveReview, undoOperation,
} from '../lib/api.js'
import {
  emptyDraft, readLocalDraft, removeLocalDraft, reviewPayload, sameDraft, validDraft, writeLocalDraft,
} from '../lib/review-drafts.js'

const clone = (v) => JSON.parse(JSON.stringify(v))

// 核查状态不反向依赖网格。队列在入口明确冻结，切图不会扩大批量范围。
export const useReviewStore = defineStore('review', () => {
  const open = ref(false)
  const queue = ref([])
  const index = ref(0)
  const item = ref(null)
  const loading = ref(false)
  const busy = ref(false)
  const error = ref('')
  const notice = ref('')
  const size = ref(null)
  const sizeError = ref('')
  const lines = ref([])
  const libraryId = ref('')
  const operations = ref({ can_undo: false, pending: [] })
  const archivePlan = ref(null)
  const bulk = reactive({ ids: [], text: '', revisions: {}, ready: false, lines: [] })
  let bulkParseGeneration = 0
  const sessions = new Map()
  const owner = `${Date.now()}-${Math.random().toString(36).slice(2)}`
  const active = ref(null)
  const draft = computed(() => active.value?.payload)
  const currentId = computed(() => queue.value[index.value])
  const stale = computed(() => !!draft.value && draft.value.base !== item.value?.revision)
  const hasChanges = (payload) => !!payload && (!!payload.text?.trim() || Object.keys(payload.edits ?? {}).length > 0 || Object.keys(payload.evidence_edits ?? {}).length > 0)
  async function refreshItem() {
    if (!item.value) return
    const data = await fetchImage(item.value.id)
    item.value = data
    if (active.value && !hasChanges(active.value.payload)) {
      active.value.payload = emptyDraft(data)
    }
  }
  let generation = 0
  let parseGeneration = 0
  let metadataGeneration = 0

  async function refreshOperations() {
    const gen = ++metadataGeneration
    const meta = await fetchMetadata()
    if (gen !== metadataGeneration) return null
    if (libraryId.value && libraryId.value !== meta.library_id) {
      for (const session of sessions.values()) clearTimeout(session.timer)
      sessions.clear()
      libraryId.value = meta.library_id
      operations.value = meta.operations
      bulk.ready = false
      archivePlan.value = null
      active.value = null
      item.value = null
      open.value = false
      generation++
      throw new Error('服务已切换到另一图库，请重新进入检查；原草稿保留在原图库')
    }
    libraryId.value = meta.library_id
    operations.value = meta.operations
    return meta
  }

  async function syncSession(session) {
    if (session.syncing) return session.syncing
    session.syncing = (async () => {
      while (session.dirty) {
        const serial = session.serial
        const payload = clone(session.payload)
        try {
          const saved = await putDraft(session.id, payload, session.revision, session.library)
          session.revision = saved.revision
          if (serial === session.serial) {
            session.dirty = false
            session.message = '草稿已保留（未保存为正式资料）'
            removeLocalDraft(localStorage, session.library, session.id, owner)
          } else {
            writeLocalDraft(localStorage, session.library, session.id, {
              payload: session.payload, revision: session.revision, owner,
            })
          }
        } catch (e) {
          session.message = `草稿同步失败：${e.message}；本页输入保留，不自动重试`
          session.failed = true
          break
        }
      }
    })()
    await session.syncing
    session.syncing = null
  }

  function changed() {
    const s = active.value
    if (!s || busy.value) return
    s.serial++
    s.dirty = true
    s.failed = false
    const ok = writeLocalDraft(localStorage, s.library, s.id, { payload: s.payload, revision: s.revision, owner })
    s.message = ok ? '草稿正在同步；尚未保存为正式资料' : '浏览器无法保留草稿，请等待同步后再关闭'
    lines.value = []
    parseGeneration++
    clearTimeout(s.timer)
    s.timer = setTimeout(() => { void syncSession(s) }, 300)
  }

  async function show(position) {
    if (busy.value || position < 0 || position >= queue.value.length) return
    index.value = position
    const id = currentId.value
    const gen = ++generation
    parseGeneration++
    loading.value = true
    item.value = null
    active.value = null
    size.value = null
    sizeError.value = ''
    lines.value = []
    error.value = ''
    archivePlan.value = null
    try {
      await refreshOperations()
      if (gen !== generation || !open.value) return
      const [data, stored] = await Promise.all([fetchImage(id), fetchDraft(id)])
      if (gen !== generation || !open.value) return
      if (stored.library_id && stored.library_id !== libraryId.value) {
        throw new Error('读取期间图库已切换，请重新进入检查；未混用另一图库草稿')
      }
      let session = sessions.get(id)
      if (!session) {
        let local = readLocalDraft(localStorage, libraryId.value, id)
        if (local && sameDraft(local.payload, stored.payload)) {
          // 页面在同步成功响应前关闭：内容相同则采用服务端新版本，不误报冲突。
          removeLocalDraft(localStorage, libraryId.value, id)
          local = null
        }
        session = reactive({
          id, library: libraryId.value,
          payload: local?.payload ?? (validDraft(stored.payload) ? stored.payload : emptyDraft(data)),
          revision: local?.revision ?? stored.revision,
          serial: 0, dirty: !!local, failed: false, syncing: null, timer: null,
          message: local ? '已恢复浏览器草稿，尚未保存为正式资料' : '草稿与正式资料分开保存',
        })
        if (local && local.revision !== stored.revision) {
          session.failed = true
          session.message = '其他页面已修改草稿，本地输入已保留；请先核对，不会自动覆盖'
        }
        if (!local && stored.payload != null && !validDraft(stored.payload)) {
          session.failed = true
          session.message = '草稿格式异常，原草稿仍保留；请明确放弃后再编辑，不会静默覆盖'
        }
        sessions.set(id, session)
      }
      if (!hasChanges(session.payload)) session.payload = emptyDraft(data)
      item.value = data
      active.value = session
      if (session.dirty && !session.failed) void syncSession(session)
      fetchFileSize(id).then((value) => {
        if (gen === generation && data.file_id === value.file_id) size.value = value.bytes
      }).catch((e) => { if (gen === generation) sizeError.value = e.message })
    } catch (e) { if (gen === generation) error.value = e.message }
    finally { if (gen === generation) loading.value = false }
  }

  async function start(ids, first = 0) {
    if (busy.value || !ids.length) return
    queue.value = [...ids]
    open.value = true
    notice.value = ''
    await show(Math.max(0, first))
  }
  function close() {
    if (busy.value) return
    open.value = false
    generation++
    item.value = null
    active.value = null
    archivePlan.value = null
  }
  function step(delta) { return show(index.value + delta) }

  function editSource(source, field, value) {
    if (!draft.value || busy.value) return
    const edits = draft.value.edits
    edits[source.id] = { ...(edits[source.id] ?? { id: source.id }), [field]: value }
    changed()
  }
  function dismissEvidence(evidence, value) {
    draft.value.evidence_edits[evidence.id] = { id: evidence.id, dismissed: value }
    changed()
  }
  async function parse() {
    const gen = ++parseGeneration
    const s = active.value
    if (!s) return
    try {
      const value = await parseLinks(s.payload.text)
      if (gen === parseGeneration && active.value === s) lines.value = value.lines
    } catch (e) { if (gen === parseGeneration) error.value = e.message }
  }

  async function save(next = false) {
    const s = active.value
    if (!s || busy.value || stale.value) return false
    busy.value = true
    error.value = ''
    try {
      clearTimeout(s.timer)
      await syncSession(s)
      if (s.failed) throw new Error(s.message)
      const payload = reviewPayload(s.payload, s.id)
      payload.confirm_scope = Object.values(s.payload.edits).some((e) => e.time_scope_ids?.length > 1)
      const result = await saveReview(payload, s.library)
      const data = result.items[0]
      item.value = data
      s.payload = { ...emptyDraft(data), text: result.lines.filter((l) => l.error).map((l) => l.input).join('\n') }
      s.serial++
      s.dirty = true
      writeLocalDraft(localStorage, s.library, s.id, { payload: s.payload, revision: s.revision, owner })
      await syncSession(s)
      lines.value = result.lines.filter((l) => l.error)
      notice.value = result.lines.some((l) => l.error)
        ? '有效内容已保存；错误行仍留在草稿，请纠正后继续'
        : '资料已保存，未自动归档'
      await refreshOperations()
      busy.value = false
      if (next && !lines.value.length && !s.failed) await step(1)
      return true
    } catch (e) { error.value = e.message; return false }
    finally { busy.value = false }
  }

  async function discard() {
    const s = active.value
    if (!s || busy.value) return
    busy.value = true
    try {
      clearTimeout(s.timer)
      if (s.syncing) await s.syncing
      const stored = await fetchDraft(s.id)
      // 只放弃本页已读过的版本，不能借重新读取版本号清除另一页面的新草稿。
      if (stored.revision !== s.revision) {
        s.failed = true
        throw new Error('另一页面已修改草稿，未清空；请用“读取最新草稿”核对')
      }
      const saved = await putDraft(s.id, null, s.revision, s.library)
      const data = await fetchImage(s.id)
      s.revision = saved.revision
      s.payload = emptyDraft(data)
      s.failed = false
      s.dirty = false
      s.message = '草稿已放弃；正式来源未删除'
      removeLocalDraft(localStorage, s.library, s.id, owner)
      item.value = data
      lines.value = []
    } catch (e) { error.value = e.message }
    finally { busy.value = false }
  }

  async function reloadDraft() {
    const s = active.value
    if (!s || busy.value) return
    busy.value = true
    try {
      clearTimeout(s.timer)
      if (s.syncing) await s.syncing
      const [stored, data] = await Promise.all([fetchDraft(s.id), fetchImage(s.id)])
      // 这是明确的读取动作，不写服务端，也不删除其他页面的草稿。
      if (stored.payload != null && !validDraft(stored.payload)) throw new Error('最新草稿格式异常，原内容保留；请明确放弃后继续')
      s.revision = stored.revision
      s.payload = stored.payload ?? emptyDraft(data)
      s.failed = false
      s.dirty = false
      s.message = '已读取最新草稿（未保存为正式资料）'
      removeLocalDraft(localStorage, s.library, s.id, owner)
      item.value = data
      lines.value = []
    } catch (e) { error.value = e.message }
    finally { busy.value = false }
  }

  async function prepareArchive(ids, force = false) {
    if (busy.value) return
    busy.value = true
    error.value = ''
    try {
      archivePlan.value = { ...(await planArchive([...ids], force, libraryId.value)), ids: [...ids] }
    } catch (e) { error.value = e.message }
    finally { busy.value = false }
    // 单图正常归档有配套撤销，无额外弹框；缺项、强制或多图仍展示清单。
    if (ids.length === 1 && !force && archivePlan.value && !archivePlan.value.errors.length) {
      return archive(false)
    }
    return false
  }
  async function archive(confirmed = false) {
    const plan = archivePlan.value
    if (!plan || plan.errors.length || busy.value) return false
    busy.value = true
    error.value = ''
    try {
      await executeArchive({ ids: plan.ids, token: plan.token, force: plan.force, confirmed }, libraryId.value)
      archivePlan.value = null
      notice.value = `已归档 ${plan.ids.length} 张；来源核查状态保持不变`
      await refreshOperations()
      if (item.value && plan.ids.includes(item.value.id)) await refreshItem()
      return true
    } catch (e) {
      error.value = e.message
      await refreshOperations().catch(() => {})
      return false
    } finally { busy.value = false }
  }
  async function undo() {
    if (busy.value || !operations.value.can_undo) return false
    busy.value = true
    try {
      await undoOperation(operations.value.id, libraryId.value)
      notice.value = '已撤销最近一次操作；草稿未视为正式资料'
      await refreshOperations()
      await refreshItem()
      return true
    } catch (e) { error.value = e.message; await refreshOperations().catch(() => {}); return false }
    finally { busy.value = false }
  }
  async function recover(id, action) {
    if (busy.value) return false
    busy.value = true
    try {
      await recoverOperation(id, action, libraryId.value)
      notice.value = action === 'finish' ? '文件操作已完成' : '已恢复操作前状态'
      await refreshOperations()
      return true
    } catch (e) { error.value = e.message; await refreshOperations().catch(() => {}); return false }
    finally { busy.value = false }
  }

  async function prepareBulk(ids) {
    if (busy.value) return
    busy.value = true
    error.value = ''
    try {
      await refreshOperations()
      const items = []
      // 限制同时请求的数量，避免千张选择一口气占满连接。
      for (let i = 0; i < ids.length; i += 10) {
        items.push(...await Promise.all(ids.slice(i, i + 10).map(fetchImage)))
      }
      Object.assign(bulk, { ids: [...ids], text: '', revisions: Object.fromEntries(items.map((i) => [i.id, i.revision])), ready: true, lines: [] })
    } catch (e) { error.value = e.message }
    finally { busy.value = false }
  }
  function bulkChanged() { bulkParseGeneration++; bulk.lines = [] }
  async function parseBulk() {
    const gen = ++bulkParseGeneration
    const text = bulk.text
    try {
      const result = await parseLinks(text)
      if (gen === bulkParseGeneration && bulk.ready && text === bulk.text) bulk.lines = result.lines
    } catch (e) { if (gen === bulkParseGeneration) error.value = e.message }
  }
  async function saveBulk() {
    if (busy.value || !bulk.ready) return false
    busy.value = true
    try {
      const result = await saveReview({ ids: [...bulk.ids], text: bulk.text, revisions: bulk.revisions, confirm_scope: true }, libraryId.value)
      bulk.lines = result.lines.filter((l) => l.error)
      bulk.text = bulk.lines.map((l) => l.input).join('\n')
      bulk.revisions = Object.fromEntries(result.items.map((i) => [i.id, i.revision]))
      notice.value = bulk.text ? '有效链接已追加给每张所选图；错误行已保留' : '链接已追加，仍待逐图核查，未自动归档'
      bulk.ready = !!bulk.text
      await refreshOperations()
      return true
    } catch (e) { error.value = e.message; return false }
    finally { busy.value = false }
  }
  return {
    open, queue, index, item, loading, busy, error, notice, size, sizeError, lines,
    libraryId, operations, archivePlan, bulk, active, draft, stale, currentId,
    refreshOperations, start, show, close, step, changed, editSource, dismissEvidence,
    parse, save, discard, reloadDraft, prepareArchive, archive, undo, recover, prepareBulk, bulkChanged, parseBulk, saveBulk,
  }
})
