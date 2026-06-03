<template>
  <div class="welcome-screen">
    <!-- 欢迎语 -->
    <h1 class="welcome-title">我是 DocMind，你的企业知识助手</h1>
    <p class="welcome-desc">选择一个知识库，开始提问吧</p>

    <!-- 快捷问题卡片 -->
    <div class="quick-questions">
      <div
        v-for="item in quickQuestions"
        :key="item.text"
        class="quick-card"
        @click="$emit('select', item.text)"
      >
        <div class="quick-card-icon">
          <i :class="item.icon"></i>
        </div>
        <span class="quick-card-text">{{ item.text }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
defineEmits(['select'])

const quickQuestions = [
  { text: '报销流程是怎样的？', icon: 'fas fa-receipt' },
  { text: '入职需要准备什么？', icon: 'fas fa-user-plus' },
  { text: '如何申请年假？', icon: 'fas fa-calendar-alt' },
  { text: 'VPN 怎么配置？', icon: 'fas fa-shield-alt' },
]
</script>

<style scoped>
.welcome-screen {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--dm-space-12) var(--dm-space-6);
  text-align: center;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.welcome-title {
  font-size: var(--dm-text-xl);
  font-weight: var(--dm-weight-bold);
  color: var(--dm-text-primary);
  margin-bottom: var(--dm-space-2);
  line-height: var(--dm-leading-title);
}

.welcome-desc {
  font-size: var(--dm-text-body);
  color: var(--dm-text-tertiary);
  margin-bottom: var(--dm-space-8);
}

.quick-questions {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--dm-space-3);
  max-width: 480px;
  width: 100%;
}

.quick-card {
  display: flex;
  align-items: center;
  gap: var(--dm-space-3);
  padding: var(--dm-space-4);
  background: var(--dm-bg-card);
  border: 1px solid var(--dm-border);
  border-radius: var(--dm-radius-md);
  cursor: pointer;
  transition: all var(--dm-transition-normal);
}

.quick-card:hover {
  border-color: var(--dm-primary);
  box-shadow: var(--dm-shadow-sm);
  transform: translateY(-1px);
}

.quick-card-icon {
  width: 36px;
  height: 36px;
  background: var(--dm-primary-light);
  border-radius: var(--dm-radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--dm-primary);
  font-size: var(--dm-text-body);
  flex-shrink: 0;
}

.quick-card-text {
  font-size: var(--dm-text-xs);
  color: var(--dm-text-primary);
  font-weight: var(--dm-weight-medium);
  text-align: left;
}
</style>
