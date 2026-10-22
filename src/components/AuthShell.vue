<template>
  <main class="auth-page">
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
import brandLogo from '../assets/brand/brand-logo-horizontal.svg'
import companion from '../assets/illustrations/open-doodles/illu-open-doodles-loving.svg'
</script>
