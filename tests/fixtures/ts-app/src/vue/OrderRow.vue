<template>
  <span>{{ order.id }}</span>
</template>

<script setup lang="ts">
const props = defineProps<{ order: { id: string } }>();
</script>
