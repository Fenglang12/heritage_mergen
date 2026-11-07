<template>
  <div class="page-wrapper">
    <div class="page-header">
      <el-icon class="ph-icon"><Share /></el-icon>
      <div>
        <h2 class="ph-title">知识图谱透视</h2>
        <p class="ph-sub">可视化非遗项目、传承人、地区与类别之间的关联关系</p>
      </div>
      <div style="margin-left:auto; display:flex; gap:12px; align-items:center;">
        <div class="stat-card stat-nodes">
          <el-icon class="stat-icon"><Share /></el-icon>
          <div class="stat-body">
            <div class="stat-value">{{ nodeCount || 0 }}</div>
            <div class="stat-label">个节点</div>
          </div>
        </div>
        <div class="stat-card stat-edges">
          <el-icon class="stat-icon"><Connection /></el-icon>
          <div class="stat-body">
            <div class="stat-value">{{ edgeCount || 0 }}</div>
            <div class="stat-label">条关系</div>
          </div>
        </div>
        <el-button size="small" @click="loadGraph" :loading="loading">
          <el-icon><Refresh /></el-icon>刷新
        </el-button>
      </div>
    </div>

    <!-- 图例 + 搜索 -->
    <div class="graph-toolbar">
      <div class="legend-row">
        <div v-for="c in categories" :key="c.name" class="legend-item">
          <span class="legend-dot" :style="{ background: c.color }"></span>
          <span>{{ c.name }}</span>
        </div>
      </div>
      <div class="search-wrap">
        <span class="hint-text">拖拽旋转 · 滚轮缩放</span>
        <el-autocomplete
          v-model="searchKeyword"
          class="graph-search-input"
          popper-class="graph-search-popper"
          placeholder="搜索节点名称…"
          size="small"
          clearable
          :trigger-on-focus="false"
          :fetch-suggestions="querySearchSuggestions"
          @select="onSelectSearchNode"
          @clear="clearSearchFocus"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
          <template #default="{ item }">
            <div class="search-suggest-item">
              <span class="search-suggest-dot" :style="{ background: getCategoryColor(item.label) }"></span>
              <span class="search-suggest-type">{{ item.label }}</span>
              <span class="search-suggest-name">{{ item.name }}</span>
            </div>
          </template>
        </el-autocomplete>
        <el-button
          v-if="focusedNodeId"
          size="small"
          text
          type="info"
          @click="clearSearchFocus"
        >
          取消定位
        </el-button>
      </div>
    </div>

    <!-- 3D 图谱容器 -->
    <div class="graph-container">
      <div v-if="loading" class="graph-overlay">
        <div class="loading-animation">
          <div class="node-pulse"></div>
          <div class="node-pulse pulse-2"></div>
          <div class="node-pulse pulse-3"></div>
        </div>
        <p class="loading-text">正在构建知识星轨...</p>
      </div>
      <div v-else-if="errorMsg" class="graph-overlay">
        <el-result icon="error" :title="errorMsg">
          <template #extra>
            <el-button type="primary" @click="loadGraph">重新加载</el-button>
          </template>
        </el-result>
      </div>

      <canvas ref="canvasRef" class="three-canvas"></canvas>

      <!-- Hover tooltip -->
      <div v-if="hoveredNode" class="node-tooltip"
           :style="{ left: tooltipPos.x + 'px', top: tooltipPos.y + 'px' }">
        <div class="tt-badge" :style="{ background: getCategoryColor(hoveredNode.nodeLabel) }">
          {{ hoveredNode.nodeLabel }}
        </div>
        <div class="tt-name">{{ hoveredNode.rawName }}</div>
      </div>

      <!-- 图谱问答 -->
      <div class="graph-qa-panel">
        <div class="graph-qa-title">图谱问答</div>
        <el-input
          v-model="graphQuestion"
          placeholder="例如：白蛇传说属于什么类别？"
          size="small"
          clearable
          @keyup.enter="submitGraphQuery"
        />
        <el-button
          type="primary"
          size="small"
          :loading="queryLoading"
          :disabled="!graphQuestion.trim()"
          @click="submitGraphQuery"
        >
          提问
        </el-button>
        <div v-if="graphAnswer" class="graph-qa-answer">{{ graphAnswer }}</div>
      </div>

      <!-- 点击详情浮窗 -->
      <transition name="detail-slide">
        <div v-if="selectedNode" class="node-detail">
          <div class="detail-header">
            <span class="detail-badge" :style="{ background: getCategoryColor(selectedNode.label) }">
              {{ selectedNode.label }}
            </span>
            <el-icon class="detail-close" @click="selectedNode = null"><Close /></el-icon>
          </div>
          <h3 class="detail-name">{{ selectedNode.properties?.name || selectedNode.id }}</h3>
          <div class="detail-props">
            <template v-for="(val, key) in filteredProps" :key="key">
              <div class="prop-row">
                <span class="prop-key">{{ propLabelMap[key] || key }}</span>
                <span class="prop-val">{{ val }}</span>
              </div>
            </template>
          </div>
        </div>
      </transition>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import * as THREE from 'three'
