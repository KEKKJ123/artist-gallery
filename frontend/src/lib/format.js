// 显示用的小工具函数（纯函数）。

const PLATFORM_NAMES = { pixiv: 'Pixiv', x: 'X', zerochan: 'Zerochan' }

/**
 * 把后端 source_hints 中的一条建议变成显示文字。
 * hint 形如 { platform: 'pixiv', post_id: '12345678', page: 0 }；
 * post_id 为空表示"只知道大概来自哪个平台"（X 网页另存的 media key）。
 * 没有建议返回 null。
 */
export function hintLabel(hint) {
  if (!hint || !hint.platform) return null
  const name = PLATFORM_NAMES[hint.platform] ?? hint.platform
  return hint.post_id ? `可能是 ${name}:${hint.post_id}` : `可能来自 ${name}，需补链接`
}

/**
 * 缩略图占位的宽高比（宽/高）。数据库里有宽高就用，没有（视频）用 4/3。
 * 限制在 0.4 ~ 2.5 之间，免得极端长图把网格撑得很怪。
 */
export function aspectRatio(item) {
  if (item.width && item.height) {
    return Math.min(2.5, Math.max(0.4, item.width / item.height))
  }
  return 4 / 3
}

/** 扩展名转成角标文字，如 '.mp4' → 'MP4'。 */
export function extLabel(ext) {
  return (ext || '').replace(/^\./, '').toUpperCase()
}

/** 是不是视频。GIF 按图片处理（不生成缩略图，但不是视频）。 */
export function isVideo(ext) {
  return ['.mp4', '.webm', '.mov', '.mkv', '.avi', '.m4v'].includes((ext || '').toLowerCase())
}

/** 来源 ID 只是标题显示，不取代图片身份；未知页码不伪造 p0。 */
export function imageCaption(item) {
  const known = item.sources?.find(s => s.status === 'confirmed')
  const hint = item.source_hints?.find(s => s.post_id)
  const source = known || hint
  if (source?.post_id) return `${known ? '' : '疑似 '}${source.post_id}${source.page == null ? '' : `_p${source.page}`}`
  return item.orig_name || (item.id != null ? `图片 #${item.id}` : '未命名')
}
