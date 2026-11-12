import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/:pathMatch(.*)*', name: 'NotFound', component: () => import('../views/NotFound.vue') },
  {
    path: '/',
    redirect: '/login',
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('../views/Register.vue'),
  },
  {
    path: '/article/:id',
    name: 'ArticleDetail',
    component: () => import('../views/ArticleDetail.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/student',
    name: 'StudentLayout',
    component: () => import('../views/student/Layout.vue'),
    redirect: '/student/dashboard',
    meta: { requiresAuth: true, role: 'student' },
    children: [
      {
        path: 'dashboard',
        name: 'StudentDashboard',
        component: () => import('../views/student/Dashboard.vue'),
      },
      {
        path: 'appointments',
        name: 'StudentAppointments',
        component: () => import('../views/student/Appointments.vue'),
      },
      {
        path: 'test',
        name: 'StudentTest',
        component: () => import('../views/student/Test.vue'),
      },
      {
        path: 'report',
        name: 'StudentReport',
        component: () => import('../views/student/Report.vue'),
      },
      {
        path: 'advanced-chat',
        name: 'AdvancedAiChat',
        component: () => import('../views/student/AdvancedAiChat.vue'),
      },
      {
        path: 'articles',
        name: 'StudentArticles',
        component: () => import('../views/student/Articles.vue'),
      },
      {
        path: 'treehole',
        name: 'StudentTreehole',
        component: () => import('../views/student/Treehole.vue'),
      },
      {
        path: 'questions',
        name: 'StudentQuestions',
        component: () => import('../views/student/Questions.vue'),
      },
    ],
  },
  {
    path: '/teacher',
    name: 'TeacherLayout',
    component: () => import('../views/teacher/Layout.vue'),
    redirect: '/teacher/advanced-dashboard',
    meta: { requiresAuth: true, role: 'teacher' },
    children: [
      {
        path: 'advanced-dashboard',
        name: 'AdvancedTeacherDashboard',
        component: () => import('../views/teacher/AdvancedDashboard.vue'),
      },
      {
        path: 'support',
        name: 'TeacherSupportWorkspace',
        component: () => import('../views/teacher/SupportWorkspace.vue'),
      },
      {
        path: 'students',
        name: 'StudentManagement',
        component: () => import('../views/teacher/StudentManagement.vue'),
      },
      {
        path: 'appointments',
        name: 'TeacherAppointmentManagement',
        component: () => import('../views/teacher/AppointmentManagement.vue'),
      },
      {
        path: 'content',
        name: 'TeacherContentManagement',
        component: () => import('../views/teacher/ContentManagement.vue'),
      },
      {
        path: 'interventions',
        name: 'TeacherInterventionRecords',
        component: () => import('../views/teacher/InterventionRecords.vue'),
      },
      {
        path: 'student/:id',
        name: 'TeacherStudentDetail',
        component: () => import('../views/teacher/StudentDetail.vue'),
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  const role = localStorage.getItem('role')

  // Verify if role is valid
  const isValidRole = role === 'teacher' || role === 'student'

  if (to.meta.requiresAuth) {
    if (!token || !isValidRole) {
      // If token is missing or role is invalid, clear storage and go to login
      if (!isValidRole && token) {
        localStorage.removeItem('token')
        localStorage.removeItem('role')
        localStorage.removeItem('user')
      }
      next('/login')
    } else if (to.meta.role && to.meta.role !== role) {
      // Role mismatch, redirect to their respective dashboard
      next(role === 'teacher' ? '/teacher' : '/student')
    } else {
      next()
    }
  } else {
    // If going to login/register but already logged in
    if ((to.path === '/login' || to.path === '/register') && token && isValidRole) {
      next(role === 'teacher' ? '/teacher' : '/student')
    } else {
      next()
    }
  }
})

// Every route is a dynamic import, so a chunk that fails to download (a deploy
// that replaced the old files, a flaky network) leaves router-view with nothing
// to render and the user with a blank page. Retry once, then send them to a
// page that says what happened instead of showing white.
router.onError((error, to) => {
  const message = String(error?.message || error)
  const isChunk =
    /Failed to fetch dynamically imported module|Importing a module script failed|Loading chunk .* failed/i.test(
      message,
    )
  if (!isChunk) return
  const target = to?.fullPath || window.location.pathname
  const attempt = Number(sessionStorage.getItem('router-chunk-retry') || 0)
  if (attempt < 1) {
    sessionStorage.setItem('router-chunk-retry', String(attempt + 1))
    window.location.assign(target)
    return
  }
  sessionStorage.removeItem('router-chunk-retry')
  // A plain static page, not a route: the chunks that would render a Vue page
  // are exactly what just failed to load.
  window.location.assign('/chunk-error.html')
})

router.afterEach(() => {
  // A successful navigation proves the chunks load again.
  sessionStorage.removeItem('router-chunk-retry')
})

export default router
