<script>
import { defineComponent } from 'vue'
import { renderLibraryIcon } from './icon-registry'

export default defineComponent({
  name: 'LibraryIcon',
  inheritAttrs: false,
  props: { name: { type: String, required: true } },
  setup:
    (props, { attrs }) =>
    () =>
      renderLibraryIcon(props.name, attrs),
})
</script>

<style>
.library-icon {
  display: inline-flex;
  flex: none;
  width: 1em;
  height: 1em;
  align-items: center;
  justify-content: center;
  vertical-align: -0.12em;
  color: inherit;
}
.library-icon > svg {
  width: 100%;
  height: 100%;
}
.library-icon--asset {
  background: currentColor;
  mask-position: center;
  mask-repeat: no-repeat;
  mask-size: contain;
  -webkit-mask-position: center;
  -webkit-mask-repeat: no-repeat;
  -webkit-mask-size: contain;
}
</style>
