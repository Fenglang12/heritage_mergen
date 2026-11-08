<template>
  <div class="page-map">
    <!-- 左侧信息面板 -->
    <div class="map-panel">
      <div class="panel-header">
        <el-icon class="panel-icon"><Location /></el-icon>
        <div>
          <h2 class="panel-title">周边非遗地图</h2>
          <p class="panel-sub">仅浏览器精确位置（已关闭 IP 定位）</p>
        </div>
      </div>

      <!-- 对话 / 识图跳转提示（深色主题） -->
      <Transition name="jump-hint">
        <div
          v-if="fromSource"
          class="jump-hint"
          :class="{ 'jump-hint--agent': fromAgent }"
        >
          <div class="jump-hint__accent" aria-hidden="true" />
          <div class="jump-hint__inner">
            <el-icon class="jump-hint__icon" aria-hidden="true">
              <ChatDotRound v-if="fromAgent" />
              <Camera v-else />
            </el-icon>
            <div class="jump-hint__body">
              <p class="jump-hint__title">{{ pendingAlertTitle }}</p>
              <p class="jump-hint__desc">地图已标注相关位置，点击列表或地图标点查看详情</p>
            </div>
            <button
              type="button"
              class="jump-hint__close"
              aria-label="关闭提示"
              @click="fromSource = false"
            >×</button>
          </div>
        </div>
      </Transition>

      <!-- 当前城市卡 -->
      <el-card class="info-card" shadow="never" :class="{ 'info-card--locating': loading && !city }">
        <div class="city-row" :class="{ 'city-row--locating': loading && !city }">
          <el-icon class="city-icon"><Position /></el-icon>
          <div class="city-text">
            <p class="city-label">当前定位 · {{ locModeLabel }}</p>
            <p class="city-name">
              <template v-if="city">{{ city }}</template>
              <span v-else class="city-name-pending">
                {{ locHint || '正在请求浏览器定位' }}<span class="city-dots"><i /><i /><i /></span>
              </span>
            </p>
            <p v-if="locHint && city" class="city-hint">{{ locHint }}</p>
          </div>
          <el-button size="small" :loading="loading" @click="reloadDefault" circle>
            <el-icon><Refresh /></el-icon>
          </el-button>
        </div>
      </el-card>

      <!-- 无 GPS 时必须点按钮授权（唯一定位入口） -->
      <div v-if="showGpsCta" class="gps-cta">
        <p class="gps-cta__title">需要浏览器精确位置</p>
        <p class="gps-cta__desc">{{ locHint || '已关闭网络 IP 定位。请点击下方按钮并允许定位权限。' }}</p>
        <el-button type="primary" :loading="loading" @click="requestPreciseGps">
          授权并获取精确位置
        </el-button>
      </div>

      <!-- AI 介绍 -->
      <div class="ai-block" v-if="aiText">
        <div class="ai-header">
          <span class="ai-avatar" aria-hidden="true">遗</span>
          <span class="ai-name">非遗星火向导</span>
        </div>
        <p class="ai-content">{{ aiText }}</p>
      </div>
      <HeritageLoadingPanel v-else-if="loading" variant="map-ip" />

      <!-- 地标列表 -->
      <div class="marker-list" v-if="markers.length">
        <div class="list-title-row">
          <p class="list-title">
            <el-icon><MapLocation /></el-icon>
            {{ listTitle }}
          </p>
          <el-button
            size="small"
            type="success"
            @click="openTourPlanner"
            class="tour-btn"
          >
            规划全程
          </el-button>
        </div>
        <div
          v-for="m in markers"
          :key="m.id"
          class="marker-item"
          :class="{ highlighted: m.id === highlightedId }"
          @click="focusMarker(m)"
        >
          <div class="marker-dot" :class="{ pulse: m.id === highlightedId }"></div>
          <div class="marker-text">
            <span class="marker-name">{{ m.base_name }}</span>
            <span v-if="formatMarkerDistance(m)" class="marker-dist">{{ formatMarkerDistance(m) }}</span>
          </div>
          <el-tag
            v-if="selectedDest && selectedDest.id === m.id"
            size="small"
            type="success"
            class="dest-tag"
          >终点</el-tag>
          <el-tag
            v-if="tourStopIds.includes(m.id)"
            size="small"
            type="warning"
            class="dest-tag"
          >途经</el-tag>
        </div>
      </div>

      <!-- ── 全程路线规划面板 ── -->
      <div class="route-section tour-section" v-if="tourMode">
        <div class="route-section-header">
          <el-icon class="route-icon"><MapLocation /></el-icon>
          <span class="route-title">全程路线规划</span>
          <el-button size="small" text type="info" @click="cancelTour" class="cancel-dest-btn">取消</el-button>
        </div>

        <!-- 起点获取 -->
        <div class="origin-block">
          <div class="origin-block-title">
            <span class="ep-dot ep-dot-origin"></span>
            <span class="ep-label">我的起点</span>
          </div>
          <div class="coord-row">
            <el-input v-model.number="originLng" placeholder="经度" size="small" style="width:100px" />
            <span class="coord-sep">，</span>
            <el-input v-model.number="originLat" placeholder="纬度" size="small" style="width:100px" />
            <el-button size="small" :loading="locating" @click="useCurrentLocation" class="locate-btn">
              <el-icon><Aim /></el-icon>
              {{ locating ? '定位中…' : '获取位置' }}
            </el-button>
          </div>
          <div class="coord-tip" v-if="originLng && originLat">{{ originLabel }}</div>
          <div class="coord-tip warn" v-else>请先点击"获取位置"或手动填写经纬度</div>
        </div>

        <!-- 途经地点排序 -->
        <div class="tour-stops-block">
          <div class="tour-stops-title">
            <span>途经地点顺序</span>
            <span class="tour-stops-hint">可调整顺序</span>
          </div>
          <div class="tour-stop-list">
            <div
              v-for="(element, index) in tourStops"
              :key="element.id"
              class="tour-stop-item"
            >
              <div class="stop-move-btns">
                <button class="move-btn" :disabled="index === 0" @click="moveTourStop(index, -1)">▲</button>
                <button class="move-btn" :disabled="index === tourStops.length - 1" @click="moveTourStop(index, 1)">▼</button>
              </div>
              <span class="stop-num">{{ index + 1 }}</span>
              <span class="stop-name">{{ element.base_name }}</span>
              <el-button
                size="small" text type="danger"
                @click="removeTourStop(element.id)"
                class="remove-stop-btn"
              >✕</el-button>
            </div>
          </div>
          <div class="tour-stop-empty" v-if="!tourStops.length">暂无地点</div>
        </div>

        <!-- 交通方式（仅驾车/步行/骑行，公交不支持多途径） -->
        <div class="travel-mode-tabs">
          <div
            v-for="mode in tourModes"
            :key="mode.key"
            class="mode-tab"
            :class="{ active: tourMode === mode.key }"
            @click="tourMode = mode.key"
          >
            <el-icon class="mode-tab-icon"><component :is="mode.icon" /></el-icon>
            <span class="mode-tab-label">{{ mode.label }}</span>
          </div>
        </div>

        <el-button
          type="primary"
          size="default"
          :loading="tourLoading"
          :disabled="!originLng || !originLat || tourStops.length < 1"
          @click="planTourRoute"
          class="plan-btn"
          block
        >
          {{ tourLoading ? '规划中…' : `规划 ${tourStops.length} 处全程路线` }}
        </el-button>

        <!-- 全程路线结果 -->
        <div v-if="tourResult" class="route-result">
          <div class="route-summary-bar">
            <div class="summary-stat">
              <span class="stat-label">时长</span>
              <span class="stat-val">{{ formatDuration(tourResult.duration) }}</span>
            </div>
            <div class="summary-divider"></div>
            <div class="summary-stat">
              <span class="stat-label">距离</span>
              <span class="stat-val">{{ formatDistance(tourResult.distance) }}</span>
            </div>
            <div class="summary-divider"></div>
            <div class="summary-stat">
              <span class="stat-label">站数</span>
              <span class="stat-val">{{ tourStops.length }}</span>
            </div>
          </div>

          <!-- 分段详细步骤 -->
          <div
            v-for="(seg, si) in tourResult.segments"
            :key="si"
            class="tour-segment"
          >
            <!-- 段标题：A → B + 本段耗时距离 -->
            <div class="tour-seg-header">
              <span class="seg-label">
                <span class="seg-badge">{{ si + 1 }}</span>
                {{ seg.fromLabel }} → {{ seg.toLabel }}
              </span>
              <span class="seg-meta">{{ formatDuration(seg.duration) }} · {{ formatDistance(seg.distance) }}</span>
            </div>
            <!-- 本段导航步骤 -->
            <div class="route-steps" v-if="seg.steps && seg.steps.length">
              <div
                v-for="(step, idx) in seg.steps"
                :key="idx"
                class="step-item"
              >
                <div class="step-num">{{ idx + 1 }}</div>
                <div class="step-info">
                  <div class="step-instruction">{{ step.instruction }}</div>
                  <div class="step-meta" v-if="step.road_name || step.step_distance">
                    <span v-if="step.road_name">{{ step.road_name }}</span>
                    <span v-if="step.step_distance"> · {{ formatDistance(+step.step_distance) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <el-button size="small" text class="clear-route-btn" @click="clearTourRoute">
            <el-icon><Delete /></el-icon> 清除路线
          </el-button>
        </div>
      </div>

      <!-- ── 路线规划面板（选中终点后显示） ── -->
      <div class="route-section" v-if="selectedDest">
        <div class="route-section-header">
          <el-icon class="route-icon"><Guide /></el-icon>
          <span class="route-title">路线规划</span>
          <el-button
            size="small" text type="info"
            @click="cancelDest"
            class="cancel-dest-btn"
          >取消</el-button>
        </div>

        <!-- 起点：手动获取位置（与打卡广场一致） -->
        <div class="origin-block">
          <div class="origin-block-title">
            <span class="ep-dot ep-dot-origin"></span>
            <span class="ep-label">我的起点</span>
          </div>
          <div class="coord-row">
            <el-input
              v-model.number="originLng"
              placeholder="经度"
              size="small"
              style="width:100px"
            />
            <span class="coord-sep">，</span>
            <el-input
              v-model.number="originLat"
              placeholder="纬度"
              size="small"
              style="width:100px"
            />
            <el-button
              size="small"
              :loading="locating"
              @click="useCurrentLocation"
              class="locate-btn"
            >
              <el-icon><Aim /></el-icon>
              {{ locating ? '定位中…' : '获取位置' }}
            </el-button>
          </div>
          <div class="coord-tip" v-if="originLng && originLat">
            {{ originLabel }}
          </div>
          <div class="coord-tip warn" v-else>
            请先点击"获取位置"或手动填写经纬度
          </div>
        </div>

        <!-- 终点信息 -->
        <div class="endpoint-row dest-row">
          <span class="ep-dot ep-dot-dest"></span>
          <span class="ep-label">终点：</span>
          <span class="ep-value">{{ selectedDest.base_name }}</span>
        </div>

        <!-- 4种交通方式选择 -->
        <div class="travel-mode-tabs">
          <div
            v-for="mode in travelModes"
            :key="mode.key"
            class="mode-tab"
            :class="{ active: activeMode === mode.key }"
            @click="selectMode(mode.key)"
          >
            <el-icon class="mode-tab-icon"><component :is="mode.icon" /></el-icon>
            <span class="mode-tab-label">{{ mode.label }}</span>
          </div>
        </div>

        <!-- 开始规划按钮 -->
        <el-button
          type="primary"
          size="default"
          :loading="routeLoading"
          :disabled="!originLng || !originLat"
          @click="planRoute"
          class="plan-btn"
          block
        >
          {{ routeLoading ? '规划中…' : '开始导航' }}
        </el-button>

        <!-- 路线结果 -->
        <div v-if="routeResult" class="route-result">
          <!-- 路线概要 -->
          <div class="route-summary-bar">
            <div class="summary-stat">
              <span class="stat-icon">⏱</span>
              <span class="stat-val">{{ formatDuration(routeResult.duration) }}</span>
            </div>
            <div class="summary-divider"></div>
            <div class="summary-stat">
              <span class="stat-label">距离</span>
              <span class="stat-val">{{ formatDistance(routeResult.distance) }}</span>
            </div>
            <div class="summary-divider" v-if="routeResult.cost"></div>
            <div class="summary-stat" v-if="routeResult.cost">
              <span class="stat-label">费用</span>
              <span class="stat-val">{{ routeResult.cost }}</span>
            </div>
          </div>

          <!-- 分段导航步骤 -->
          <div class="route-steps" v-if="routeResult.steps && routeResult.steps.length">
            <p class="steps-title">导航步骤</p>
            <div
              v-for="(step, idx) in routeResult.steps"
              :key="idx"
              class="step-item"
            >
              <div class="step-num">{{ idx + 1 }}</div>
              <div class="step-info">
                <div class="step-instruction">{{ step.instruction }}</div>
                <div class="step-meta" v-if="step.road_name || step.step_distance">
                  <span v-if="step.road_name">{{ step.road_name }}</span>
                  <span v-if="step.step_distance"> · {{ formatDistance(+step.step_distance) }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 清除路线 -->
          <el-button size="small" text class="clear-route-btn" @click="clearRoute">
            <el-icon><Delete /></el-icon> 清除路线
          </el-button>
        </div>
      </div>
    </div>

    <!-- 地图主体 -->
    <div class="map-area">
      <div id="amap-container" class="amap-box"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, onBeforeUnmount, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useMapStore } from '@/features/map/stores/mapStore'
import { getDefaultLocal, searchMapMarkers } from '@/api'
import { getBrowserPreciseLocation } from '@/features/map/utils/browserGps'
import HeritageLoadingPanel from '@/features/shared/components/HeritageLoadingPanel.vue'
import {
  Location, Position, Refresh, MapLocation, Delete, Aim,
  ChatDotRound, Camera, Guide, Van, Bicycle, User,
} from '@element-plus/icons-vue'

const route = useRoute()

const mapStore = useMapStore()

const city     = ref('')
const aiText   = ref('')
const markers  = ref([])
const loading  = ref(false)
const fromSource    = ref(false)
const fromAgent     = ref(false)
const highlightedId = ref(null)
/** gps | ip | fixed | pending */
const locSource = ref('')
const locHint = ref('')
const gpsReady = ref(false)
const searchMode = ref('')
const searchRadius = ref(null)
const locModeLabel = computed(() => {
  if (gpsReady.value) return '浏览器精确位置'
  if (loading.value) return '定位中'
  return '等待授权'
})
const showGpsCta = computed(() => !loading.value && !gpsReady.value)
const listTitle = computed(() => {
  const n = markers.value.length
  if (String(searchMode.value || '').startsWith('around')) {
    const km = searchRadius.value ? Math.round(searchRadius.value / 1000) : null
    return km ? `附近约 ${km}km（${n}处）` : `附近地标（${n}处）`
  }
  if (searchMode.value === 'city_fallback') return `同城参考（${n}处）`
  return `已标记地点（${n}处）`
})

function formatMarkerDistance(m) {
  const d = m?.distance_m
  if (d == null || Number.isNaN(+d)) return ''
  const n = +d
  if (n < 1000) return `${Math.round(n)}m`
  return `${(n / 1000).toFixed(n < 10000 ? 1 : 0)}km`
}

const pendingAlertTitle = computed(() => {
  const n = markers.value.length
  if (fromAgent.value) {
    const kw = mapStore.pendingKeyword || route.query.keyword
    return kw
      ? `对话推荐 · 「${kw}」${n} 处标点`
      : `对话推荐 · 已标注 ${n} 处`
  }
  return `识图溯源 · 已标注 ${n} 处`
})

// ── 路线规划状态 ─────────────────────────────────────────────
const selectedDest  = ref(null)
const activeMode    = ref('driving')
const routeLoading  = ref(false)
const routeResult   = ref(null)

// ── 全程路线规划状态 ─────────────────────────────────────────
const tourMode    = ref(false)     // false = 关闭，'driving'|'walking'|'cycling' = 开启+模式
const tourStops   = ref([])        // 可拖拽排序的途经地点列表
const tourLoading = ref(false)
const tourResult  = ref(null)
const tourPolylines = []           // 地图上的全程折线列表

const tourStopIds = computed(() => tourStops.value.map(s => s.id))

const tourModes = [
  { key: 'driving', icon: Van, label: '驾车' },
  { key: 'cycling', icon: Bicycle, label: '骑行' },
  { key: 'walking', icon: User, label: '步行' },
]

// 当前用户位置
const originLng      = ref(null)
const originLat      = ref(null)
const originLabel    = ref('')
const originCitycode = ref('010')
const locating       = ref(false)

const travelModes = [
  { key: 'driving', icon: Van, label: '驾车' },
  { key: 'cycling', icon: Bicycle, label: '骑行' },
  { key: 'walking', icon: User, label: '步行' },
  { key: 'transit', icon: Van, label: '公交' },
]

let map           = null
let infoWindow    = null
let markerObjects = []
let routePolyline = null
let routeMarkers  = []

onMounted(async () => {
  await nextTick()
  if (typeof window.AMap !== 'undefined') {
    initMap()
  } else {
    const key = window.__AMAP_KEY__ || '6093701a8f925e7ac1af1156c7c5c30a'
    await new Promise((resolve) => {
      const script = document.createElement('script')
      script.src = `https://webapi.amap.com/maps?v=2.0&key=${key}&plugin=AMap.Geocoder,AMap.Geolocation`
      script.onload = resolve
      document.head.appendChild(script)
    })
    initMap()
  }
  if (mapStore.hasPendingUpdate) {
    applyPendingMarkers()
  } else if (route.query.keyword) {
    await loadSearchMarkers(
      String(route.query.city || ''),
      String(route.query.keyword || ''),
    )
  } else {
    await loadDefaultData()
  }
})

onBeforeUnmount(() => {})

watch(
  () => mapStore.hasPendingUpdate,
  (val) => { if (val) applyPendingMarkers() }
)

watch(
  () => `${route.query.keyword || ''}|${route.query.city || ''}`,
  async (key, prev) => {
    if (key === prev || !route.query.keyword) return
    if (mapStore.hasPendingUpdate) return
    await loadSearchMarkers(
      String(route.query.city || ''),
      String(route.query.keyword || ''),
    )
  },
)

// ── 手动触发：路线起点用浏览器精确位置 ────────────────────────
async function useCurrentLocation() {
  locating.value = true
  try {
    const { coords, error } = await getBrowserPreciseLocation({ timeoutMs: 12000 })
    if (!coords) {
      ElMessage.warning(error || '无法获取精确位置，请手动输入经纬度')
      return
    }
    originLng.value = coords.lng
    originLat.value = coords.lat
    originLabel.value = `${coords.lng}, ${coords.lat}`

    if (window.AMap) {
      window.AMap.plugin('AMap.Geocoder', () => {
        const geocoder = new window.AMap.Geocoder()
        geocoder.getAddress([coords.lng, coords.lat], (status, result) => {
          if (status === 'complete' && result.regeocode) {
            const addr = result.regeocode.addressComponent
            if (addr?.citycode) originCitycode.value = addr.citycode
            originLabel.value = result.regeocode.formattedAddress || originLabel.value
          }
        })
      })
    }
    ElMessage.success(`定位成功：${coords.lng}, ${coords.lat}`)
  } finally {
    locating.value = false
  }
}

// ── 消费来自识图 / Agent 对话的待渲染标点 ─────────────────────
function applyPendingMarkers() {
  markers.value = mapStore.pendingMarkers
  city.value = mapStore.pendingCity
  const isAgent = mapStore.pendingSource === 'agent'
  fromAgent.value = isAgent
  fromSource.value = true
  const kw = mapStore.pendingKeyword
  if (isAgent && kw) {
    aiText.value = `已在【${mapStore.pendingCity}】标注与「${kw}」相关的 ${markers.value.length} 处地标。`
  } else if (isAgent) {
    aiText.value = `已在【${mapStore.pendingCity}】标注 Agent 检索到的 ${markers.value.length} 处地标。`
  } else {
    aiText.value = `已定位到【${mapStore.pendingCity}】，并标出识图相关地标。`
  }
  mapStore.consumeUpdate()
  centerMapOnMarkers()
  if (map) drawMarkers(true)
}

async function loadSearchMarkers(cityParam, keyword) {
  loading.value = true
  fromAgent.value = true
  fromSource.value = true
  try {
    const res = await searchMapMarkers(cityParam, keyword)
    city.value = res.data.city
    markers.value = res.data.markers || []
    aiText.value = res.data.ai_text || ''
    if (markers.value.length) {
      mapStore.pushMarkersFromAgent(markers.value, city.value, keyword)
      mapStore.consumeUpdate()
    }
    centerMapOnMarkers()
    if (map) drawMarkers(markers.value.length > 0)
  } catch (e) {
    console.error(e)
    ElMessage.error('地标搜索失败，已加载默认地图')
    await loadDefaultData()
  } finally {
    loading.value = false
  }
}

function centerMapOnMarkers() {
  if (!map || !markers.value.length) return
  const first = markers.value.find((m) => m.lng != null && m.lat != null)
  if (!first) return
  map.setCenter([+first.lng, +first.lat])
  map.setZoom(markers.value.length === 1 ? 14 : 12)
}

function applyDefaultLocalResult(data, { recenterAlways = false } = {}) {
  city.value = data.city || ''
  aiText.value = data.ai_text || ''
  markers.value = data.markers || []
  locSource.value = data.loc_source || ''
  searchMode.value = data.search_mode || ''
  searchRadius.value = data.search_radius ?? null
  gpsReady.value = String(data.loc_source || '').startsWith('gps') && !!data.city
  console.info('[地图定位]', {
    city: data.city,
    loc_source: data.loc_source,
    search_mode: data.search_mode,
    search_radius: data.search_radius,
    lng: data.lng,
    lat: data.lat,
  })
  if (gpsReady.value) {
    const nearHint = String(searchMode.value || '').startsWith('around')
      ? ` · 周边 ${searchRadius.value ? Math.round(searchRadius.value / 1000) + 'km' : '检索'}`
      : searchMode.value === 'city_fallback'
        ? ' · 附近无点，已用同城参考'
        : ''
    locHint.value = data.formatted_address
      ? `GPS · ${data.formatted_address}${nearHint}`
      : `GPS · ${data.lng}, ${data.lat}${nearHint}`
    originLng.value = +data.lng
    originLat.value = +data.lat
    if (data.formatted_address) originLabel.value = data.formatted_address
    if (data.citycode) originCitycode.value = data.citycode
  }
  // 周边模式：以 GPS 为中心；同城回退：仍以 GPS 为中心但缩小缩放
  if (map && data.lng != null && data.lat != null && gpsReady.value) {
    map.setCenter([+data.lng, +data.lat])
    const around = String(searchMode.value || '').startsWith('around')
    map.setZoom(around ? (markers.value.length ? 14 : 13) : 12)
  } else if (recenterAlways) {
    centerMapOnMarkers()
  }
  if (map) drawMarkers(false)
}

/** 仅浏览器 GPS：无坐标则不请求后端 */
async function loadByPreciseGps({ timeoutMs = 20000 } = {}) {
  locHint.value = '正在请求浏览器定位权限…'
  locSource.value = ''
  gpsReady.value = false
  city.value = ''
  markers.value = []
  aiText.value = ''

  const { coords, error } = await getBrowserPreciseLocation({
    timeoutMs,
    maximumAge: 0,
  })
  if (!coords) {
    locHint.value = error || '未获得浏览器坐标'
    ElMessage.warning(locHint.value)
    return
  }

  locHint.value = `已获 GPS ${coords.lng}, ${coords.lat}，正在解析城市…`
  mapStore.setLastGps(coords)
  try {
    const res = await getDefaultLocal(false, { lng: coords.lng, lat: coords.lat })
    applyDefaultLocalResult(res.data, { recenterAlways: true })
    mapStore.setLastGps({
      ...coords,
      city: res.data?.city || '',
      citycode: res.data?.citycode || '',
    })
    ElMessage.success(`已精确定位到【${res.data.city}】`)
  } catch (e) {
    const msg = e?.response?.data?.loc_error || e?.response?.data?.ai_text || e?.message || '定位接口失败'
    locHint.value = msg
    gpsReady.value = false
    ElMessage.error(msg)
  }
}

/** 用户点击触发（唯一入口，便于弹出定位授权） */
async function requestPreciseGps() {
  fromSource.value = false
  fromAgent.value = false
  loading.value = true
  try {
    await loadByPreciseGps({ timeoutMs: 20000 })
  } catch (e) {
    console.error(e)
    ElMessage.error('精确定位失败')
  } finally {
    loading.value = false
  }
}

async function loadDefaultData() {
  // # 已注释：进页不再自动走 IP
  // const res = await getDefaultLocal(false, null)
  locHint.value = '请点击下方按钮授权浏览器精确位置'
  gpsReady.value = false
  city.value = ''
  markers.value = []
  aiText.value = ''
  // 进页直接尝试一次 GPS（部分浏览器允许）；失败则显示授权按钮
  loading.value = true
  try {
    await loadByPreciseGps({ timeoutMs: 12000 })
  } finally {
    loading.value = false
  }
}

async function reloadDefault() {
  fromSource.value = false
  fromAgent.value = false
  highlightedId.value = null
  selectedDest.value = null
  clearRoute()
  await requestPreciseGps()
}

// ── 初始化高德地图 ────────────────────────────────────────────
function initMap() {
  if (!window.AMap) return
  map = new AMap.Map('amap-container', {
    viewMode: '3D', pitch: 40, rotation: -10,
    zoom: 5, center: [104.114129, 37.550339],
    layers: [new AMap.TileLayer.Satellite(), new AMap.TileLayer.RoadNet()],
    mapStyle: 'amap://styles/dark'
  })
  const buildings = new AMap.Buildings({ zooms: [16, 20], zIndex: 10, heightFactor: 2 })
  map.add(buildings)
  infoWindow = new AMap.InfoWindow({ isCustom: true, offset: new AMap.Pixel(0, -10) })
}

// ── 绘制地标 ─────────────────────────────────────────────────
function drawMarkers(highlight = false) {
  markerObjects.forEach(({ marker, circle }) => {
    map.remove(marker)
    if (circle) map.remove(circle)
  })
  markerObjects = []
  infoWindow.close()
  highlightedId.value = null

  markers.value.forEach((item, idx) => {
    const pos = [+item.lng, +item.lat]
    const marker = new AMap.Marker({
      position: pos,
      title: item.base_name,
      icon: new AMap.Icon({
        size: new AMap.Size(28, 28),
        image: highlight
          ? 'https://webapi.amap.com/theme/v1.3/markers/n/mark_r.png'
          : 'https://webapi.amap.com/theme/v1.3/markers/n/mark_b.png',
        imageSize: new AMap.Size(28, 28)
      }),
      zIndex: 100 + idx,
      animation: highlight ? 'AMAP_ANIMATION_DROP' : 'AMAP_ANIMATION_NONE'
    })

    let circle = null
    if (highlight) {
      circle = new AMap.Circle({
        center: pos, radius: 800,
        strokeColor: '#3d9e8c', strokeWeight: 2, strokeOpacity: 0.8,
        fillColor: '#3d9e8c', fillOpacity: 0.12, zIndex: 50
      })
      map.add(circle)
    }

    marker.on('click', () => {
      highlightedId.value = item.id
      infoWindow.setContent(buildPopup(item))
      infoWindow.open(map, marker.getPosition())
      setTimeout(() => {
        const closeBtn = document.querySelector('.popup-close-btn')
        const routeBtn = document.querySelector('.popup-route-btn')
        closeBtn?.addEventListener('click', () => infoWindow.close())
        routeBtn?.addEventListener('click', () => {
          infoWindow.close()
          setDestination(item)
        })
      }, 50)
    })

    map.add(marker)
    markerObjects.push({ id: item.id, marker, circle })
  })

  if (markerObjects.length) {
    map.setFitView(markerObjects.map(m => m.marker), false, [60, 60, 60, 60])
    if (highlight) setTimeout(() => map.setZoom(Math.min(map.getZoom() + 1, 14)), 800)
  }
}

// ── 弹窗（含路线规划按钮） ───────────────────────────────────
function escapePopupHtml(text) {
  return String(text ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function popupIntroText(item) {
  const intro = (item.ai_intro || '').trim()
  const name = (item.base_name || '').trim()
  const addr = (item.address || '').trim()
  if (!intro) {
    return addr ? `位于${addr}。` : '本地文化相关地标。'
  }
  if (name && addr && intro === `【${name}】，${addr}。`) {
    return addr ? `位于${addr}。` : '本地文化相关地标。'
  }
  if (name && intro === `【${name}】`) {
    return '本地文化相关地标。'
  }
  return intro
}

function buildPopup(item) {
  const isSelected = selectedDest.value && selectedDest.value.id === item.id
  const name = escapePopupHtml(item.base_name)
  const addr = escapePopupHtml(item.address)
  const intro = escapePopupHtml(popupIntroText(item))
  const typeTag = item.type ? escapePopupHtml(String(item.type).split(';')[0]) : ''
  const addressBlock = addr
    ? `<p class="heritage-card-address">${addr}</p>`
    : ''
  const typeBlock = typeTag ? `<span class="heritage-card-type">${typeTag}</span>` : ''

  return `<div class="heritage-card">
    <button class="popup-close-btn" title="关闭">×</button>
    <div class="heritage-card-header">
      <span class="heritage-card-icon" aria-hidden="true"></span>
      <div class="heritage-card-title-wrap">
        <span class="heritage-card-name">${name}</span>
        ${typeBlock}
      </div>
    </div>
    ${addressBlock}
    <div class="heritage-card-body">${intro}</div>
    <button class="popup-route-btn ${isSelected ? 'selected' : ''}">
      ${isSelected ? '已选为终点' : '规划路线到这里'}
    </button>
  </div>`
}

function focusMarker(m) {
  if (!map) return
  highlightedId.value = m.id
  map.setCenter([+m.lng, +m.lat])
  map.setZoom(14)
  const obj = markerObjects.find(o => o.id === m.id)
  if (obj) {
    infoWindow.setContent(buildPopup(m))
    infoWindow.open(map, obj.marker.getPosition())
    setTimeout(() => {
      const closeBtn = document.querySelector('.popup-close-btn')
      const routeBtn = document.querySelector('.popup-route-btn')
      closeBtn?.addEventListener('click', () => infoWindow.close())
      routeBtn?.addEventListener('click', () => {
        infoWindow.close()
        setDestination(m)
      })
    }, 50)
  }
}

// ── 设置终点 ──────────────────────────────────────────────────
function setDestination(item) {
  selectedDest.value = item
  activeMode.value   = 'driving'
  routeResult.value  = null
  clearRouteOnMap()
  // 滚动到路线规划区域
  setTimeout(() => {
    document.querySelector('.route-section')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, 100)
}

function cancelDest() {
  selectedDest.value = null
  clearRoute()
}

// ================================================================
// 全程路线规划
// ================================================================

function openTourPlanner() {
  // 默认把所有地标按顺序加入途经点
  tourStops.value = [...markers.value]
  tourMode.value  = 'driving'
  tourResult.value = null
  clearTourRouteOnMap()
  // 关闭单点规划
  selectedDest.value = null
  clearRoute()
  setTimeout(() => {
    document.querySelector('.tour-section')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, 100)
}

function cancelTour() {
  tourMode.value   = false
  tourStops.value  = []
  tourResult.value = null
  clearTourRouteOnMap()
}

function removeTourStop(id) {
  tourStops.value = tourStops.value.filter(s => s.id !== id)
}

function moveTourStop(index, dir) {
  const arr    = [...tourStops.value]
  const target = index + dir
  if (target < 0 || target >= arr.length) return
  ;[arr[index], arr[target]] = [arr[target], arr[index]]
  tourStops.value = arr
}

async function planTourRoute() {
  if (!originLng.value || !originLat.value) {
    ElMessage.warning('请先获取起点位置')
    return
  }
  if (tourStops.value.length < 1) {
    ElMessage.warning('请至少选择1个途经地点')
    return
  }

  tourLoading.value = true
  clearTourRouteOnMap()
  tourResult.value  = null

  const stops = tourStops.value
  // 起点 → 第一站 → ... → 最后一站，每段单独请求（高德途经点只支持驾车）
  // 对于步行/骑行分段请求后拼接
  try {
    let totalDuration = 0
    let totalDistance = 0
    const allPolylines = []
    const allSegments  = []

    // 构建分段：[起点, stop0], [stop0, stop1], ..., [stopN-1, stopN]
    const waypoints = [
      { lng: originLng.value, lat: originLat.value, label: '起点', isOrigin: true },
      ...stops.map((s, i) => ({ lng: +s.lng, lat: +s.lat, label: s.base_name, index: i }))
    ]

    for (let i = 0; i < waypoints.length - 1; i++) {
      const from = waypoints[i]
      const to   = waypoints[i + 1]
      const res  = await fetch('/api/direction', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          origin_lng: from.lng,
          origin_lat: from.lat,
          dest_lng:   to.lng,
          dest_lat:   to.lat,
          mode:       tourMode.value,
          citycode:   originCitycode.value,
        })
      }).then(r => r.json())

      if (res.status === 'success') {
        totalDuration += res.duration || 0
        totalDistance += res.distance || 0
        // 收集每段步骤，标注是从哪里到哪里
        allSegments.push({
          fromLabel: from.label,
          toLabel:   to.label,
          duration:  res.duration || 0,
          distance:  res.distance || 0,
          steps:     res.steps   || [],
        })
        if (res.polyline?.length > 1) {
          allPolylines.push({ points: res.polyline, fromLabel: from.label, toLabel: to.label })
        } else {
          allPolylines.push({
            points: [[from.lng, from.lat], [to.lng, to.lat]],
            fromLabel: from.label, toLabel: to.label
          })
        }
      }
    }

    tourResult.value = { duration: totalDuration, distance: totalDistance, segments: allSegments }
    drawTourRouteOnMap(waypoints, allPolylines)
  } catch (e) {
    console.error('全程路线规划失败', e)
    ElMessage.error('网络错误，请稍后重试')
  } finally {
    tourLoading.value = false
  }
}

function drawTourRouteOnMap(waypoints, polylines) {
  if (!map) return
  clearTourRouteOnMap()

  const modeColors = { driving: '#4ECDC4', cycling: '#F39C12', walking: '#27AE60' }
  const color = modeColors[tourMode.value] || '#4ECDC4'

  // 画每段折线
  polylines.forEach(seg => {
    const line = new AMap.Polyline({
      path: seg.points,
      strokeColor: color,
      strokeWeight: 4,
      strokeOpacity: 0.9,
      strokeStyle: tourMode.value === 'walking' ? 'dashed' : 'solid',
      lineJoin: 'round',
      lineCap: 'round',
      showDir: true,
      zIndex: 150
    })
    map.add(line)
    tourPolylines.push(line)
  })

  // 画各站点标记（带编号）
  const numColors = ['#3498DB', '#E74C3C', '#F39C12', '#9B59B6', '#1ABC9C', '#E67E22']
  waypoints.forEach((wp, idx) => {
    const isOrigin = wp.isOrigin
    const num      = isOrigin ? '起' : String(idx)
    const bgColor  = isOrigin ? '#3498DB' : numColors[idx % numColors.length]
    const marker   = new AMap.Marker({
      position:  [wp.lng, wp.lat],
      title:     wp.label,
      content:   `<div class="tour-num-marker" style="background:${bgColor}">${num}</div>`,
      anchor:    'center',
      zIndex:    200 + idx,
      animation: 'AMAP_ANIMATION_DROP'
    })
    map.add(marker)
    tourPolylines.push(marker)  // 复用数组统一清理
  })

  // 自适应视野
  map.setFitView(tourPolylines, false, [60, 60, 60, 340])
}

function clearTourRouteOnMap() {
  tourPolylines.forEach(obj => map?.remove(obj))
  tourPolylines.length = 0
}

function clearTourRoute() {
  clearTourRouteOnMap()
  tourResult.value = null
}

function selectMode(mode) {
  activeMode.value = mode
  // 如果已有结果，切换后自动重新规划
  if (routeResult.value) {
    planRoute()
  }
}

// ================================================================
// 路线规划 - 直接调用高德 Direction API v5
// ================================================================

async function planRoute() {
  if (!selectedDest.value) return
  if (!originLng.value || !originLat.value) {
    ElMessage.warning('无法获取当前位置，请刷新页面重试')
    return
  }

  routeLoading.value = true
  clearRouteOnMap()
  routeResult.value  = null

  try {
    const res = await fetch('/api/direction', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        origin_lng: originLng.value,
        origin_lat: originLat.value,
        dest_lng:   +selectedDest.value.lng,
        dest_lat:   +selectedDest.value.lat,
        mode:       activeMode.value,
        citycode:   originCitycode.value,
      })
    })
    const data = await res.json()

    if (data.status !== 'success') {
      ElMessage.warning(data.msg || '路线规划失败，请尝试其他出行方式')
      return
    }
    routeResult.value = data
    drawRouteOnMap(data, activeMode.value)
  } catch (e) {
    console.error('路线规划失败', e)
    ElMessage.error('网络错误，请稍后重试')
  } finally {
    routeLoading.value = false
  }
}

