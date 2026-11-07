<template>
  <div class="heatmap-root">

    <!-- 顶部标题 + 切换按钮 -->
    <div class="heatmap-header">
      <div class="heatmap-title">
        <el-icon :size="18"><DataAnalysis /></el-icon>
        热力图分析
      </div>
      <div class="heatmap-switch">
        <el-button-group>
          <el-button
            :type="mode === 'heritage' ? 'primary' : 'default'"
            size="small"
            @click="switchMode('heritage')"
          >
            <el-icon><OfficeBuilding /></el-icon> 非遗项目分布
          </el-button>
          <el-button
            :type="mode === 'checkin' ? 'primary' : 'default'"
            size="small"
            @click="switchMode('checkin')"
          >
            <el-icon><LocationFilled /></el-icon> 用户打卡热度
          </el-button>
        </el-button-group>
        <el-button size="small" :loading="loading" @click="reload" class="refresh-btn">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>
    </div>

    <!-- 图例 + 统计条 -->
    <div class="heatmap-info">
      <div class="info-desc">
        <template v-if="mode === 'heritage'">
          <el-icon color="var(--color-accent-gold)"><InfoFilled /></el-icon>
          知识图谱中非遗项目（传承人、技艺、保护单位等）的地理分布
        </template>
        <template v-else>
          <el-icon color="var(--color-accent-teal)"><InfoFilled /></el-icon>
          审核通过的用户打卡记录地理分布
        </template>
      </div>
      <div class="info-count">
        共 <b>{{ points.length }}</b> 个数据点
        <span v-if="!loading && points.length === 0" class="no-data-hint">（暂无坐标数据）</span>
      </div>
    </div>

    <!-- 地图容器 -->
    <div class="map-wrap" v-loading="loading" element-loading-background="rgba(14,16,21,0.8)">
      <div id="heatmap-amap" class="amap-container"></div>

      <!-- 无数据占位 -->
      <div v-if="!loading && points.length === 0" class="no-data-overlay">
        <el-icon :size="48" color="var(--color-text-muted)"><MapLocation /></el-icon>
        <div>暂无可用坐标数据</div>
        <div class="no-data-sub">
          <template v-if="mode === 'heritage'">
            请确认 graph_nodes 表中含有 longitude/latitude 字段数据，
            或地区字段可识别的城市名称
          </template>
          <template v-else>
            请确认已有审核通过（status=1）且含经纬度的打卡记录
          </template>
        </div>
      </div>
    </div>

    <!-- 图例 -->
    <div class="heatmap-legend">
      <span class="legend-label">密度</span>
      <div class="legend-bar">
        <span class="legend-low">低</span>
        <div class="legend-gradient"></div>
        <span class="legend-high">高</span>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import {
  DataAnalysis, LocationFilled, Refresh,
  InfoFilled, MapLocation, OfficeBuilding
} from '@element-plus/icons-vue'
import { adminHeatmapHeritage, adminHeatmapCheckin } from '@/api'

const mode    = ref('heritage')   // 'heritage' | 'checkin'
const loading = ref(false)
const points  = ref([])

let mapInstance  = null
let heatmapLayer = null

// ── 初始化地图 ────────────────────────────────────────────────
async function initMap() {
  if (!window.AMap) {
    ElMessage.error('高德地图未加载，请检查 index.html 中的 AMap 脚本')
    return
  }

  // 销毁旧实例
  if (mapInstance) {
    mapInstance.destroy()
    mapInstance = null
    heatmapLayer = null
  }

  mapInstance = new window.AMap.Map('heatmap-amap', {
    center:   [104.1954, 35.8617],
    zoom:     4,
    mapStyle: 'amap://styles/dark',
  })

  mapInstance.plugin(['AMap.HeatMap'], () => {
    heatmapLayer = new window.AMap.HeatMap(mapInstance, {
      radius:  25,
      opacity: [0, 0.85],
      gradient: {
        0.25: '#1a9850',
        0.50: '#fee08b',
        0.75: '#f46d43',
        1.00: '#d73027',
      },
    })
    renderHeatmap()
  })
}

