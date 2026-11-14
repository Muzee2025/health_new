import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useDeepThinkSettings } from './useDeepThinkSettings'

function createLocalStorage(initial = {}) {
  const values = new Map(Object.entries(initial))
  return {
    getItem: vi.fn((key) => values.get(key) ?? null),
    setItem: vi.fn((key, value) => values.set(key, String(value))),
    values,
  }
}

function createHarness(storage = createLocalStorage()) {
  const chatSession = { isActive: vi.fn(() => true) }
  const ElMessage = { success: vi.fn(), error: vi.fn() }
  const ElMessageBox = { alert: vi.fn() }
  const settings = useDeepThinkSettings({ chatSession, ElMessage, ElMessageBox, storage })
  return { settings, storage, chatSession, ElMessage, ElMessageBox }
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('useDeepThinkSettings persistence contract', () => {
  it('loads the saved preference and normal-reply statistics', () => {
    const context = createHarness(
      createLocalStorage({
        advanced_ai_deep_think_enabled: '1',
        advanced_ai_normal_reply_avg_chars: '128',
        advanced_ai_normal_reply_count: '4',
      }),
    )

    context.settings.loadSettings()

    expect(context.settings.deepThinkEnabled.value).toBe(true)
    expect(context.settings.normalReplyAvgChars.value).toBe(128)
    expect(context.settings.normalReplyCount.value).toBe(4)
  })

  it('resets unreadable settings for an active session and asks an inactive mount to stop', () => {
    const storage = createLocalStorage()
    storage.getItem.mockImplementation(() => {
      throw new Error('storage unavailable')
    })
    const context = createHarness(storage)

    expect(context.settings.loadSettings()).toBe(true)
    expect(context.settings.deepThinkEnabled.value).toBe(false)
    expect(context.settings.normalReplyAvgChars.value).toBe(0)
    expect(context.settings.normalReplyCount.value).toBe(0)

    context.chatSession.isActive.mockReturnValue(false)
    expect(context.settings.loadSettings()).toBe(false)
  })

  it('persists toggles, shows the welcome message once, and reports success', () => {
    const context = createHarness()

    context.settings.toggleDeepThink()
    context.settings.toggleDeepThink()
    context.settings.toggleDeepThink()

    expect(context.settings.deepThinkEnabled.value).toBe(true)
    expect(context.storage.values.get('advanced_ai_deep_think_enabled')).toBe('1')
    expect(context.storage.values.get('advanced_ai_deep_think_welcome_shown')).toBe('1')
    expect(context.ElMessageBox.alert).toHaveBeenCalledOnce()
    expect(context.ElMessage.success).toHaveBeenCalledTimes(3)
  })

  it('keeps the prior preference and reports an error when storage rejects a toggle', () => {
    const storage = createLocalStorage()
    storage.setItem.mockImplementation(() => {
      throw new Error('storage unavailable')
    })
    const context = createHarness(storage)

    context.settings.toggleDeepThink()

    expect(context.settings.deepThinkEnabled.value).toBe(false)
    expect(context.ElMessage.error).toHaveBeenCalledWith(
      '无法保存深度思考设置，请检查浏览器存储权限',
    )
    expect(context.ElMessage.success).not.toHaveBeenCalled()
  })

  it('persists updated normal-reply statistics without coupling send flow to storage', () => {
    const context = createHarness()
    context.settings.normalReplyAvgChars.value = 96
    context.settings.normalReplyCount.value = 2

    context.settings.persistNormalReplyStats()

    expect(context.storage.setItem).toHaveBeenNthCalledWith(
      1,
      'advanced_ai_normal_reply_avg_chars',
      '96',
    )
    expect(context.storage.setItem).toHaveBeenNthCalledWith(
      2,
      'advanced_ai_normal_reply_count',
      '2',
    )
  })
})