import { ElMessage } from 'element-plus'
import { getGraphData, queryGraph } from '@/api'

const canvasRef      = ref(null)
const loading        = ref(false)
const errorMsg       = ref('')
const searchKeyword  = ref('')
const selectedNode   = ref(null)
const hoveredNode    = ref(null)
const tooltipPos     = ref({ x: 0, y: 0 })
const nodeCount      = ref(0)
const edgeCount      = ref(0)
const graphQuestion  = ref('')
const graphAnswer    = ref('')
const queryLoading   = ref(false)
const relatedNodeIds = ref([])
const focusedNodeId  = ref(null)

const categories = [
  { name: '非遗项目', color: '#3dcea8' },
  { name: '传承人',  color: '#f0c040' },
  { name: '地区',    color: '#8b7fe8' },
  { name: '类别',    color: '#e05c5c' },
  { name: '批次',    color: '#4aafd4' },
]
const colorMap = Object.fromEntries(categories.map(c => [c.name, c.color]))
function getCategoryColor(label) { return colorMap[label] || '#888' }

const propLabelMap = {
  name: '名称', region: '地区', category: '类别', batch: '批次',
  type: '类型', protection_unit: '保护单位', ethnicity: '民族',
  gender: '性别', work_unit: '工作单位'
}
const filteredProps = computed(() => {
  if (!selectedNode.value?.properties) return {}
  return Object.fromEntries(
    Object.entries(selectedNode.value.properties).filter(([k, v]) => v && k !== 'id')
  )
})

// Three.js 对象
let renderer, scene, camera, animFrameId
let nodeMeshes = []   // Array<{ mesh, data }>
let edgeLines  = []
let isDragging = false
let mouseDownX = 0, mouseDownY = 0
let spherical  = { theta: 0.3, phi: 1.2, radius: 700 }
let cameraTarget = new THREE.Vector3(0, 0, 0)
let defaultCamera = { theta: 0.3, phi: 1.2, radius: 700, tx: 0, ty: 0, tz: 0 }
let focusAnimId = null
let raycaster, mouse

const FOCUS_RADIUS = 320

onMounted(() => loadGraph())
onUnmounted(() => dispose())

async function loadGraph() {
  loading.value   = true
  errorMsg.value  = ''
  dispose()
  try {
    const res = await getGraphData()
    const rawNodes = res.data.nodes || []
    const rawEdges = res.data.edges || []
    nodeCount.value = rawNodes.length
    edgeCount.value = rawEdges.length
    await nextTick()
    initThree(rawNodes, rawEdges)
  } catch {
    errorMsg.value = '图谱数据加载失败，请检查登录状态'
  } finally {
    loading.value = false
  }
}

