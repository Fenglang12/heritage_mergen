/**
 * 仅使用浏览器原生精确位置 navigator.geolocation。
 * 高德 Geolocation / IP 等其它方式已注释停用。
 */

function gpsErrorMessage(err) {
  if (!err) return '定位失败'
  if (err.code === 1) return '定位权限被拒绝，请点击地址栏锁图标允许「位置」后重试'
  if (err.code === 2) return '无法获取位置（设备定位关闭或信号弱）'
  if (err.code === 3) return '定位超时，请到窗边/室外后重试'
  if (typeof err === 'string') return err
  if (err.message) return err.message
  return '定位失败'
}

function withTimeout(promise, ms, label) {
  return new Promise((resolve) => {
    const timer = setTimeout(
      () => resolve({ coords: null, error: `${label}超时（${ms}ms）` }),
      ms + 500,
    )
    promise.then((r) => {
      clearTimeout(timer)
      resolve(r)
    })
  })
}

function fromNativeGeolocation(timeoutMs, maximumAge) {
  return new Promise((resolve) => {
    if (!navigator.geolocation) {
      resolve({ coords: null, error: '当前浏览器不支持定位' })
      return
    }
    if (!window.isSecureContext) {
      resolve({
        coords: null,
        error: '当前页面非安全上下文（需 localhost 或 HTTPS）才能使用 GPS',
      })
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        resolve({
          coords: {
            lng: parseFloat(pos.coords.longitude.toFixed(6)),
            lat: parseFloat(pos.coords.latitude.toFixed(6)),
            accuracy: pos.coords.accuracy,
            source: 'browser-gps',
          },
          error: null,
        })
      },
      (err) => resolve({ coords: null, error: gpsErrorMessage(err) }),
      { enableHighAccuracy: true, timeout: timeoutMs, maximumAge },
    )
  })
}

// # 已注释：高德 Geolocation 兜底
// function fromAmapGeolocation(timeoutMs) { ... }

/**
 * @param {{ timeoutMs?: number, maximumAge?: number }} [opts]
 * @returns {Promise<{ coords: object | null, error: string | null }>}
 */
export async function getBrowserPreciseLocation(opts = {}) {
  const timeoutMs = opts.timeoutMs ?? 15000
  const maximumAge = opts.maximumAge ?? 0

  const native = await withTimeout(
    fromNativeGeolocation(timeoutMs, maximumAge),
    timeoutMs,
    '浏览器GPS',
  )
  if (native.coords) {
    console.info('[精确位置] browser-gps', native.coords)
    return native
  }
  console.warn('[精确位置] 浏览器GPS失败:', native.error)
  return { coords: null, error: native.error || '无法获取精确位置' }
}
