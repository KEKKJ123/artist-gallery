import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import ToastNotice from '../src/components/ToastNotice.vue'

let wrapper
beforeEach(() => { vi.useFakeTimers() })
afterEach(() => { wrapper?.unmount(); vi.clearAllTimers(); vi.useRealTimers() })

const toast = () => wrapper.find('.toast')
async function show(message, seq) {
  await wrapper.setProps({ message, seq })
}

it('序号变化后显示，3 秒后自动消失', async () => {
  wrapper = mount(ToastNotice, { props: { message: '', seq: 0 } })
  expect(toast().exists()).toBe(false)
  await show('已归档 1 张', 1)
  expect(toast().text()).toBe('已归档 1 张')
  await vi.advanceTimersByTimeAsync(2999)
  expect(toast().exists()).toBe(true)
  await vi.advanceTimersByTimeAsync(1)
  expect(toast().exists()).toBe(false)
})

it('新提示重新计时，相同文字也会再次显示', async () => {
  wrapper = mount(ToastNotice, { props: { message: '', seq: 0 } })
  await show('已归档 1 张', 1)
  await vi.advanceTimersByTimeAsync(2000)
  await show('已归档 1 张', 2)
  await vi.advanceTimersByTimeAsync(2000)
  expect(toast().exists()).toBe(true)
  await vi.advanceTimersByTimeAsync(1000)
  expect(toast().exists()).toBe(false)
  await show('已归档 1 张', 3)
  expect(toast().exists()).toBe(true)
})

it('悬停期间不消失，移开后重新计满 3 秒', async () => {
  wrapper = mount(ToastNotice, { props: { message: '', seq: 0 } })
  await show('已归档 1 张', 1)
  await vi.advanceTimersByTimeAsync(2500)
  await toast().trigger('mouseenter')
  await vi.advanceTimersByTimeAsync(10000)
  expect(toast().exists()).toBe(true)
  await toast().trigger('mouseleave')
  await vi.advanceTimersByTimeAsync(2999)
  expect(toast().exists()).toBe(true)
  await vi.advanceTimersByTimeAsync(1)
  expect(toast().exists()).toBe(false)
})

it('播报区域常驻，不显示时也存在；没有撤销按钮', async () => {
  wrapper = mount(ToastNotice, { props: { message: '', seq: 0 } })
  const region = wrapper.find('[role="status"]')
  expect(region.exists()).toBe(true)
  expect(region.attributes('aria-live')).toBe('polite')
  await show('已撤销最近一次操作', 1)
  expect(wrapper.find('button').exists()).toBe(false)
})

it('空消息不显示；卸载后不留计时器', async () => {
  wrapper = mount(ToastNotice, { props: { message: '', seq: 0 } })
  await show('', 1)
  expect(toast().exists()).toBe(false)
  await show('已归档 2 张', 2)
  wrapper.unmount()
  wrapper = null
  expect(vi.getTimerCount()).toBe(0)
})
