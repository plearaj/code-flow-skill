<template>
  <div class="orders">
    <OrderRow v-for="order in orders" :key="order.id" :order="order" />
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import OrderRow from "./OrderRow.vue";

const props = defineProps<{ customerId: string; compact?: boolean }>();
const orders = ref([]);

/** Refresh the order list. */
function refresh() {
  orders.value = [];
}

refresh();
</script>
