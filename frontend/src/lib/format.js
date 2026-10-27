// 显示用的小工具函数（纯函数）。

const PLATFORM_NAMES = { pixiv: 'Pixiv', x: 'X', zerochan: 'Zerochan' }

/**
 * 把后端的 source_hint 变成角标文字。
 * hint 形如 { platform: 'pixiv', post_id: '12345678', page: 0 }；
 * post_id 为空表示"只知道大概来自哪个平台"（X 网页另存的 media key）。
 * 没有建议返回 null。
 */
export function hintLabel(hint) {
  if (!hint || !hint.platform) return null
  const name = PLATFORM_NAMES[hint.platform] ?? hint.platform
  return hint.post_id ? `可能是 ${name}:${hint.post_id}` : `可能来自 ${name}，需补链接`
}

/** 角标的短写，网格里空间小。 */
export function hintShort(hint) {
  if (!hint || !hint.platform) return null
  const name = PLATFORM_NAMES[hint.platform] ?? hint.platform
  return hint.post_id ? `${name} ${hint.post_id}` : `${name}?`
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
