const DIMENSION_KEYS = ['academic', 'interpersonal', 'family', 'emotion', 'physical']
const DIMENSION_ALIASES = {
  academic: 'Academic',
  interpersonal: 'Interpersonal',
  family: 'Family',
  emotion: 'Emotion',
  physical: 'Physical',
}

function readScore(value) {
  if (value === null || value === undefined || value === '') return null
  if (typeof value !== 'number' && typeof value !== 'string') return null
  if (typeof value === 'string' && !value.trim()) return null
  const score = Number(value)
  return Number.isFinite(score) && score >= 0 && score <= 100 ? score : null
}

export function getFiveDimensionResult(payload) {
  const sourceEnvelope = payload?.data
  const status = payload?.data_status
  const source = sourceEnvelope?.five_dimensions
  const provenance = sourceEnvelope?.provenance || source?.provenance
  const provenanceLabel = (
    typeof provenance === 'string'
      ? provenance
      : typeof provenance?.description === 'string'
        ? provenance.description
        : typeof provenance?.source === 'string'
          ? provenance.source
          : ''
  ).trim()

  if (
    !payload ||
    typeof payload !== 'object' ||
    (!Object.hasOwn(payload, 'data') && status !== 'insufficient' && status !== 'empty')
  ) {
    return { status: 'invalid', message: '返回的数据格式不完整，暂不展示。' }
  }

  if (status === 'insufficient' || status === 'empty') {
    const unavailable = payload?.source === 'not_available'
    return {
      status: unavailable ? 'not-integrated' : 'no-records',
      message:
        payload?.message ||
        (unavailable
          ? '五维数据尚未接入；现有记录不能推导这五项独立分数。'
          : '暂无可核验的五维观察记录。'),
    }
  }

  if (!sourceEnvelope || typeof sourceEnvelope !== 'object') {
    return { status: 'invalid', message: '返回的数据格式不完整，暂不展示。' }
  }

  if (!source || !provenanceLabel) {
    return { status: 'invalid', message: '数据缺少完整来源说明，暂不展示。' }
  }

  const dimensions = Object.fromEntries(
    DIMENSION_KEYS.map((key) => [
      key,
      readScore(Object.hasOwn(source, key) ? source[key] : source[DIMENSION_ALIASES[key]]),
    ]),
  )
  const missing = DIMENSION_KEYS.filter((key) => dimensions[key] === null)
  if (missing.length) {
    const labels = {
      academic: '学业',
      interpersonal: '人际',
      family: '家庭',
      emotion: '情绪',
      physical: '身体',
    }
    return {
      status: 'partial',
      message: `数据不完整，暂不绘图。缺少或无效：${missing.map((key) => labels[key]).join('、')}。`,
      missing,
    }
  }

  return { status: 'ready', dimensions, provenance: provenanceLabel }
}

export function getFiveDimensionFailure(error) {
  if (error?.response?.status === 404) {
    return { status: 'not-integrated', message: '五维数据接口尚未接入。' }
  }
  return { status: 'network-error', message: '五维数据加载失败，请重试。' }
}
