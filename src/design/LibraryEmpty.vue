<script setup>
import { computed } from 'vue'
import { ElEmpty } from 'element-plus'
import { getVisualAsset } from './asset-registry'

defineOptions({ inheritAttrs: false })
const props = defineProps({ role: { type: String, default: 'emptyList' } })
const image = computed(() => getVisualAsset(props.role))
</script>

<template>
  <ElEmpty v-bind="$attrs" :image="image.url" :data-library-asset-id="image.id">
    <template v-for="(_, name) in $slots" #[name]="slotProps">
      <slot :name="name" v-bind="slotProps || {}" />
    </template>
  </ElEmpty>
</template>
