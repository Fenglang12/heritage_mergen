import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/features/auth/auth'

/** 登录/注册表单逻辑 */
export function useAuthForm(options = {}) {
  const { onSuccess, onFail } = options
  const router = useRouter()
  const auth = useAuthStore()

  const mode = ref('login')
  const loading = ref(false)
  const errorMsg = ref('')
  const successMsg = ref('')

  const username = ref('')
  const password = ref('')
  const regUsername = ref('')
  const regPassword = ref('')
  const rememberMe = ref(false)

  async function doLogin() {
    errorMsg.value = ''
    successMsg.value = ''
    if (!username.value.trim() || !password.value.trim()) {
      errorMsg.value = '账号和密码不能为空'
      return
    }
    loading.value = true
    try {
      const r = await auth.login(username.value.trim(), password.value.trim())
      if (r.success) {
        onSuccess?.('login')
        setTimeout(() => router.push('/'), options.successDelay ?? 800)
      } else {
        errorMsg.value = r.msg
        onFail?.('login')
      }
    } catch {
      errorMsg.value = '网络异常，请重试'
      onFail?.('login')
    } finally {
      loading.value = false
    }
  }

  async function doRegister() {
    errorMsg.value = ''
    successMsg.value = ''
    if (!regUsername.value.trim() || !regPassword.value.trim()) {
      errorMsg.value = '请填写完整信息'
      return
    }
    if (regPassword.value.length < 6) {
      errorMsg.value = '密码至少需要6位'
      return
    }
    loading.value = true
    try {
      const r = await auth.register(regUsername.value.trim(), regPassword.value.trim())
      if (r.success) {
        onSuccess?.('register')
        successMsg.value = '注册成功！请登录'
        username.value = regUsername.value
        regUsername.value = ''
        regPassword.value = ''
        setTimeout(() => {
          mode.value = 'login'
          successMsg.value = ''
        }, 1500)
      } else {
        errorMsg.value = r.msg
        onFail?.('register')
      }
    } catch {
      errorMsg.value = '网络异常，请重试'
      onFail?.('register')
    } finally {
      loading.value = false
    }
  }

  return {
    mode,
    loading,
    errorMsg,
    successMsg,
    username,
    password,
    regUsername,
    regPassword,
    rememberMe,
    doLogin,
    doRegister,
  }
}
