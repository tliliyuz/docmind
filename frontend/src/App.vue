<template>
  <AppLayout v-if="!$route.meta.public">
    <router-view />
  </AppLayout>
  <router-view v-else />
</template>

<script setup>
import AppLayout from '@/components/layout/AppLayout.vue'
</script>