// ── 在地图上绘制路线 ──────────────────────────────────────────
function drawRouteOnMap(data, mode) {
  if (!map) return
  clearRouteOnMap()

  const modeColors = {
    driving: '#4ECDC4',
    cycling: '#F39C12',
    walking: '#27AE60',
    transit: '#8E44AD',
  }
  const color = modeColors[mode] || '#4ECDC4'

  // 起点标记（蓝色）
  if (originLng.value && originLat.value) {
    const originMarker = new AMap.Marker({
      position: [originLng.value, originLat.value],
      title: '起点',
      icon: new AMap.Icon({
        size: new AMap.Size(32, 32),
        image: 'https://webapi.amap.com/theme/v1.3/markers/n/mark_b.png',
        imageSize: new AMap.Size(32, 32)
      }),
      label: {
        content: `<div class="route-stop-label origin-label">起点</div>`,
        direction: 'top'
      },
      zIndex: 200,
      animation: 'AMAP_ANIMATION_DROP'
    })
    map.add(originMarker)
    routeMarkers.push(originMarker)
  }

  // 终点标记（红色）
  const destMarker = new AMap.Marker({
    position: [+selectedDest.value.lng, +selectedDest.value.lat],
    title: selectedDest.value.base_name,
    icon: new AMap.Icon({
      size: new AMap.Size(32, 32),
      image: 'https://webapi.amap.com/theme/v1.3/markers/n/mark_r.png',
      imageSize: new AMap.Size(32, 32)
    }),
    label: {
      content: `<div class="route-stop-label dest-label">${selectedDest.value.base_name}</div>`,
      direction: 'top'
    },
    zIndex: 201,
    animation: 'AMAP_ANIMATION_DROP'
  })
  map.add(destMarker)
  routeMarkers.push(destMarker)

  // 路线折线
  const polylinePoints = data.polyline?.length > 1
    ? data.polyline
    : [
        [originLng.value, originLat.value],
        [+selectedDest.value.lng, +selectedDest.value.lat]
      ]

  const isDashed = mode === 'walking' || mode === 'transit'
  routePolyline = new AMap.Polyline({
    path: polylinePoints,
    strokeColor: color,
    strokeWeight: mode === 'walking' ? 4 : 5,
    strokeOpacity: 0.92,
    strokeStyle: isDashed ? 'dashed' : 'solid',
    lineJoin: 'round',
    lineCap: 'round',
    showDir: !isDashed,
    zIndex: 150
  })
  map.add(routePolyline)

  // 自适应视野
  const allObjs = [...routeMarkers, routePolyline]
  map.setFitView(allObjs, false, [80, 80, 80, 350])
}

