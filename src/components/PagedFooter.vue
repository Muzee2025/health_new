<template>
  <div class="pagination-wrapper" :class="align">
    <el-pagination
      :current-page="currentPage"
      :page-size="pageSize"
      :page-sizes="pageSizes"
      :pager-count="5"
      :layout="layout"
      :total="total"
      :hide-on-single-page="hideOnSinglePage"
      :aria-label="ariaLabel"
      @update:current-page="emit('update:currentPage', $event)"
      @update:page-size="emit('update:pageSize', $event)"
      @current-change="emit('change', $event)"
    />
  </div>
</template>

<script setup>
import { ElPagination } from 'element-plus'

/**
 * The paged table footer. Five screens had their own copy of this block and its
 * CSS; the only real differences were alignment and whether the size selector
 * was offered, so both are props.
 */
defineProps({
  currentPage: { type: Number, required: true },
  pageSize: { type: Number, required: true },
  total: { type: Number, required: true },
  pageSizes: { type: Array, default: () => [10, 20, 50] },
  layout: { type: String, default: 'total, sizes, prev, pager, next' },
  hideOnSinglePage: { type: Boolean, default: false },
  align: { type: String, default: 'end' },
  ariaLabel: { type: String, default: '' },
})

const emit = defineEmits(['update:currentPage', 'update:pageSize', 'change'])
</script>

<style scoped>
.pagination-wrapper {
  margin-top: 20px;
  display: flex;
  min-width: 0;
  width: 100%;
}

.pagination-wrapper.end {
  justify-content: flex-end;
}

.pagination-wrapper.center {
  justify-content: center;
}

@media (max-width: 760px) {
  .pagination-wrapper.end {
    justify-content: flex-start;
    overflow: visible;
  }

  .pagination-wrapper :deep(.el-pagination) {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-start;
    gap: 8px 10px;
    max-width: 100%;
  }

  .pagination-wrapper :deep(.el-pagination__total) {
    order: 1;
    margin-right: 0;
  }

  .pagination-wrapper :deep(.el-pagination__sizes) {
    order: 2;
    margin: 0;
  }

  .pagination-wrapper :deep(.el-pagination__sizes .el-select) {
    width: 104px;
  }

  .pagination-wrapper :deep(.btn-prev) {
    order: 3;
    margin: 0;
  }

  .pagination-wrapper :deep(.el-pager) {
    order: 4;
    margin: 0;
  }

  .pagination-wrapper :deep(.btn-next) {
    order: 5;
    margin: 0;
  }
}
</style>
