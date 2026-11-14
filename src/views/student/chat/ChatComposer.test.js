import { afterEach, describe, expect, it, vi } from 'vitest'
import * as Vue from 'vue'
import { createRenderer } from 'vue'
import { compileScript, compileTemplate, parse } from '@vue/compiler-sfc'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { ElInput } from 'element-plus'
import ChatComposer from './ChatComposer.vue'

vi.mock('vue', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    useSSRContext: () => ({ modules: new Set() }),
  }
})

vi.mock('element-plus', async () => {
  const { h } = await import('vue')

  return {
    ElInput: {
      inheritAttrs: false,
      props: ['modelValue', 'type', 'rows', 'placeholder', 'resize', 'disabled'],
      emits: ['update:modelValue'],
      setup(props, { attrs, emit }) {
        return () =>
          h('textarea', {
            ...attrs,
            value: props.modelValue,
            rows: props.rows,
            placeholder: props.placeholder,
            disabled: props.disabled,
            onInput: (event) => emit('update:modelValue', event.target.value),
          })
      },
    },
  }
})

const composerSource = readFileSync(new URL('./ChatComposer.vue', import.meta.url), 'utf8')
const composerFilename = 'src/views/student/chat/ChatComposer.vue'
const { descriptor } = parse(composerSource, { filename: composerFilename })
if (!descriptor.template || !descriptor.scriptSetup)
  throw new Error('ChatComposer SFC blocks were not found')
const composerScript = compileScript(descriptor, { id: 'chat-composer-test' })
const composerTemplate = compileTemplate({
  source: descriptor.template.content,
  filename: composerFilename,
  id: 'chat-composer-test',
  compilerOptions: { bindingMetadata: composerScript.bindings, mode: 'function' },
})
if (composerTemplate.errors.length) throw composerTemplate.errors[0]
ChatComposer.render = runInNewContext(`(Vue) => { ${composerTemplate.code} }`)(Vue)

function createHostRenderer() {
  const insert = (node, parent, anchor = null) => {
    if (node.parent) {
      const oldIndex = node.parent.children.indexOf(node)
      if (oldIndex >= 0) node.parent.children.splice(oldIndex, 1)
    }
    const index = anchor ? parent.children.indexOf(anchor) : -1
    if (index < 0) parent.children.push(node)
    else parent.children.splice(index, 0, node)
    node.parent = parent
  }

  return createRenderer({
    patchProp(node, key, _previous, next) {
      node.props[key] = next
    },
    insert,
    remove(node) {
      if (!node.parent) return
      const index = node.parent.children.indexOf(node)
      if (index >= 0) node.parent.children.splice(index, 1)
      node.parent = null
    },
    createElement(type) {
      return { type, props: {}, children: [], parent: null, text: '' }
    },
    createText(text) {
      return { type: '#text', props: {}, children: [], parent: null, text }
    },
    createComment(text) {
      return { type: '#comment', props: {}, children: [], parent: null, text }
    },
    setText(node, text) {
      node.text = text
    },
    setElementText(node, text) {
      node.text = text
      node.children = []
    },
    parentNode(node) {
      return node.parent
    },
    nextSibling(node) {
      if (!node.parent) return null
      const index = node.parent.children.indexOf(node)
      return node.parent.children[index + 1] || null
    },
    insertStaticContent(content, parent, anchor) {
      const node = {
        type: '#static',
        props: {},
        children: [],
        parent: null,
        text: content,
      }
      insert(node, parent, anchor)
      return [node, node]
    },
  })
}

function findNode(node, predicate) {
  if (predicate(node)) return node
  for (const child of node.children || []) {
    const match = findNode(child, predicate)
    if (match) return match
  }
  return null
}

function collectText(node) {
  return `${node.text || ''}${(node.children || []).map(collectText).join('')}`
}

const baseProps = {
  modelValue: '',
  isAnonymous: false,
  currentSessionId: 'session-1',
  isTyping: false,
  deepThinkEnabled: false,
  lastReplyChars: 0,
  lastReplyRatio: 1,
}

function mountComposer(props = {}) {
  const root = { type: 'root', props: {}, children: [], parent: null, text: '' }
  const app = createHostRenderer().createApp(ChatComposer, { ...baseProps, ...props })
  app.component('ElInput', ElInput)
  app.mount(root)
  return { app, root }
}

