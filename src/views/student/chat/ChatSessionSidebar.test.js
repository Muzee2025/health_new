import { afterEach, describe, expect, it, vi } from 'vitest'
import * as Vue from 'vue'
import { createRenderer, nextTick } from 'vue'
import { compileScript, compileTemplate, parse } from '@vue/compiler-sfc'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import ChatSessionSidebar from './ChatSessionSidebar.vue'

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
    ElButton: {
      setup(_props, { attrs, slots }) {
        return () => h('button', attrs, slots.default?.())
      },
    },
    ElInput: {
      inheritAttrs: false,
      props: ['modelValue', 'placeholder'],
      emits: ['update:modelValue'],
      setup(props, { attrs, emit }) {
        return () =>
          h('input', {
            ...attrs,
            value: props.modelValue,
            placeholder: props.placeholder,
            onInput: (event) => emit('update:modelValue', event.target.value),
          })
      },
    },
    ElDropdown: {
      emits: ['command'],
      setup(_props, { slots, emit }) {
        return () =>
          h('div', { class: 'dropdown-stub' }, [
            slots.default?.(),
            h('button', {
              class: 'rename-command',
              onClick: () => emit('command', 'rename'),
            }),
            h('button', {
              class: 'delete-command',
              onClick: () => emit('command', 'delete'),
            }),
          ])
      },
    },
    ElDropdownMenu: {
      setup(_props, { slots }) {
        return () => h('div', slots.default?.())
      },
    },
    ElDropdownItem: {
      setup(_props, { slots }) {
        return () => h('button', slots.default?.())
      },
    },
    vLoading: {
      mounted(element, binding) {
        element.props['data-loading'] = binding.value
      },
      updated(element, binding) {
        element.props['data-loading'] = binding.value
      },
    },
  }
})

const sidebarSource = readFileSync(new URL('./ChatSessionSidebar.vue', import.meta.url), 'utf8')
const sidebarFilename = 'src/views/student/chat/ChatSessionSidebar.vue'
const { descriptor } = parse(sidebarSource, { filename: sidebarFilename })
if (!descriptor.template || !descriptor.scriptSetup)
  throw new Error('ChatSessionSidebar SFC blocks were not found')
const sidebarScript = compileScript(descriptor, { id: 'chat-session-sidebar-test' })
const sidebarTemplate = compileTemplate({
  source: descriptor.template.content,
  filename: sidebarFilename,
  id: 'chat-session-sidebar-test',
  compilerOptions: { bindingMetadata: sidebarScript.bindings, mode: 'function' },
})
if (sidebarTemplate.errors.length) throw sidebarTemplate.errors[0]
ChatSessionSidebar.render = runInNewContext(`(Vue) => { ${sidebarTemplate.code} }`)(Vue)

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

function findAllNodes(node, predicate, result = []) {
  if (predicate(node)) result.push(node)
  for (const child of node.children || []) findAllNodes(child, predicate, result)
  return result
}

function collectText(node) {
  return `${node.text || ''}${(node.children || []).map(collectText).join('')}`
}

function session(id, title, archived = false) {
  return {
    id,
    title,
    archived,
    mode: 'daily',
    updated_at: '2026-11-14T00:00:00.000Z',
  }
}

function mountSidebar(props = {}) {
  const root = { type: 'root', props: {}, children: [], parent: null, text: '' }
  const app = createHostRenderer().createApp(ChatSessionSidebar, props)
  app.component('LibraryIcon', { render: () => null })
  app.mount(root)
  return { app, root }
}

afterEach(() => {
  vi.clearAllMocks()
})

describe('ChatSessionSidebar component contract', () => {
  it('searches case-sensitively while excluding archived sessions', async () => {
    const { app, root } = mountSidebar({
      sessions: [
        session('match', 'Daily support'),
        session('lowercase', 'daily notes'),
        session('archived', 'Daily archived', true),
      ],
    })

    try {
      const names = () =>
        findAllNodes(root, (node) => node.props.class === 'session-name').map(collectText)
      expect(names()).toEqual(['Daily support', 'daily notes'])
      expect(collectText(findNode(root, (node) => node.props.class === 'session-time'))).toBe(
        '11-14',
      )

      const search = findNode(root, (node) => node.type === 'input')
      search.props.onInput({ target: { value: 'Daily' } })
      await nextTick()
      expect(names()).toEqual(['Daily support'])
    } finally {
      app.unmount()
    }
  })

  it('marks the active session and exposes its aria-current state', () => {
    const { app, root } = mountSidebar({
      sessions: [session('first', 'First'), session('second', 'Second')],
      currentSessionId: 'second',
    })

    try {
      const items = findAllNodes(root, (node) => String(node.props.class).includes('session-item'))
      expect(items[0].props.class).not.toContain('active')
      expect(items[0].props['aria-current']).toBeUndefined()
      expect(items[1].props.class).toContain('active')
      expect(items[1].props['aria-current']).toBe('true')
    } finally {
      app.unmount()
    }
  })

  it('selects sessions by click, Enter, and Space', () => {
    const onSelect = vi.fn()
    const target = session('session-42', 'A session')
    const { app, root } = mountSidebar({ sessions: [target], onSelect })

    try {
      const item = findNode(root, (node) => String(node.props.class).includes('session-item'))
      item.props.onClick()
      expect(onSelect).toHaveBeenLastCalledWith('session-42')

      const enter = { key: 'Enter', stopPropagation: vi.fn(), preventDefault: vi.fn() }
      item.props.onKeydown[0](enter)
      expect(enter.stopPropagation).toHaveBeenCalledOnce()
      expect(enter.preventDefault).toHaveBeenCalledOnce()
      expect(onSelect).toHaveBeenLastCalledWith('session-42')

      const space = { key: ' ', stopPropagation: vi.fn(), preventDefault: vi.fn() }
      item.props.onKeydown[1](space)
      expect(space.stopPropagation).toHaveBeenCalledOnce()
      expect(space.preventDefault).toHaveBeenCalledOnce()
      expect(onSelect).toHaveBeenCalledTimes(3)
    } finally {
      app.unmount()
    }
  })

  it('creates using the current mode and emits rename/delete with the session', () => {
    const onCreate = vi.fn()
    const onRename = vi.fn()
    const onDelete = vi.fn()
    const target = session('session-7', 'Rename me')
    const { app, root } = mountSidebar({
      sessions: [target],
      currentMode: 'counseling',
      onCreate,
      onRename,
      onDelete,
    })

    try {
      findNode(root, (node) => node.props.class === 'new-conv-btn').props.onClick()
      expect(onCreate).toHaveBeenCalledWith('counseling')

      findNode(root, (node) => node.props.class === 'rename-command').props.onClick()
      expect(onRename).toHaveBeenCalledWith(target)

      findNode(root, (node) => node.props.class === 'delete-command').props.onClick()
      expect(onDelete).toHaveBeenCalledWith(target)
    } finally {
      app.unmount()
    }
  })

  it('forwards the loading state to the session list directive', () => {
    const { app, root } = mountSidebar({ loadingSessions: true })

    try {
      expect(
        findNode(root, (node) => node.props.class === 'session-list')?.props['data-loading'],
      ).toBe(true)
    } finally {
      app.unmount()
    }
  })
})