function initThree(rawNodes, rawEdges) {
  const canvas = canvasRef.value
  if (!canvas) return
  const W = canvas.clientWidth || canvas.offsetWidth
  const H = canvas.clientHeight || canvas.offsetHeight

  // Renderer
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true })
  renderer.setSize(W, H)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setClearColor(0x000000, 0)

  // Scene & Camera
  scene  = new THREE.Scene()
  camera = new THREE.PerspectiveCamera(50, W / H, 1, 8000)
  updateCamera()

  // Lights
  scene.add(new THREE.AmbientLight(0xffffff, 0.55))
  const dir = new THREE.DirectionalLight(0xffffff, 0.9)
  dir.position.set(300, 400, 300)
  scene.add(dir)
  const fill = new THREE.PointLight(0x4488ff, 0.4, 1200)
  fill.position.set(-200, -200, 200)
  scene.add(fill)

  // ── 力导向布局（纯 JS 预计算，不占渲染帧，彻底无频闪）──
  const nodeMap = {}
  const simNodes = rawNodes.map(n => {
    const props   = n.properties || {}
    const rawName = props.name || n.label || n.id
    const r = 250
    const theta = Math.random() * Math.PI * 2
    const phi   = Math.acos(2 * Math.random() - 1)
    const obj = {
      id: String(n.id), rawName,
      nodeLabel: n.label || '未知', properties: props,
      x: r * Math.sin(phi) * Math.cos(theta),
      y: r * Math.sin(phi) * Math.sin(theta),
      z: r * Math.cos(phi),
      vx: 0, vy: 0, vz: 0
    }
    nodeMap[obj.id] = obj
    return obj
  })

  const simEdges = rawEdges
    .map(e => ({ s: nodeMap[String(e.source)], t: nodeMap[String(e.target)], rel: e.relationship }))
    .filter(e => e.s && e.t)

  // 力导向迭代（完全预计算，静态结果，渲染时节点绝对不动）
  const ITER = 100, REPUL = 20000, ATTR = 0.015, DAMP = 0.82, TLEN = 200

  for (let i = 0; i < ITER; i++) {
    for (let a = 0; a < simNodes.length; a++) {
      for (let b = a + 1; b < simNodes.length; b++) {
        const na = simNodes[a], nb = simNodes[b]
        const dx = nb.x - na.x, dy = nb.y - na.y, dz = nb.z - na.z
        const d2 = dx*dx + dy*dy + dz*dz + 1
        const f  = REPUL / d2, inv = 1 / Math.sqrt(d2)
        na.vx -= f*dx*inv; na.vy -= f*dy*inv; na.vz -= f*dz*inv
        nb.vx += f*dx*inv; nb.vy += f*dy*inv; nb.vz += f*dz*inv
      }
    }
    for (const e of simEdges) {
      const dx = e.t.x-e.s.x, dy = e.t.y-e.s.y, dz = e.t.z-e.s.z
      const d = Math.sqrt(dx*dx+dy*dy+dz*dz) + 0.01
      const f = (d - TLEN) * ATTR
      e.s.vx += f*dx/d; e.s.vy += f*dy/d; e.s.vz += f*dz/d
      e.t.vx -= f*dx/d; e.t.vy -= f*dy/d; e.t.vz -= f*dz/d
    }
    for (const n of simNodes) {
      n.vx = (n.vx - n.x*0.002) * DAMP
      n.vy = (n.vy - n.y*0.002) * DAMP
      n.vz = (n.vz - n.z*0.002) * DAMP
      n.x += n.vx; n.y += n.vy; n.z += n.vz
    }
  }

  // ── 节点球体 ─────────────────────────────────────────
  const sizeMap = { '非遗项目': 18, '传承人': 13, '地区': 9, '类别': 12, '批次': 9 }
  nodeMeshes = []
  for (const n of simNodes) {
    const sz  = sizeMap[n.nodeLabel] || 9
    const col = new THREE.Color(getCategoryColor(n.nodeLabel))
    const geo = new THREE.SphereGeometry(sz, 20, 20)
    const mat = new THREE.MeshPhongMaterial({
      color: col,
      emissive: col.clone().multiplyScalar(0.3),
      shininess: 90,
      transparent: true, opacity: 1
    })
    const mesh = new THREE.Mesh(geo, mat)
    mesh.position.set(n.x, n.y, n.z)
    mesh.userData = n
    scene.add(mesh)
    nodeMeshes.push({ mesh, data: n })
  }

  // ── 边线 ──────────────────────────────────────────────
  edgeLines = []
  for (const e of simEdges) {
    const pts = [
      new THREE.Vector3(e.s.x, e.s.y, e.s.z),
      new THREE.Vector3(e.t.x, e.t.y, e.t.z)
    ]
    const geo  = new THREE.BufferGeometry().setFromPoints(pts)
    const mat  = new THREE.LineBasicMaterial({ color: 0x3a4a5e, transparent: true, opacity: 0.4 })
    const line = new THREE.Line(geo, mat)
    scene.add(line)
    edgeLines.push(line)
  }

  raycaster = new THREE.Raycaster()
  mouse     = new THREE.Vector2()

  defaultCamera = {
    theta: spherical.theta,
    phi: spherical.phi,
    radius: spherical.radius,
    tx: 0,
    ty: 0,
    tz: 0,
  }
  cameraTarget.set(0, 0, 0)

  bindEvents()
  animate()
}