function clearRouteOnMap() {
  if (routePolyline) { map?.remove(routePolyline); routePolyline = null }
  routeMarkers.forEach(m => map?.remove(m))
  routeMarkers = []
  infoWindow?.close()
}

function clearRoute() {
  clearRouteOnMap()
  routeResult.value = null
}

// ── 格式化工具 ────────────────────────────────────────────────
function formatDuration(sec) {
  if (!sec) return '--'
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  if (h > 0) return `${h}小时${m}分钟`
  return `${m}分钟`
}
function formatDistance(meter) {
  if (!meter) return '--'
  return meter >= 1000 ? `${(meter / 1000).toFixed(1)}公里` : `${meter}米`
}
</script>

<style scoped>
.page-map {
  display: flex; height: 100%;
  background: var(--color-bg-base);
}

/* 左侧面板 */
.map-panel {
  width: 300px; flex-shrink: 0;
  background: var(--color-bg-panel);
  border-right: 1px solid var(--color-border);
  display: flex; flex-direction: column; gap: 14px;
  padding: 20px 16px;
  overflow-y: auto;
}

.panel-header { display: flex; align-items: flex-start; gap: 12px; }
.panel-icon { font-size: 22px; color: var(--color-accent-teal); margin-top: 2px; }
.panel-title { font-family: var(--font-serif); font-size: 16px; color: var(--color-text-primary); margin-bottom: 2px; }
.panel-sub { font-size: 11px; color: var(--color-text-muted); }

