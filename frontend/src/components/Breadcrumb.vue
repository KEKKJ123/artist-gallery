<script setup>
import { ChevronRight } from '@lucide/vue'
import { computed } from 'vue'
import { breadcrumbs } from '../lib/location.js'

const props = defineProps({ path: { type: String, default: '' } })
const emit = defineEmits(['navigate'])

const crumbs = computed(() => breadcrumbs(props.path))
</script>

<template>
  <ol class="crumbs" aria-label="当前位置">
    <li>
      <button class="crumb" :aria-current="crumbs.length === 0 ? 'page' : undefined" @click="emit('navigate', '')">
        已归档
      </button>
    </li>
    <li v-for="(c, i) in crumbs" :key="c.path">
      <ChevronRight :size="14" class="sep" aria-hidden="true" />
      <button
        class="crumb"
        :aria-current="i === crumbs.length - 1 ? 'page' : undefined"
        @click="emit('navigate', c.path)"
      >
        {{ c.name }}
      </button>
    </li>
  </ol>
</template>

<style scoped>
.crumbs {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 2px;
  margin: 0;
  padding: 0;
  list-style: none;
  min-width: 0;
}
li {
  display: inline-flex;
  align-items: center;
  min-width: 0;
}
.sep {
  flex: none;
  color: var(--fg-dim);
}
.crumb {
  padding: 2px 6px;
  border: none;
  background: transparent;
  border-radius: var(--radius);
  color: var(--fg-dim);
  max-width: 14em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.crumb:hover {
  background: var(--bg-sunken);
  color: var(--fg);
}
.crumb[aria-current='page'] {
  color: var(--fg);
  font-weight: 600;
  pointer-events: none;
}
</style>
