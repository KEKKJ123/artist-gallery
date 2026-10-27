import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

// 界面偏好：主题、缩略图大小、方形/原比例。存在浏览器本地（localStorage），不进图库。
const KEY = 'artist-gallery:prefs'

export const THEMES = ['system', 'light', 'dark']
export const SIZE_MIN = 100
export const SIZE_MAX = 400

function load() {
  try {
    return JSON.parse(localStorage.getItem(KEY)) ?? {}
  } catch {
    return {} // 数据坏了就当没有，用默认值
  }
}

function clampSize(n) {
  const v = Number(n)
  if (!Number.isFinite(v)) return 180
  return Math.min(SIZE_MAX, Math.max(SIZE_MIN, Math.round(v)))
}

export const usePrefsStore = defineStore('prefs', () => {
  const saved = load()
  const theme = ref(THEMES.includes(saved.theme) ? saved.theme : 'system')
  const thumbSize = ref(clampSize(saved.thumbSize ?? 180))
  const square = ref(Boolean(saved.square)) // 默认原比例
  // 右侧面板：第一次打开时，宽屏默认展开，手机（窄屏）默认收起，把地方让给图片
  const panelOpen = ref(saved.panelOpen ?? window.matchMedia('(min-width: 721px)').matches)
  // 左侧文件夹列表：和右侧面板一样，宽屏默认展开，手机默认收起（手机上它以抽屉形式盖在图上）
  const navOpen = ref(saved.navOpen ?? window.matchMedia('(min-width: 721px)').matches)

  function applyTheme() {
    const el = document.documentElement
    if (theme.value === 'system') el.removeAttribute('data-theme')
    else el.setAttribute('data-theme', theme.value)
  }

  function persist() {
    try {
      localStorage.setItem(
        KEY,
        JSON.stringify({
          theme: theme.value,
          thumbSize: thumbSize.value,
          square: square.value,
          panelOpen: panelOpen.value,
          navOpen: navOpen.value,
        }),
      )
    } catch {
      /* 隐私模式等写不进去：本次有效，下次回到默认 */
    }
  }

  watch(theme, applyTheme, { immediate: true })
  watch([theme, thumbSize, square, panelOpen, navOpen], persist)

  function setThumbSize(n) {
    thumbSize.value = clampSize(n)
  }
  function nudgeThumbSize(delta) {
    setThumbSize(thumbSize.value + delta)
  }
  function cycleTheme() {
    theme.value = THEMES[(THEMES.indexOf(theme.value) + 1) % THEMES.length]
  }

  return { theme, thumbSize, square, panelOpen, navOpen, setThumbSize, nudgeThumbSize, cycleTheme }
})
