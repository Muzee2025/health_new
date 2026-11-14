import { afterEach, describe, expect, it, vi } from 'vitest'
import * as Vue from 'vue'
import { createRenderer, nextTick } from 'vue'
import { compileScript, compileTemplate, parse } from '@vue/compiler-sfc'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import ChatMessageList from './ChatMessageList.vue'

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
    ElAvatar: {
      props: ['size', 'src'],
      setup(props, { attrs, slots }) {
        return () =>
          h(
            'div',
            {
              ...attrs,
              class: ['avatar-stub', attrs.class],
              'data-src': props.src,
              'data-size': props.size,
            },
            slots.default?.(),
          )
      },
    },
    ElIcon: {
      setup(_props, { slots }) {
        return () => h('span', { class: 'icon-stub' }, slots.default?.())
      },
    },
  }
})

const source = readFileSync(new URL('./ChatMessageList.vue', import.meta.url), 'utf8')
const filename = 'src/views/student/chat/ChatMessageList.vue'
const { descriptor } = parse(source, { filename })
if (!descriptor.template || !descriptor.scriptSetup)
  throw new Error('ChatMessageList SFC blocks were not found')
const script = compileScript(descriptor, { id: 'chat-message-list-test' })
const template = compileTemplate({
  source: descriptor.template.content,
  filename,
  id: 'chat-message-list-test',
  compilerOptions: { bindingMetadata: script.bindings, mode: 'function' },
})
if (template.errors.length) throw template.errors[0]
ChatMessageList.render = runInNewContext('(Vue) => { ' + template.code + ' }')(Vue)

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
      return {
        type,
        props: {},
        children: [],
        parent: null,
        text: '',
        scrollTop: 0,
        scrollHeight: 0,
      }
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
      const node = { type: '#static', props: {}, children: [], parent: null, text: content }
      insert(node, parent, anchor)
      return [node, node]
    },
  })
}

function classNames(node) {
  const value = node?.props?.class
  if (Array.isArray(value)) return value.flat(Infinity).filter(Boolean).join(' ')
  return String(value || '')
}

function hasClass(node, className) {
  return classNames(node).split(/\s+/).includes(className)
}

function findAllNodes(node, predicate, result = []) {
  if (predicate(node)) result.push(node)
  for (const child of node.children || []) findAllNodes(child, predicate, result)
  return result
}

function findNode(node, predicate) {
  return findAllNodes(node, predicate)[0] || null
}

function collectText(node) {
  return String(node?.text || '') + (node?.children || []).map(collectText).join('')
}

function mountList(props = {}) {
  const root = { type: 'root', props: {}, children: [], parent: null, text: '' }
  const app = createHostRenderer().createApp(ChatMessageList, props)
  app.component('LibraryIcon', { render: () => null })
  app.mount(root)
  return { app, root }
}

afterEach(() => {
  vi.clearAllMocks()
})

