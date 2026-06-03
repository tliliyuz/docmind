<template>
  <div class="chat-input-bar">
    <div class="input-wrapper" :class="{ shaking: isShaking }">
      <textarea
        ref="textareaRef"
        v-model="inputText"
        class="input-textarea"
        placeholder="输入你的问题…"
        :disabled="streaming"
        maxlength="2000"
        @input="autoResize"
        @keydown="handleKeydown"
      ></textarea>
      <div class="input-footer">
        <label class="deep-think-toggle" :class="{ active: deepThinking }">
          <input v-model="deepThinking" type="checkbox" class="toggle-checkbox" />
          <i class="fas fa-lightbulb"></i>
          <span>深度思考</span>
        </label>
        <div class="input-actions">
          <span class="char-count" :class="{ over: charCount > 2000 }">
            {{ charCount }}/2000
          </span>
          <button
            v-if="!streaming"
            class="send-btn"
            :disabled="!canSend"
            @click="handleSend"
          >
            <i class="fas fa-paper-plane"></i>
          </button>
          <button
            v-else
            class="stop-btn"
            @click="$emit('stop')"
          >
            <i class="fas fa-stop"></i>
            <span>停止生成</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, watch } from 'vue'

const props = defineProps({
  streaming: { type: Boolean, default: false },
})

const emit = defineEmits(['send', 'stop'])

const textareaRef = ref(null)
const inputText = ref('')
const deepThinking = ref(false)
const isShaking = ref(false)

const charCount = computed(() => inputText.value.length)
const canSend = computed(() => inputText.value.trim().length > 0 && charCount.value <= 2000)

/** 自动调整 textarea 高度 */
function autoResize() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 200) + 'px'
}

/** 处理 Enter / Shift+Enter */
function handleKeydown(e) {
  if (props.streaming) return
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

/** 发送消息 */
function handleSend() {
  if (!canSend.value) {
    triggerShake()
    return
  }
  emit('send', { question: inputText.value.trim(), deepThinking: deepThinking.value })
  inputText.value = ''
  nextTick(autoResize)
}

/** 空输入抖动 */
function triggerShake() {
  isShaking.value = true
  setTimeout(() => { isShaking.value = false }, 500)
}

/** 外部注入问题（快捷问题卡片） */
function setText(text) {
  inputText.value = text
  nextTick(autoResize)
}

/** 聚焦输入框 */
function focus() {
  nextTick(() => textareaRef.value?.focus())
}

watch(() => props.streaming, (val) => {
  if (!val) nextTick(focus)
})

defineExpose({ setText, focus })
</script>

<style scoped>
.chat-input-bar {
  padding: 0 var(--dm-space-6) var(--dm-space-6);
  flex-shrink: 0;
}

.input-wrapper {
  max-width: var(--dm-chat-max-width);
  margin: 0 auto;
  background: var(--dm-bg-card);
  border: 1px solid var(--dm-border);
  border-radius: var(--dm-radius-lg);
  box-shadow: var(--dm-shadow-md);
  overflow: hidden;
  transition: border-color var(--dm-transition-normal), box-shadow var(--dm-transition-normal);
}

.input-wrapper:focus-within {
  border-color: var(--dm-text-primary);
  box-shadow: var(--dm-shadow-input-focus);
}

.input-wrapper.shaking {
  animation: shake 0.5s ease;
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  10%, 50%, 90% { transform: translateX(-4px); }
  30%, 70% { transform: translateX(4px); }
}

.input-textarea {
  width: 100%;
  min-height: 52px;
  max-height: 200px;
  padding: 14px 16px 0;
  border: none;
  outline: none;
  resize: none;
  background: transparent;
  font-family: var(--dm-font-family);
  font-size: var(--dm-text-body);
  color: var(--dm-text-primary);
  line-height: var(--dm-leading-body);
}

.input-textarea::placeholder {
  color: var(--dm-text-tertiary);
}

.input-textarea:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.input-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px 10px;
}

.deep-think-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: var(--dm-radius-sm);
  cursor: pointer;
  font-size: var(--dm-text-2xs);
  color: var(--dm-text-secondary);
  transition: all var(--dm-transition-fast);
  user-select: none;
}

.deep-think-toggle:hover {
  background: var(--dm-bg-page);
}

.deep-think-toggle.active {
  color: var(--dm-warning);
  background: var(--dm-warning-light);
}

.toggle-checkbox {
  display: none;
}

.input-actions {
  display: flex;
  align-items: center;
  gap: var(--dm-space-2);
}

.char-count {
  font-size: var(--dm-text-3xs);
  color: var(--dm-text-tertiary);
  font-variant-numeric: tabular-nums;
}

.char-count.over {
  color: var(--dm-danger);
}

.send-btn,
.stop-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: none;
  border-radius: var(--dm-radius-sm);
  cursor: pointer;
  font-size: var(--dm-text-body);
  transition: all var(--dm-transition-fast);
}

.send-btn {
  width: 36px;
  height: 36px;
  background: var(--dm-text-primary);
  color: white;
}

.send-btn:hover:not(:disabled) {
  background: var(--dm-primary-hover);
}

.send-btn:disabled {
  background: var(--dm-border);
  color: var(--dm-text-tertiary);
  cursor: not-allowed;
}

.stop-btn {
  height: 32px;
  padding: 0 12px;
  background: var(--dm-danger-light);
  color: var(--dm-danger);
  font-size: var(--dm-text-xs);
  font-weight: var(--dm-weight-medium);
}

.stop-btn:hover {
  background: var(--dm-danger);
  color: white;
}
</style>