function animate() {
  // 纯静态渲染，节点位置完全固定，只有相机旋转
  animFrameId = requestAnimationFrame(animate)
  renderer.render(scene, camera)
}

function updateCamera() {
  if (!camera) return
  const { theta, phi, radius } = spherical
  const t = cameraTarget
  camera.position.set(
    t.x + radius * Math.sin(phi) * Math.cos(theta),
    t.y + radius * Math.cos(phi),
    t.z + radius * Math.sin(phi) * Math.sin(theta),
  )
  camera.lookAt(t)
}

function bindEvents() {
  const c = canvasRef.value
  c.addEventListener('mousedown', onMouseDown)
  c.addEventListener('mousemove', onMouseMove)
  c.addEventListener('mouseup',   onMouseUp)
  c.addEventListener('click',     onClick)
  c.addEventListener('wheel',     onWheel, { passive: true })
  window.addEventListener('resize', onResize)
}

function onMouseDown(e) {
  isDragging = false
  mouseDownX = e.clientX
  mouseDownY = e.clientY
}

function onMouseMove(e) {
  const canvas = canvasRef.value
  if (!canvas) return

  if (e.buttons === 1) {
    isDragging = true
    const dx = (e.clientX - mouseDownX) * 0.005
    const dy = (e.clientY - mouseDownY) * 0.005
    spherical.theta -= dx
    spherical.phi    = Math.max(0.1, Math.min(Math.PI - 0.1, spherical.phi + dy))
    mouseDownX = e.clientX; mouseDownY = e.clientY
    updateCamera()
    return
  }

  // Hover 检测
  const rect = canvas.getBoundingClientRect()
  mouse.x =  ((e.clientX - rect.left) / rect.width)  * 2 - 1
  mouse.y = -((e.clientY - rect.top)  / rect.height)  * 2 + 1
  raycaster.setFromCamera(mouse, camera)
  const meshes = nodeMeshes.map(n => n.mesh)
  const hits   = raycaster.intersectObjects(meshes)

  applyNodeVisuals()

  if (hits.length > 0) {
    const m = hits[0].object
    const col = getCategoryColor(m.userData.nodeLabel)
    m.material.emissive.set(new THREE.Color(col).multiplyScalar(
      focusedNodeId.value === m.userData.id ? 1.2 : 1.0,
    ))
    hoveredNode.value = m.userData
    tooltipPos.value  = { x: e.clientX - rect.left + 14, y: e.clientY - rect.top - 14 }
    canvas.style.cursor = 'pointer'
  } else {
    hoveredNode.value   = null
    canvas.style.cursor = 'default'
  }
}

function onMouseUp() {}

function onClick(e) {
  if (isDragging) { isDragging = false; return }
  const canvas = canvasRef.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  mouse.x =  ((e.clientX - rect.left) / rect.width)  * 2 - 1
  mouse.y = -((e.clientY - rect.top)  / rect.height)  * 2 + 1
  raycaster.setFromCamera(mouse, camera)
  const hits = raycaster.intersectObjects(nodeMeshes.map(n => n.mesh))
  if (hits.length > 0) {
    const d = hits[0].object.userData
    selectedNode.value = { id: d.id, label: d.nodeLabel, rawName: d.rawName, properties: d.properties }
  } else {
    selectedNode.value = null
  }
}

function onWheel(e) {
  spherical.radius = Math.max(150, Math.min(3000, spherical.radius + e.deltaY))
  updateCamera()
}

function onResize() {
  const canvas = canvasRef.value
  if (!canvas || !renderer || !camera) return
  const W = canvas.clientWidth, H = canvas.clientHeight
  camera.aspect = W / H
  camera.updateProjectionMatrix()
  renderer.setSize(W, H)
}

