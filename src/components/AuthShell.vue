<template>
  <main class="auth-page" :style="backgroundStyle">
    <section class="auth-story" aria-label="心域智链">
      <img :src="brandLogo" class="business-brand" alt="心域智链" width="152" height="52" />
      <div>
        <h1>让每一份心事，<br />都有温柔的回应。</h1>
        <p>从了解自己开始，在倾诉与陪伴中，找到适合自己的节奏。</p>
      </div>
      <img :src="companion" class="auth-illustration" alt="" width="300" height="220" />
    </section>
    <section class="auth-form-region">
      <div class="auth-form">
        <img :src="brandLogo" class="business-brand auth-mobile-brand" alt="心域智链" width="152" height="52" />
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
