// stores/auth.js — 含角色 (role) 状态
import { defineStore } from 'pinia'
import { login as apiLogin, logout as apiLogout, register as apiRegister } from '@/api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    username: localStorage.getItem('username') || null,
    role:     parseInt(localStorage.getItem('role') || '0'),  // 0=普通用户 1=管理员
  }),
  getters: {
    isLoggedIn: (s) => !!s.username,
    isAdmin:    (s) => s.role === 1,
  },
  actions: {
    async login(username, password) {
      const res = await apiLogin(username, password)
      if (res.data.status === 'success') {
        this.username = res.data.username
        this.role     = res.data.role ?? 0
        localStorage.setItem('username', res.data.username)
        localStorage.setItem('role',     String(res.data.role ?? 0))
        return { success: true }
      }
      return { success: false, msg: res.data.msg }
    },
    async register(username, password) {
      const res = await apiRegister(username, password)
      return { success: res.data.status === 'success', msg: res.data.msg }
    },
    async logout() {
      await apiLogout()
      this.username = null
      this.role     = 0
      localStorage.removeItem('username')
      localStorage.removeItem('role')
    }
  }
})
