<script setup>
// 站点标志：品牌色圆角方块 + 白色首字母。纯 CSS 绘制（没有图片文件，任意缩放都清晰，深浅主题通用）。
// 用于缩略图左下角、右侧面板和大图预览里。
defineProps({
  platform: { type: Object, required: true }, // { name, color, letter }
  uncertain: Boolean, // 只知道站点、缺具体作品：右上角加一个小圆点提示
  size: { type: Number, default: 22 },
})
</script>

<template>
  <span
    class="pbadge"
    :class="{ uncertain }"
    :style="{ '--c': platform.color, '--s': size + 'px' }"
    role="img"
    :aria-label="platform.name"
  >
    <span class="ch">{{ platform.letter }}</span>
  </span>
</template>

<style scoped>
.pbadge {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: none;
  width: var(--s);
  height: var(--s);
  border-radius: calc(var(--s) * 0.26);
  background: var(--c);
  color: #fff;
  /* 白色细描边：压在任何颜色的图片上都分得清边界（深色图、浅色图都一样清晰） */
  box-shadow:
    0 0 0 1.5px rgba(255, 255, 255, 0.9),
    0 1px 4px rgba(0, 0, 0, 0.45);
  font-weight: 700;
  font-size: calc(var(--s) * 0.58);
  line-height: 1;
  user-select: none;
}
.ch {
  transform: translateY(-0.02em);
}
/* "只知道站点、缺具体作品"：右上角一个琥珀色小圆点，和整理时的"需补链接"提示同色 */
.uncertain::after {
  content: '';
  position: absolute;
  top: calc(var(--s) * -0.18);
  right: calc(var(--s) * -0.18);
  width: calc(var(--s) * 0.38);
  height: calc(var(--s) * 0.38);
  border-radius: 50%;
  background: #f5a524;
  box-shadow: 0 0 0 1.5px #fff;
}
</style>