/* 对话 / 识图跳转提示条 */
.jump-hint {
  position: relative;
  border-radius: var(--radius-md);
  overflow: hidden;
  background: linear-gradient(135deg, rgba(28, 31, 39, 0.98) 0%, rgba(22, 25, 32, 0.98) 100%);
  border: 1px solid var(--color-border);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
}
.jump-hint--agent {
  border-color: rgba(61, 158, 140, 0.35);
  box-shadow: 0 4px 24px rgba(61, 158, 140, 0.08);
}
.jump-hint__accent {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: linear-gradient(180deg, var(--color-accent-gold) 0%, var(--color-accent-teal) 100%);
}
.jump-hint--agent .jump-hint__accent {
  background: linear-gradient(180deg, var(--color-accent-teal) 0%, var(--color-accent-gold-light) 100%);
}
.jump-hint__inner {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 12px 12px 14px;
}
.jump-hint__icon {
  flex-shrink: 0;
  font-size: 18px;
  line-height: 1;
  margin-top: 1px;
  filter: drop-shadow(0 0 6px rgba(201, 168, 76, 0.35));
}
.jump-hint__body {
  flex: 1;
  min-width: 0;
}
.jump-hint__title {
  font-family: var(--font-serif);
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary);
  line-height: 1.45;
  margin-bottom: 4px;
}
.jump-hint--agent .jump-hint__title {
  color: var(--color-accent-gold-light);
}
.jump-hint__desc {
  font-size: 11px;
  color: var(--color-text-muted);
  line-height: 1.5;
}
.jump-hint__close {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--color-text-muted);
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
  transition: color 0.15s, background 0.15s;
  padding: 0;
}
.jump-hint__close:hover {
  color: var(--color-text-primary);
  background: rgba(255, 255, 255, 0.06);
}
.jump-hint-enter-active,
.jump-hint-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.jump-hint-enter-from,
.jump-hint-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

