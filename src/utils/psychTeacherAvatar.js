import teacherAvatar1 from '../assets/avatars/teachers/psych-teacher-1.png'
import teacherAvatar2 from '../assets/avatars/teachers/psych-teacher-2.png'
import teacherAvatar3 from '../assets/avatars/teachers/psych-teacher-3.png'

export const PSYCH_TEACHER_AVATAR_ALT = '心理教师卡通形象'

export const PSYCH_TEACHER_AVATAR_LIST = [teacherAvatar1, teacherAvatar2, teacherAvatar3]

export const PSYCH_TEACHER_AVATAR_SOURCES = {
  default: teacherAvatar1,
  list: PSYCH_TEACHER_AVATAR_LIST,
  byTeacherName: {
    王芳: teacherAvatar2,
    刘洋: teacherAvatar3,
    周敏: teacherAvatar1,
  },
}

export const PSYCH_TEACHER_AVATAR_SRCSET = `${teacherAvatar1} 1x, ${teacherAvatar2} 2x, ${teacherAvatar3} 3x`

const toSeedString = (seed) => String(seed ?? '')

const hashSeed = (seed) => {
  const text = toSeedString(seed)
  if (!text) return 0
  let hash = 0
  for (let i = 0; i < text.length; i += 1) {
    hash = (hash * 31 + text.charCodeAt(i)) >>> 0
  }
  return hash
}

export const getPsychTeacherAvatar = (seed = '', teacherName = '') => {
  const normalizedName = String(teacherName || '').trim()
  if (normalizedName && PSYCH_TEACHER_AVATAR_SOURCES.byTeacherName[normalizedName]) {
    return PSYCH_TEACHER_AVATAR_SOURCES.byTeacherName[normalizedName]
  }
  if (!PSYCH_TEACHER_AVATAR_LIST.length) return PSYCH_TEACHER_AVATAR_SOURCES.default
  const idx = hashSeed(seed) % PSYCH_TEACHER_AVATAR_LIST.length
  return PSYCH_TEACHER_AVATAR_LIST[idx]
}
