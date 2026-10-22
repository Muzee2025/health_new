<template>
  <main class="not-found">
    <img :src="illustration" alt="" width="320" height="180" />
    <h1>这个页面暂时找不到</h1>
    <p>请检查地址，或返回首页继续使用。</p>
    <el-button type="primary" @click="$router.push('/')">返回首页</el-button>
  </main>
</template>
<script setup>
import illustration from '../assets/illustrations/illu-not-found-320.svg'
</script>
<style scoped>
.not-found { min-height: 100svh; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 24px; text-align: center; }
.not-found h1 { font-size: 24px; margin: 20px 0 4px; }
.not-found p { color: var(--text-secondary); margin-bottom: 24px; }
.not-found img { max-width: 100%; height: auto; }
</style>