describe('ChatMessageList component contract', () => {
  it('preserves message order, role layout, and anonymous avatar selection', () => {
    const { app, root } = mountList({
      messages: [
        { id: 'user-1', role: 'user', content: 'first message' },
        { id: 'ai-1', role: 'ai', content: 'second message' },
      ],
      isAnonymous: true,
      userAvatar: 'synthetic-user-avatar',
      anonymousAvatar: 'synthetic-anonymous-avatar',
    })

    try {
      const rows = findAllNodes(root, (node) => hasClass(node, 'message-row'))
      expect(rows.map((node) => classNames(node))).toEqual([
        'message-row row-user',
        'message-row row-ai',
      ])
      expect(collectText(rows[0])).toContain('first message')
      expect(collectText(rows[1])).toContain('second message')
      const avatars = findAllNodes(root, (node) => hasClass(node, 'avatar-stub'))
      expect(avatars[0].props['data-src']).toBe('synthetic-anonymous-avatar')
      expect(avatars[1].props.class).toContain('mail-avatar')
    } finally {
      app.unmount()
    }
  })

  it('marks only matching user messages with the danger class', () => {
    const { app, root } = mountList({
      messages: [
        { id: 'user-risk', role: 'user', content: 'flag this message' },
        { id: 'ai-copy', role: 'ai', content: 'flag in a reply' },
      ],
      isDangerText: (content) => content.includes('flag'),
    })

    try {
      const bubbles = findAllNodes(root, (node) => hasClass(node, 'bubble'))
      expect(hasClass(bubbles[0], 'bubble-danger')).toBe(true)
      expect(hasClass(bubbles[1], 'bubble-danger')).toBe(false)
    } finally {
      app.unmount()
    }
  })

  it('does not mark user messages as dangerous when no detector is provided', () => {
    const { app, root } = mountList({
      messages: [{ id: 'user-plain', role: 'user', content: 'ordinary message' }],
    })

    try {
      const bubble = findNode(root, (node) => hasClass(node, 'bubble'))
      expect(hasClass(bubble, 'bubble-danger')).toBe(false)
    } finally {
      app.unmount()
    }
  })

  it('shows the crisis banner and anchors thinking details to the matching message', () => {
    const { app, root } = mountList({
      messages: [
        { id: 'user-1', role: 'user', content: 'hello' },
        { id: 'ai-anchor', role: 'ai', content: 'reply' },
      ],
      crisisBannerVisible: true,
      isDeepStreaming: true,
      thinkingLogs: ['memory trace', 'trend trace'],
      thinkingAnchorMessageId: 'ai-anchor',
      thinkingPhase: 'trend',
      phaseLabelMap: { trend: '正在纵向洞察' },
    })

    try {
      const banner = findNode(root, (node) => hasClass(node, 'crisis-banner'))
      const panel = findNode(root, (node) => hasClass(node, 'thinking-panel'))
      expect(collectText(banner)).toContain('高危预警')
      expect(collectText(panel)).toContain('正在纵向洞察')
      expect(
        findAllNodes(panel, (node) => hasClass(node, 'thinking-line')).map(collectText),
      ).toEqual(['memory trace', 'trend trace'])
      const ordered = findAllNodes(
        root,
        (node) => hasClass(node, 'message-row') || hasClass(node, 'thinking-panel'),
      )
      expect(ordered.map(classNames)).toEqual([
        'message-row row-user',
        'message-row row-ai',
        'thinking-panel',
      ])
    } finally {
      app.unmount()
    }
  })

  it('shows instant feedback or animated dots only while typing outside deep streaming', () => {
    const feedback = mountList({
      messages: [],
      isTyping: true,
      instantFeedback: '正在准备回复',
      isDeepStreaming: false,
    })

    try {
      expect(collectText(findNode(feedback.root, (node) => hasClass(node, 'typing')))).toContain(
        '正在准备回复',
      )
      expect(findAllNodes(feedback.root, (node) => node.type === 'i')).toHaveLength(0)
    } finally {
      feedback.app.unmount()
    }

    const dots = mountList({ messages: [], isTyping: true, isDeepStreaming: false })
    try {
      expect(findAllNodes(dots.root, (node) => node.type === 'i')).toHaveLength(3)
    } finally {
      dots.app.unmount()
    }

    const streaming = mountList({
      messages: [],
      isTyping: true,
      isDeepStreaming: true,
      instantFeedback: 'hidden while streaming',
    })
    try {
      expect(findNode(streaming.root, (node) => hasClass(node, 'typing'))).toBeNull()
    } finally {
      streaming.app.unmount()
    }
  })

  it('exposes the scroll element and scrolls to the bottom after the next tick', async () => {
    const { app, root } = mountList({ messages: [] })

    try {
      const element = findNode(root, (node) => hasClass(node, 'messages-area'))
      element.scrollTop = 12
      element.scrollHeight = 240
      const exposed = app._instance.exposed
      expect(exposed.scrollElement.value.scrollTop).toBe(12)
      expect(exposed.scrollElement.value.scrollHeight).toBe(240)

      const pendingScroll = exposed.scrollToBottom()
      expect(element.scrollTop).toBe(12)
      await pendingScroll
      await nextTick()
      expect(element.scrollTop).toBe(240)
    } finally {
      app.unmount()
    }
  })
})