.info-card { background: var(--color-bg-card) !important; border-color: var(--color-border) !important; }
.info-card--locating {
  border-color: rgba(61, 158, 140, 0.35) !important;
  box-shadow: 0 0 0 1px rgba(61, 158, 140, 0.08);
}
:deep(.el-card__body) { padding: 14px !important; }
.city-row { display: flex; align-items: center; gap: 12px; }
.city-row--locating .city-icon {
  animation: city-icon-pulse 1.8s ease-in-out infinite;
}
.city-icon { color: var(--color-accent-teal); font-size: 20px; flex-shrink: 0; }
.city-text { flex: 1; min-width: 0; }
.city-label { font-size: 11px; color: var(--color-text-muted); }
.city-name { font-size: 15px; color: var(--color-text-primary); font-weight: 600; margin-top: 1px; }
.city-hint {
  margin: 4px 0 0;
  font-size: 11px;
  line-height: 1.4;
  color: var(--color-text-muted);
  max-width: 220px;
}
.gps-cta {
  margin: 0 0 12px;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid rgba(212, 168, 83, 0.45);
  background: rgba(212, 168, 83, 0.12);
}
.gps-cta__title {
  margin: 0 0 6px;
  font-size: 13px;
  font-weight: 600;
  color: #e8c57a;
}
.gps-cta__desc {
  margin: 0 0 10px;
  font-size: 12px;
  line-height: 1.45;
  color: var(--color-text-muted);
}
.city-name-pending {
  display: inline-flex;
  align-items: baseline;
  gap: 2px;
  color: var(--color-accent-teal);
  font-weight: 500;
}
.city-dots {
  display: inline-flex;
  gap: 3px;
  margin-left: 2px;
  vertical-align: baseline;
}
.city-dots i {
  display: block;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--color-accent-teal);
  opacity: 0.35;
  animation: city-dot-bounce 1.2s ease-in-out infinite;
}
.city-dots i:nth-child(2) { animation-delay: 0.15s; }
.city-dots i:nth-child(3) { animation-delay: 0.3s; }