function applyNodeVisuals() {
  const focusId = focusedNodeId.value
  const related = new Set(relatedNodeIds.value.map((id) => String(id).toLowerCase()))
  const hasRelated = related.size > 0

  for (const { mesh, data } of nodeMeshes) {
    const name = (mesh.userData.rawName || '').toLowerCase()
    const nid = (mesh.userData.id || '').toLowerCase()
    const col = new THREE.Color(getCategoryColor(data.nodeLabel))
    const isFocus = focusId && data.id === focusId
    const matchRelated = hasRelated && (related.has(name) || related.has(nid))

    if (isFocus) {
      mesh.material.opacity = 1
      mesh.material.emissive.copy(col).multiplyScalar(1.1)
      mesh.scale.setScalar(1.6)
    } else if (focusId || hasRelated) {
      mesh.material.opacity = matchRelated ? 0.85 : 0.07
      mesh.material.emissive.copy(col).multiplyScalar(0.25)
      mesh.scale.setScalar(matchRelated ? 1.2 : 1)
    } else {
      mesh.material.opacity = 1
      mesh.material.emissive.copy(col).multiplyScalar(0.3)
      mesh.scale.setScalar(1)
    }
  }

  const dimEdges = Boolean(focusId || hasRelated)
  for (const line of edgeLines) {
    line.material.opacity = dimEdges ? 0.12 : 0.4
  }
}

function querySearchSuggestions(queryString, cb) {
  const kw = (queryString || '').trim().toLowerCase()
  if (!kw || !nodeMeshes.length) {
    cb([])
    return
  }
  const list = []
  for (const { data } of nodeMeshes) {
    const name = data.rawName || data.id || ''
    const nid = String(data.id || '')
    if (name.toLowerCase().includes(kw) || nid.toLowerCase().includes(kw)) {
      list.push({
        value: name,
        name,
        label: data.nodeLabel,
        nodeId: data.id,
        data,
      })
    }
  }
  cb(list.slice(0, 20))
}

function setSelectedFromNodeData(d) {
  selectedNode.value = {
    id: d.id,
    label: d.nodeLabel,
    rawName: d.rawName,
    properties: d.properties,
  }
}

function cancelFocusAnim() {
  if (focusAnimId) {
    cancelAnimationFrame(focusAnimId)
    focusAnimId = null
  }
}

function animateCameraToNode(data, duration = 650) {
  const entry = nodeMeshes.find((n) => n.data.id === data.id)
  if (!entry || !camera) return

  cancelFocusAnim()
  const { x, y, z } = entry.mesh.position
  const start = {
    tx: cameraTarget.x,
    ty: cameraTarget.y,
    tz: cameraTarget.z,
    theta: spherical.theta,
    phi: spherical.phi,
    radius: spherical.radius,
  }
  const end = {
    tx: x,
    ty: y,
    tz: z,
    theta: spherical.theta,
    phi: Math.max(0.35, Math.min(1.25, spherical.phi)),
    radius: FOCUS_RADIUS,
  }
  const t0 = performance.now()

  const step = (now) => {
    const p = Math.min(1, (now - t0) / duration)
    const ease = 1 - Math.pow(1 - p, 3)
    cameraTarget.set(
      start.tx + (end.tx - start.tx) * ease,
      start.ty + (end.ty - start.ty) * ease,
      start.tz + (end.tz - start.tz) * ease,
    )
    spherical.theta = start.theta + (end.theta - start.theta) * ease
    spherical.phi = start.phi + (end.phi - start.phi) * ease
    spherical.radius = start.radius + (end.radius - start.radius) * ease
    updateCamera()
    if (p < 1) {
      focusAnimId = requestAnimationFrame(step)
    } else {
      focusAnimId = null
    }
  }
  focusAnimId = requestAnimationFrame(step)
}

function focusOnNode(data) {
  if (!data) return
  focusedNodeId.value = data.id
  searchKeyword.value = data.rawName || data.id
  setSelectedFromNodeData(data)
  applyNodeVisuals()
  animateCameraToNode(data)
}

function clearSearchFocus() {
  cancelFocusAnim()
  focusedNodeId.value = null
  searchKeyword.value = ''
  cameraTarget.set(defaultCamera.tx, defaultCamera.ty, defaultCamera.tz)
  spherical.theta = defaultCamera.theta
  spherical.phi = defaultCamera.phi
  spherical.radius = defaultCamera.radius
  updateCamera()
  applyNodeVisuals()
}

function onSelectSearchNode(item) {
  if (!item?.data) return
  focusOnNode(item.data)
}

function focusFirstRelatedNode() {
  if (!relatedNodeIds.value.length) return
  const related = new Set(relatedNodeIds.value.map((id) => String(id).toLowerCase()))
  const hit = nodeMeshes.find(({ data }) => {
    const name = (data.rawName || '').toLowerCase()
    const nid = String(data.id || '').toLowerCase()
    return related.has(name) || related.has(nid)
  })
  if (hit) focusOnNode(hit.data)
}

