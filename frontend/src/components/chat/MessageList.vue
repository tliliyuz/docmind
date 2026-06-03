<template>
  <div ref="scrollContainer" class="message-list" @scroll="handleScroll">
    <MessageItem
      v-for="msg in messages"
      :key="msg.id"
      :msg="msg"
      @regenerate="$emit('regenerate')"
    />

    <!-- 新消息浮动按钮 -->
    <Transition name="fade">
      <button
        v-if="showScrollBtn"
        class="scroll-bottom-btn"
        @click="scrollToBottom(true)"
      >
        <i class="fas fa-chevron-down"></i>
        <span>新消息</span>
      </button>
    </Transition>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted } from 'vue'
import MessageItem from './MessageItem.vue'

const props = defineProps({
  messages: { type: Array, required: true },
})

defineEmits(['regenerate'])

const scrollContainer = ref(null)
const showScrollBtn = ref(false)
let isAutoScrolling = false

/** 判断是否在底部附近 */
function isNearBottom() {
  const el = scrollContainer.value
  if (!el) return true
  return el.scrollHeight - el.scrollTop - el.clientHeight < 100
}

/** 滚动到底部 */
function scrollToBottom(smooth = false) {
  const el = scrollContainer.value
  if (!el) return
  isAutoScrolling = true
  el.scrollTo({
    top: el.scrollHeight,
    behavior: smooth ? 'smooth' : 'instant',
  })
  showScrollBtn.value = false
  setTimeout(() => { isAutoScrolling = false }, 300)
}

/** 监听滚动事件 */
function handleScroll() {
  if (isAutoScrolling) return
  showScrollBtn.value = !isNearBottom()
}

/** 消息变化时自动滚动 */
watch(
  () => props.messages.length,
  () => {
    nextTick(() => {
      if (isNearBottom()) {
        scrollToBottom()
      } else {
        showScrollBtn.value = true
      }
    })
  }
)

/** 流式内容变化时持续滚动 */
watch(
  () => {
    const last = props.messages[props.messages.length - 1]
    return last ? last.content : ''
  },
  () => {
    if (isNearBottom()) {
      nextTick(scrollToBottom)
    }
  }
)

onMounted(() => {
  scrollToBottom()
})

defineExpose({ scrollToBottom })
</script>

<style scoped>
.message-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: var(--dm-space-4) var(--dm-space-6);
  position: relative;
}

.scroll-bottom-btn {
  position: sticky;
  bottom: var(--dm-space-4);
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: var(--dm-bg-card);
  border: 1px solid var(--dm-border);
  border-radius: var(--dm-radius-xl);
  box-shadow: var(--dm-shadow-md);
  color: var(--dm-text-primary);
  font-size: var(--dm-text-xs);
  font-weight: var(--dm-weight-medium);
  cursor: pointer;
  transition: all var(--dm-transition-fast);
  z-index: 5;
  margin: 0 auto;
  width: fit-content;
}

.scroll-bottom-btn:hover {
  background: var(--dm-bg-page);
  border-color: var(--dm-text-primary);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--dm-transition-fast);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
