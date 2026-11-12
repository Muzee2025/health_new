<template>
  <main class="auth-page" :style="backgroundStyle">
    <section class="auth-story" aria-label="心域智链">
      <img :src="brandLogo" class="business-brand" alt="心域智链" width="152" height="52" />
      <div>
        <h2>让每一份心事，<br />都有温柔的回应。</h2>
        <p>从了解自己开始，在倾诉与陪伴中，找到适合自己的节奏。</p>
      </div>
      <img :src="companion" class="auth-illustration" alt="" width="300" height="220" />
    </section>
    <section class="auth-form-region">
      <div class="auth-form">
        <img
          :src="brandLogo"
          class="business-brand auth-mobile-brand"
          alt="心域智链"
          width="152"
          height="52"
        />
        <slot />
      </div>
    </section>
  </main>
</template>

<script setup>
import { getVisualAsset } from '../design/asset-registry'
const brandLogo = getVisualAsset('brandLogo').url
const companion = getVisualAsset('companion').url
const loginBackground = getVisualAsset('loginBackground').url
const backgroundStyle = { '--library-login-background': `url("${loginBackground}")` }
</script>

<style scoped>
.auth-story h2 {
  max-width: 420px;
  color: var(--brand-700);
  font: 400 clamp(28px, 3.2vw, 44px)/1.6 var(--font-editorial);
}
.auth-form :deep(h1) {
  margin: 0 0 var(--space-3);
  font-size: var(--text-h2);
  line-height: var(--line-height-heading);
}
.auth-form :deep(.auth-intro) {
  color: var(--text-secondary);
  margin: 0 0 var(--space-6);
  line-height: var(--line-height);
}
.auth-form :deep(.auth-field-help) {
  margin: var(--space-2) 0 0;
  color: var(--text-secondary);
  font-size: var(--text-xs);
  line-height: var(--line-height);
}
.auth-form :deep(.auth-optional) {
  margin: 0 0 var(--space-5);
  padding: var(--space-4);
  min-width: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}
.auth-form :deep(.auth-optional legend) {
  padding: 0 var(--space-2);
  color: var(--text-secondary);
  font-size: var(--text-sm);
}
.auth-form :deep(.auth-optional .el-form-item:last-child) {
  margin-bottom: 0;
}
@media (max-width: 600px) {
  .auth-form :deep(h1) {
    font-size: var(--text-h3);
  }
}
</style>