async function submitGraphQuery() {
  const q = graphQuestion.value.trim()
  if (!q) return
  queryLoading.value = true
  graphAnswer.value = ''
  try {
    const res = await queryGraph(q)
    graphAnswer.value = res.data.answer || '未找到相关结果'
    relatedNodeIds.value = res.data.related_nodes || []
    focusFirstRelatedNode()
  } catch {
    ElMessage.error('图谱问答失败，请稍后重试')
  } finally {
    queryLoading.value = false
  }
}

function dispose() {
  cancelFocusAnim()
  focusedNodeId.value = null
  if (animFrameId) { cancelAnimationFrame(animFrameId); animFrameId = null }
  const c = canvasRef.value
  if (c) {
    c.removeEventListener('mousedown', onMouseDown)
    c.removeEventListener('mousemove', onMouseMove)
    c.removeEventListener('mouseup',   onMouseUp)
    c.removeEventListener('click',     onClick)
    c.removeEventListener('wheel',     onWheel)
  }
  window.removeEventListener('resize', onResize)
  if (scene) {
    scene.traverse(obj => {
      if (obj.geometry) obj.geometry.dispose()
      if (obj.material) obj.material.dispose()
    })
  }
  if (renderer) { renderer.dispose(); renderer = null }
  nodeMeshes = []; edgeLines = []; scene = null
}
</script>

<style scoped>
@import '@/assets/page-common.css';

.page-header { align-items: center; }