// ── 渲染热力图数据 ─────────────────────────────────────────────
function renderHeatmap() {
  if (!heatmapLayer) return

  const heatData = points.value.map(p => ({
    lng:    p.lng,
    lat:    p.lat,
    count:  p.weight || 1,
  }))

  heatmapLayer.setDataSet({
    data: heatData,
    max:  Math.max(1, heatData.length > 0 ? 5 : 1),
  })

  // 有数据时自适应视野
  if (heatData.length > 0) {
    try {
      const bounds = heatData.reduce(
        (acc, p) => ({
          minLng: Math.min(acc.minLng, p.lng),
          maxLng: Math.max(acc.maxLng, p.lng),
          minLat: Math.min(acc.minLat, p.lat),
          maxLat: Math.max(acc.maxLat, p.lat),
        }),
        { minLng: 180, maxLng: -180, minLat: 90, maxLat: -90 }
      )
      mapInstance.setBounds(
        new window.AMap.Bounds(
          [bounds.minLng, bounds.minLat],
          [bounds.maxLng, bounds.maxLat]
        )
      )
    } catch (_) { /* 边界计算失败时保持默认视野 */ }
  }
}

// ── 数据加载 ─────────────────────────────────────────────────
async function loadData() {
  loading.value = true
  try {
    const res = mode.value === 'heritage'
      ? await adminHeatmapHeritage()
      : await adminHeatmapCheckin()

    if (res.data.status === 'success') {
      points.value = res.data.points || []
    } else {
      ElMessage.warning(res.data.msg || '数据加载失败')
      points.value = []
    }
  } catch (e) {
    ElMessage.error('热力图数据请求失败：' + (e.message || '网络异常'))
    points.value = []
  } finally {
    loading.value = false
    // 数据就绪后渲染
    await nextTick()
    if (heatmapLayer) {
      renderHeatmap()
    } else {
      await initMap()
    }
  }
}

async function switchMode(m) {
  if (m === mode.value) return
  mode.value = m
  await loadData()
}

async function reload() {
  await loadData()
}

onMounted(async () => {
  await nextTick()
  await loadData()
})

onUnmounted(() => {
  if (mapInstance) {
    mapInstance.destroy()
    mapInstance = null
    heatmapLayer = null
  }
})
</script>

<style scoped>
.heatmap-root {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 20px 24px;
  background: var(--color-bg-base);
  overflow: hidden;
}

/* 顶部标题 */
.heatmap-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  flex-shrink: 0;
}
.heatmap-title {
  display: flex; align-items: center; gap: 8px;
  font-size: 18px; font-family: var(--font-serif);
  color: var(--color-text-primary);
}
.heatmap-switch { display: flex; align-items: center; gap: 8px; }
.refresh-btn { padding: 5px 8px; }

/* 信息条 */
.heatmap-info {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 14px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--color-text-secondary);
  flex-shrink: 0;
}
.info-desc { display: flex; align-items: center; gap: 6px; }
.info-count b { color: var(--color-accent-gold); }
.no-data-hint { color: var(--color-accent-red); font-size: 12px; }

/* 地图 */
.map-wrap {
  flex: 1;
  position: relative;
  border-radius: var(--radius-lg);
  overflow: hidden;
  border: 1px solid var(--color-border);
  min-height: 0;
}
.amap-container { width: 100%; height: 100%; }

/* 无数据覆盖层 */
.no-data-overlay {
  position: absolute; inset: 0;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 12px;
  background: rgba(14, 16, 21, 0.75);
  font-size: 15px; color: var(--color-text-secondary);
}
.no-data-sub {
  font-size: 12px; color: var(--color-text-muted);
  text-align: center; max-width: 400px; line-height: 1.6;
}

/* 图例 */
.heatmap-legend {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 0 0;
  flex-shrink: 0;
}
.legend-label { font-size: 12px; color: var(--color-text-secondary); }
.legend-bar { display: flex; align-items: center; gap: 6px; }
.legend-low, .legend-high { font-size: 11px; color: var(--color-text-muted); }
.legend-gradient {
  width: 160px; height: 10px; border-radius: 5px;
  background: linear-gradient(to right, #1a9850, #fee08b, #f46d43, #d73027);
}
</style>