afterEach(() => {
  vi.clearAllMocks()
})

describe('ChatComposer component contract', () => {
  it('emits draft updates and sends on Enter or button activation', () => {
    const onUpdate = vi.fn()
    const onSend = vi.fn()
    const { app, root } = mountComposer({
      modelValue: 'draft',
      'onUpdate:modelValue': onUpdate,
      onSend,
    })

    try {
      const input = findNode(root, (node) => node.type === 'textarea')
      expect(input).toBeTruthy()
      expect(input.props.value).toBe('draft')
      input.props.onInput({ target: { value: 'updated draft' } })
      expect(onUpdate).toHaveBeenCalledWith('updated draft')

      const preventDefault = vi.fn()
      input.props.onKeydown({ key: 'Enter', preventDefault })
      expect(preventDefault).toHaveBeenCalledOnce()
      expect(onSend).toHaveBeenCalledOnce()

      const sendButton = findNode(root, (node) => node.props.class === 'send-btn')
      expect(sendButton).toBeTruthy()
      sendButton.props.onClick()
      expect(onSend).toHaveBeenCalledTimes(2)
    } finally {
      app.unmount()
    }
  })

  it.each([
    ['empty draft', { modelValue: '' }, true],
    ['real-name without session', { modelValue: 'hello', currentSessionId: null }, true],
    ['anonymous without session', { modelValue: 'hello', isAnonymous: true }, false],
    ['real-name with session', { modelValue: 'hello' }, false],
    ['typing', { modelValue: 'hello', isTyping: true }, true],
  ])('preserves send disabled rule for %s', (_name, props, expectedDisabled) => {
    const { app, root } = mountComposer(props)
    try {
      const sendButton = findNode(root, (node) => node.props.class === 'send-btn')
      expect(sendButton?.props.disabled).toBe(expectedDisabled)
    } finally {
      app.unmount()
    }
  })

  it.each([
    ['real-name without session', { currentSessionId: null }, true],
    ['anonymous without session', { currentSessionId: null, isAnonymous: true }, false],
    ['real-name with session', {}, false],
  ])('preserves textarea session gating for %s', (_name, props, expectedDisabled) => {
    const { app, root } = mountComposer(props)
    try {
      const input = findNode(root, (node) => node.type === 'textarea')
      expect(input?.props.disabled).toBe(expectedDisabled)
    } finally {
      app.unmount()
    }
  })

  it('disables deep-think toggle while typing and emits a toggle event otherwise', () => {
    const onToggle = vi.fn()
    const typingPage = mountComposer({ modelValue: 'hello', isTyping: true })
    try {
      const toggle = findNode(typingPage.root, (node) => node.props.class === 'deep-think-toggle')
      expect(toggle?.props.disabled).toBe(true)
    } finally {
      typingPage.app.unmount()
    }

    const readyPage = mountComposer({
      modelValue: 'hello',
      deepThinkEnabled: true,
      onToggleDeep: onToggle,
    })
    try {
      const toggle = findNode(readyPage.root, (node) =>
        node.props.class?.includes('deep-think-toggle'),
      )
      expect(toggle?.props.disabled).toBe(false)
      expect(collectText(toggle)).toContain('\u6df1\u5ea6\u601d\u8003: \u5f00')
      toggle.props.onClick()
      expect(onToggle).toHaveBeenCalledOnce()
    } finally {
      readyPage.app.unmount()
    }
  })

  it('shows reply statistics only when a reply count exists and keeps one decimal place', () => {
    const withStats = mountComposer({ lastReplyChars: 12, lastReplyRatio: 1.234 })
    try {
      expect(collectText(withStats.root)).toContain(
        '\u672c\u56de\u7b54\u517112\u5b57\uff0c\u7ea6\u4e3a\u60a8\u5e73\u65f6\u8bf7\u6c42\u76841.2\u500d',
      )
    } finally {
      withStats.app.unmount()
    }

    const withoutStats = mountComposer({ lastReplyChars: 0, lastReplyRatio: 1 })
    try {
      expect(findNode(withoutStats.root, (node) => node.props.class === 'reply-stats')).toBeNull()
    } finally {
      withoutStats.app.unmount()
    }
  })
})