@keyframes city-icon-pulse {
  0%, 100% { opacity: 0.7; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.08); }
}
@keyframes city-dot-bounce {
  0%, 80%, 100% { opacity: 0.35; transform: translateY(0); }
  40% { opacity: 1; transform: translateY(-3px); }
}

.ai-block {
  background: rgba(61,158,140,0.06);
  border: 1px solid rgba(61,158,140,0.18);
  border-radius: var(--radius-md);
  padding: 14px;
}
.ai-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.ai-avatar { font-family: var(--font-serif); font-size: 14px; width: 22px; height: 22px; border-radius: 6px; display: inline-flex; align-items: center; justify-content: center; background: linear-gradient(135deg, var(--color-accent-teal), #2a7066); color: #fff; }
.ai-name { font-size: 12px; color: var(--color-accent-teal); font-weight: 600; }
.ai-content { font-size: 13px; color: var(--color-text-secondary); line-height: 1.7; }

/* 地标列表标题行（含全程规划按钮） */
.list-title-row {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 8px;
}
.list-title { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--color-text-muted); margin: 0; }
.tour-btn { font-size: 11px; padding: 4px 8px; }

/* 全程规划途经站点列表 */
.tour-stops-block {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 10px;
  display: flex; flex-direction: column; gap: 6px;
}
.tour-stops-title {
  display: flex; align-items: center; justify-content: space-between;
  font-size: 11px; font-weight: 600; color: var(--color-text-secondary);
}
.tour-stops-hint { color: var(--color-text-muted); font-weight: 400; }
.tour-stop-list { display: flex; flex-direction: column; gap: 4px; }
.tour-stop-item {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 8px;
  background: var(--color-bg-hover);
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border);
}
.stop-move-btns { display: flex; flex-direction: column; gap: 1px; flex-shrink: 0; }
.move-btn {
  width: 16px; height: 14px; border: none; border-radius: 3px;
  background: rgba(255,255,255,0.08); color: var(--color-text-muted);
  font-size: 9px; line-height: 1; cursor: pointer; padding: 0;
  transition: background 0.15s;
}
.move-btn:hover:not(:disabled) { background: rgba(61,158,140,0.3); color: var(--color-accent-teal); }
.move-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.stop-num {
  width: 18px; height: 18px; border-radius: 50%;
  background: var(--color-accent-teal);
  color: #fff; font-size: 10px; font-weight: 600;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.stop-name { flex: 1; font-size: 12px; color: var(--color-text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.remove-stop-btn { padding: 0 2px; flex-shrink: 0; }
.tour-stop-empty { font-size: 12px; color: var(--color-text-muted); text-align: center; padding: 8px 0; }

/* 地图上的站点编号标记 */
.marker-item {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 10px; border-radius: var(--radius-sm);
  font-size: 13px; color: var(--color-text-secondary);
  cursor: pointer; transition: color 0.15s, background-color 0.15s, border-color 0.15s;
}
.marker-item:hover { background: var(--color-bg-hover); color: var(--color-text-primary); }
.marker-item.highlighted {
  background: rgba(61,158,140,0.12);
  color: var(--color-accent-teal);
}
.marker-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.marker-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.marker-dist {
  font-size: 11px;
  color: var(--color-text-muted);
  letter-spacing: 0.2px;
}
.marker-item.highlighted .marker-dist { color: rgba(61,158,140,0.85); }
.marker-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--color-accent-teal); flex-shrink: 0;
  transition: color 0.2s, background-color 0.2s, border-color 0.2s;
}
.marker-dot.pulse {
  background: #c0392b;
  box-shadow: 0 0 0 4px rgba(192,57,43,0.25);
  animation: dot-pulse 1.5s ease-in-out infinite;
}
.dest-tag { margin-left: auto; flex-shrink: 0; }

