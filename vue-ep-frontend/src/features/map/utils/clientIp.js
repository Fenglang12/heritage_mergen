/**
 * 本地开发：浏览器查询公网 IP，经 X-Client-Public-IP 传给后端。
 * 开 VPN 后需点地图页「刷新」或重新进入页面以更新 IP。
 */

let cachedIp = null
let cachedAt = 0
const TTL_MS = 60 * 1000

async function fetchFrom(url) {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), 5000)
  try {
    const res = await fetch(url, { signal: ctrl.signal })
    if (!res.ok) return null
    return await res.json()
  } finally {
    clearTimeout(timer)
  }
}

function isValidIp(ip) {
  if (!ip || typeof ip !== 'string') return false
  return /^\d{1,3}(\.\d{1,3}){3}$/.test(ip) || /^[0-9a-f:]+$/i.test(ip)
}

export async function ensureClientPublicIp(force = false) {
  if (!force && cachedIp && Date.now() - cachedAt < TTL_MS) {
    return cachedIp
  }

  const providers = [
  // ipinfo 常能反映 VPN 出口国家
    async () => {
      const d = await fetchFrom('https://ipinfo.io/json')
      if (d?.ip && isValidIp(d.ip)) {
        if (import.meta.env.DEV) {
          console.info('[IP定位] ipinfo', d.ip, d.country, d.city)
        }
        return d.ip
      }
      return null
    },
    async () => {
      const d = await fetchFrom('https://api.ipify.org?format=json')
      if (d?.ip && isValidIp(d.ip)) {
        if (import.meta.env.DEV) console.info('[IP定位] ipify', d.ip)
        return d.ip
      }
      return null
    },
    async () => {
      const d = await fetchFrom('https://api64.ipify.org?format=json')
      if (d?.ip && isValidIp(d.ip)) {
        if (import.meta.env.DEV) console.info('[IP定位] ipify64', d.ip)
        return d.ip
      }
      return null
    },
  ]

  for (const getIp of providers) {
    try {
      const ip = await getIp()
      if (ip) {
        cachedIp = ip
        cachedAt = Date.now()
        return ip
      }
    } catch (e) {
      if (import.meta.env.DEV) console.warn('[IP定位] 查询失败', e.message)
    }
  }

  if (import.meta.env.DEV && !cachedIp) {
    console.warn('[IP定位] 无法获取公网 IP，后端将改用服务器出口 IP 或兜底城市')
  }
  return cachedIp
}

export function clearClientPublicIpCache() {
  cachedIp = null
  cachedAt = 0
}
