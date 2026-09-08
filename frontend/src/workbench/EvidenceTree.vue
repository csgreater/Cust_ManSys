<template>
  <span v-if="isScalar" class="evidence-scalar">{{ displayValue }}</span>
  <ul v-else class="evidence-tree">
    <li v-for="(child, key) in value" :key="key">
      <b>{{ label(key) }}</b>
      <EvidenceTree :value="child" />
    </li>
  </ul>
</template>

<script setup>
import { computed } from "vue";
import { evidenceFieldLabel } from "./contract.js";

const props = defineProps({ value: { default: null } });
const isScalar = computed(() => props.value === null || typeof props.value !== "object");
const displayValue = computed(() => {
  if (props.value === null || props.value === undefined || props.value === "") return "—";
  if (typeof props.value === "boolean") return props.value ? "是" : "否";
  return `${props.value}`;
});
function label(key) { return evidenceFieldLabel(key); }
</script>