@keyframes dot-pulse {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.55; }
}

/* ── 路线规划区块 ── */
.route-section {
  border-top: 1px dashed rgba(61,158,140,0.3);
  padding-top: 14px;
  display: flex; flex-direction: column; gap: 10px;
}
.route-section-header {
  display: flex; align-items: center; gap: 7px;
}
.route-icon  { font-size: 15px; }
.route-title { font-size: 12px; font-weight: 600; color: var(--color-accent-teal); letter-spacing: 0.2px; flex: 1; }
.cancel-dest-btn { padding: 0 4px; font-size: 11px; }

/* 起点手动定位块 */
.origin-block {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 10px 12px;
  display: flex; flex-direction: column; gap: 8px;
}
.origin-block-title {
  display: flex; align-items: center; gap: 8px;
}
.coord-row {
  display: flex; align-items: center; gap: 4px; flex-wrap: wrap;
}
.coord-sep { font-size: 12px; color: var(--color-text-muted); }
.locate-btn { flex-shrink: 0; }
.coord-tip {
  font-size: 11px; color: var(--color-accent-teal); line-height: 1.4;
  word-break: break-all;
}
.coord-tip.warn { color: var(--color-text-muted); }

/* 终点行 */
.dest-row {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}
.endpoint-row {
  display: flex; align-items: center; gap: 8px;
  padding: 5px 0;
}
.ep-dot {
  width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0;
}
.ep-dot-origin { background: #3498DB; }
.ep-dot-dest   { background: #C0392B; }
.ep-label { font-size: 11px; color: var(--color-text-muted); flex-shrink: 0; }
.ep-value { font-size: 12px; color: var(--color-text-primary); font-weight: 500;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* 4种交通方式 */
.travel-mode-tabs {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px;
}
.mode-tab {
  display: flex; flex-direction: column; align-items: center; gap: 3px;
  padding: 8px 4px; border-radius: var(--radius-sm);
  border: 1px solid var(--color-border);
  background: var(--color-bg-card);
  cursor: pointer; transition: color 0.18s, background-color 0.18s, border-color 0.18s;
}
.mode-tab:hover {
  border-color: var(--color-accent-teal);
  background: rgba(61,158,140,0.07);
}
.mode-tab.active {
  border-color: var(--color-accent-teal);
  background: rgba(61,158,140,0.15);
  box-shadow: 0 0 0 1px var(--color-accent-teal);
}
.mode-tab-icon  { font-size: 18px; }
.mode-tab-label { font-size: 11px; color: var(--color-text-secondary); }
.mode-tab.active .mode-tab-label { color: var(--color-accent-teal); font-weight: 600; }

/* 规划按钮 */
.plan-btn { width: 100%; }

/* 路线结果 */
.route-result { display: flex; flex-direction: column; gap: 10px; }

.route-summary-bar {
  display: flex; align-items: center; justify-content: center; gap: 10px;
  background: rgba(61,158,140,0.08);
  border: 1px solid rgba(61,158,140,0.22);
  border-radius: var(--radius-md);
  padding: 10px 12px;
}
.summary-stat { display: flex; align-items: center; gap: 5px; }
.stat-icon { font-size: 14px; }
.stat-val { font-size: 13px; font-weight: 600; color: var(--color-text-primary); }
.summary-divider { width: 1px; height: 16px; background: var(--color-border); }

/* 全程规划分段 */
.tour-segment {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
}
.tour-seg-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 7px 10px;
  background: rgba(61,158,140,0.1);
  border-bottom: 1px solid var(--color-border);
  gap: 6px;
}
.seg-label {
  display: flex; align-items: center; gap: 6px;
  font-size: 11px; font-weight: 600; color: var(--color-text-primary);
  flex: 1; overflow: hidden;
}
.seg-badge {
  width: 18px; height: 18px; border-radius: 50%;
  background: var(--color-accent-teal);
  color: #fff; font-size: 10px; font-weight: 600;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.seg-meta { font-size: 10px; color: var(--color-text-muted); flex-shrink: 0; }
.tour-segment .route-steps { padding: 6px 8px; display: flex; flex-direction: column; gap: 4px; }

/* 导航步骤 */
.route-steps { display: flex; flex-direction: column; gap: 5px; }
.steps-title {
  font-size: 11px; color: var(--color-text-muted);
  margin-bottom: 4px; font-weight: 600; letter-spacing: 0.5px;
}
.step-item {
  display: flex; align-items: flex-start; gap: 8px;
  padding: 7px 9px; border-radius: var(--radius-sm);
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
}
.step-num {
  width: 18px; height: 18px; border-radius: 50%;
  background: var(--color-accent-teal);
  color: #fff; font-size: 10px; font-weight: 600;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; margin-top: 1px;
}
.step-info { flex: 1; overflow: hidden; }
.step-instruction { font-size: 12px; color: var(--color-text-primary); line-height: 1.5; }
.step-meta { font-size: 10px; color: var(--color-text-muted); margin-top: 2px; }

.clear-route-btn { font-size: 11px; color: var(--color-text-muted); padding: 0; }

/* 地图区 */
.map-area { flex: 1; position: relative; }
.amap-box  { width: 100%; height: 100%; }
</style>

<!-- 地标卡片全局样式（AMap DOM 在 scoped 之外） -->
<style>
.heritage-card {
  position: relative;
  width: 240px;
  background: rgba(18, 18, 32, 0.92);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(61, 158, 140, 0.35);
  border-radius: 14px;
  padding: 14px 16px 10px;
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.55),
    0 0 0 1px rgba(255,255,255,0.04) inset;
  font-family: 'PingFang SC', 'Hiragino Sans GB', sans-serif;
  margin-bottom: 8px;
}
.heritage-card::after {
  content: '';
  position: absolute;
  bottom: -8px; left: 50%;
  transform: translateX(-50%);
  border-left: 8px solid transparent;
  border-right: 8px solid transparent;
  border-top: 8px solid rgba(18, 18, 32, 0.92);
  filter: drop-shadow(0 2px 2px rgba(0,0,0,0.3));
}
.popup-close-btn {
  position: absolute; top: 8px; right: 10px;
  width: 22px; height: 22px; border-radius: 50%;
  border: 1px solid rgba(255,255,255,0.15);
  background: rgba(255,255,255,0.08);
  color: rgba(255,255,255,0.6);
  font-size: 14px; line-height: 1; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: background 0.15s, color 0.15s; padding: 0;
}
.popup-close-btn:hover {
  background: rgba(192, 57, 43, 0.6); color: #fff; border-color: transparent;
}
.heritage-card-header {
  display: flex; align-items: flex-start; gap: 8px;
  margin-bottom: 8px; padding-right: 24px;
}
.heritage-card-icon { font-size: 18px; flex-shrink: 0; margin-top: 1px; }
.heritage-card-title-wrap {
  display: flex; flex-direction: column; gap: 4px; min-width: 0;
}
.heritage-card-name {
  font-size: 14px; font-weight: 600; color: #C9A84C; letter-spacing: 0.5px; line-height: 1.3;
}
.heritage-card-type {
  display: inline-block; align-self: flex-start;
  font-size: 10px; color: var(--color-accent-teal);
  background: rgba(61, 158, 140, 0.12);
  border: 1px solid rgba(61, 158, 140, 0.25);
  border-radius: 4px; padding: 1px 6px;
}
.heritage-card-address {
  display: flex; align-items: flex-start; gap: 6px;
  margin: 0 0 8px; padding: 0;
  font-size: 11px; color: rgba(180, 190, 210, 0.95); line-height: 1.5;
}
.heritage-card-addr-icon { flex-shrink: 0; font-size: 12px; }
.heritage-card-body {
  font-size: 12px; color: rgba(220, 225, 240, 0.85); line-height: 1.65;
  border-top: 1px solid rgba(255,255,255,0.07); padding-top: 9px;
}

/* 路线规划按钮（弹窗内） */
.popup-route-btn {
  display: flex; align-items: center; justify-content: center; gap: 6px;
  width: 100%; margin-top: 10px;
  padding: 7px 12px; border-radius: 8px;
  border: 1px solid rgba(61,158,140,0.5);
  background: rgba(61,158,140,0.12);
  color: #3d9e8c; font-size: 12px; font-weight: 600;
  cursor: pointer; transition: color 0.18s, background-color 0.18s, border-color 0.18s;
}
.popup-route-btn:hover {
  background: rgba(61,158,140,0.25);
  border-color: #3d9e8c;
  color: #fff;
}
.popup-route-btn.selected {
  background: rgba(61,158,140,0.3);
  border-color: #3d9e8c;
  color: #3d9e8c;
}

.amap-info-content {
  padding: 0 !important; background: transparent !important;
  border: none !important; box-shadow: none !important;
}
.amap-info-sharp, .amap-info-close { display: none !important; }

/* 全程路线编号标记 */
.tour-num-marker {
  width: 28px; height: 28px; border-radius: 50%;
  color: #fff; font-size: 12px; font-weight: 600;
  display: flex; align-items: center; justify-content: center;
  border: 2px solid rgba(255,255,255,0.8);
  box-shadow: 0 2px 8px rgba(0,0,0,0.4);
  font-family: 'PingFang SC', sans-serif;
}

/* 路线站点标签（地图浮层） */
.route-stop-label {
  background: rgba(18,18,32,0.88);
  border: 1px solid #3d9e8c;
  color: #fff; font-size: 11px;
  padding: 2px 7px; border-radius: 10px;
  white-space: nowrap;
  font-family: 'PingFang SC', sans-serif;
}
.origin-label { border-color: #3498DB; }
.dest-label   { border-color: #C0392B; }
</style>