.stat-card {
  display: flex; align-items: center; gap: 10px; min-width: 130px;
  padding: 8px 16px; border-radius: 10px; cursor: default; user-select: none;
  position: relative; overflow: hidden; transition: transform 0.15s, box-shadow 0.15s;
}
.stat-card:hover { transform: translateY(-2px); }
.stat-card::after {
  content: ''; position: absolute; right: -10px; bottom: -10px;
  width: 52px; height: 52px; border-radius: 50%; background: rgba(255,255,255,0.12);
}
.stat-nodes { background: linear-gradient(135deg, #3d9e8c, #2a7a70); box-shadow: 0 4px 14px rgba(61,158,140,0.4); }
.stat-edges { background: linear-gradient(135deg, #c9a84c, #a8842a); box-shadow: 0 4px 14px rgba(201,168,76,0.4); }
.stat-icon  { font-size: 22px; color: rgba(255,255,255,0.75); flex-shrink: 0; }
.stat-body  { display: flex; flex-direction: column; gap: 1px; }
.stat-value { font-size: 20px; font-weight: 600; color: #fff; line-height: 1.1; font-variant-numeric: tabular-nums; }
.stat-label { font-size: 11px; color: rgba(255,255,255,0.75); letter-spacing: 0.5px; }

.graph-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 16px; background: var(--color-bg-panel);
  border: 1px solid var(--color-border); border-radius: var(--radius-md); flex-shrink: 0;
}
.legend-row  { display: flex; gap: 20px; flex-wrap: wrap; }
.legend-item { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--color-text-secondary); }
.legend-dot  { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.hint-text   { font-size: 11px; color: var(--color-text-muted); white-space: nowrap; }
.search-wrap {
  display: flex; gap: 8px; align-items: center; flex-wrap: wrap; justify-content: flex-end;
}
.graph-search-input { width: 260px; }
.search-suggest-item {
  display: flex; align-items: center; gap: 8px; padding: 2px 0; min-width: 0;
}
.search-suggest-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.search-suggest-type {
  font-size: 11px; color: var(--color-text-muted); flex-shrink: 0;
}
.search-suggest-name {
  font-size: 13px; color: var(--color-text-primary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

.graph-container {
  flex: 1; position: relative; overflow: hidden;
  background: var(--color-bg-panel); border: 1px solid var(--color-border);
  border-radius: var(--radius-lg); min-height: 0;
}
.three-canvas { width: 100%; height: 100%; display: block; }

.graph-overlay {
  position: absolute; inset: 0; z-index: 10;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  background: var(--color-bg-panel);
}
.loading-animation { position: relative; width: 80px; height: 80px; margin-bottom: 20px; }
.node-pulse {
  position: absolute; inset: 0; border-radius: 50%;
  border: 2px solid var(--color-accent-teal);
  animation: pulse-ring 2s ease-out infinite;
}
.pulse-2 { animation-delay: 0.6s; border-color: var(--color-accent-gold); }
.pulse-3 { animation-delay: 1.2s; }
@keyframes pulse-ring {
  0%   { transform: scale(0.3); opacity: 1; }
  100% { transform: scale(1.2); opacity: 0; }
}
.loading-text { color: var(--color-text-muted); font-size: 13px; letter-spacing: 0.4px; }

.node-tooltip {
  position: absolute; z-index: 30; pointer-events: none;
  background: rgba(8, 10, 18, 0.93); border: 1px solid rgba(255,255,255,0.1);
  border-radius: 8px; padding: 8px 12px; backdrop-filter: blur(10px);
  box-shadow: 0 4px 20px rgba(0,0,0,0.5);
}
.tt-badge {
  font-size: 10px; color: #fff; padding: 1px 7px;
  border-radius: 8px; display: inline-block; margin-bottom: 4px; letter-spacing: 1px;
}
.tt-name { font-size: 13px; color: #e8e6df; font-weight: 500; }

.node-detail {
  position: absolute; top: 16px; right: 16px; z-index: 20; width: 240px;
  background: var(--color-bg-card); border: 1px solid var(--color-border);
  border-radius: var(--radius-md); padding: 14px; box-shadow: 0 8px 32px rgba(0,0,0,0.4);
}
.detail-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.detail-badge  { font-size: 11px; color: #fff; padding: 2px 8px; border-radius: 10px; letter-spacing: 1px; }
.detail-close  { color: var(--color-text-muted); cursor: pointer; font-size: 16px; }
.detail-close:hover { color: var(--color-text-primary); }
.detail-name   {
  font-family: var(--font-serif); font-size: 15px; color: var(--color-text-primary);
  margin-bottom: 12px; border-bottom: 1px solid var(--color-border); padding-bottom: 8px;
}
.detail-props  { display: flex; flex-direction: column; gap: 6px; }
.prop-row      { display: flex; gap: 8px; align-items: flex-start; }
.prop-key      { font-size: 11px; color: var(--color-text-muted); flex-shrink: 0; width: 62px; padding-top: 1px; }
.prop-val      { font-size: 12px; color: var(--color-text-secondary); line-height: 1.5; word-break: break-word; }

.detail-slide-enter-active,
.detail-slide-leave-active { transition: opacity 0.2s, transform 0.2s; }
.detail-slide-enter-from,
.detail-slide-leave-to { opacity: 0; transform: translateX(10px); }

.graph-qa-panel {
  position: absolute; right: 16px; bottom: 16px; z-index: 25;
  width: 280px; padding: 12px;
  background: rgba(22, 25, 32, 0.92);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  display: flex; flex-direction: column; gap: 8px;
  backdrop-filter: blur(8px);
}
.graph-qa-title { font-size: 12px; font-weight: 600; color: var(--color-accent-teal); }
.graph-qa-answer {
  font-size: 12px; line-height: 1.6; color: var(--color-text-secondary);
  max-height: 120px; overflow-y: auto;
}
</style>

<!-- 搜索下拉 teleport 到 body，需全局样式 -->
<style>
.graph-search-popper.el-popper {
  background: #1c1f27 !important;
  border: 1px solid #2a2e38 !important;
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.55) !important;
}

.graph-search-popper .el-popper__arrow::before {
  background: #1c1f27 !important;
  border-color: #2a2e38 !important;
}

.graph-search-popper .el-autocomplete-suggestion__wrap {
  background: #1c1f27 !important;
}

.graph-search-popper .el-autocomplete-suggestion li {
  color: #e8e6df !important;
  background: transparent !important;
}

.graph-search-popper .el-autocomplete-suggestion li:hover,
.graph-search-popper .el-autocomplete-suggestion li.highlighted {
  background: rgba(61, 158, 140, 0.15) !important;
}

.graph-search-popper .search-suggest-item {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.graph-search-popper .search-suggest-type {
  font-size: 11px;
  color: #3d9e8c !important;
  flex-shrink: 0;
}

.graph-search-popper .search-suggest-name {
  font-size: 13px;
  font-weight: 600;
  color: #e8e6df !important;
}
</style>