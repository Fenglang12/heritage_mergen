<template>
  <div class="community-root">

    <!-- ── 左侧：地图 + 打卡表单 ─────────────────────────────── -->
    <div class="left-panel">
      <div class="panel-header">
        <span class="panel-title"><el-icon><Location /></el-icon> 非遗打卡地图</span>
        <el-button type="primary" size="small" @click="openCheckinDialog">
          <el-icon><Plus /></el-icon> 我要打卡
        </el-button>
      </div>

      <!-- 高德地图 -->
      <div id="community-map" class="map-box"></div>

      <!-- 地图图例 -->
      <div class="map-legend">
        <span class="legend-dot user"></span><span>用户打卡</span>
      </div>
    </div>

    <!-- ── 右侧：打卡广场 ─────────────────────────────────────── -->
    <div class="right-panel">
      <div class="panel-header">
        <span class="panel-title"><el-icon><PictureFilled /></el-icon> 打卡广场</span>
        <el-input
          v-model="searchSite"
          placeholder="搜索地点…"
          size="small"
          clearable
          style="width:160px"
          @change="loadCheckins(1)"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
      </div>

      <!-- 打卡卡片列表 -->
      <div class="checkin-list" v-loading="listLoading">
        <div v-if="checkins.length === 0 && !listLoading" class="empty-state">
          <el-empty description="暂无打卡记录，快去探索吧！" :image-size="80" />
        </div>

        <div
          v-for="item in checkins"
          :key="item.id"
          class="checkin-card"
          @click="openDetail(item)"
        >
          <div class="card-photo" v-if="item.photo_data">
            <img :src="item.photo_data" alt="打卡照片" />
            <div class="card-overlay">
              <el-icon><ZoomIn /></el-icon>
            </div>
          </div>
          <div class="card-photo no-photo" v-else>
            <el-icon size="32"><Picture /></el-icon>
          </div>

          <div class="card-body">
            <div class="card-site">
              <el-icon><Location /></el-icon>
              <span>{{ item.site_name }}</span>
            </div>
            <div class="card-desc" v-if="item.description">{{ item.description }}</div>
            <div class="card-meta">
              <el-avatar :size="20" class="meta-avatar">{{ item.username?.charAt(0)?.toUpperCase() }}</el-avatar>
              <span class="meta-user">{{ item.username }}</span>
              <span class="meta-time">{{ item.created_at }}</span>
              <el-icon class="meta-comment"><ChatDotSquare /></el-icon>
              <span class="meta-comment-cnt">{{ item.comment_count }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 分页 -->
      <div class="pagination-bar" v-if="totalPages > 1">
        <el-pagination
          small
          background
          layout="prev, pager, next"
          :total="totalCount"
          :page-size="12"
          v-model:current-page="currentPage"
          @current-change="loadCheckins"
        />
      </div>

      <!-- 我的打卡入口 -->
      <div class="my-checkin-btn">
        <el-button size="small" text @click="myCheckinVisible = true">
          <el-icon><Tickets /></el-icon> 我的打卡记录
        </el-button>
      </div>
    </div>

    <!-- ══ 打卡提交弹窗 ══════════════════════════════════════ -->
    <el-dialog
      v-model="checkinDialogVisible"
      width="560px"
      :show-close="false"
      :close-on-click-modal="false"
      class="heritage-dialog checkin-dialog"
    >
      <!-- 自定义顶部 -->
      <template #header>
        <div class="checkin-dialog-hero">
          <div class="checkin-dialog-hero-inner">
            <div class="checkin-dialog-hero-icon" aria-hidden="true"><el-icon :size="22"><Location /></el-icon></div>
            <div>
              <div class="checkin-dialog-hero-title">打卡非遗地点</div>
              <div class="checkin-dialog-hero-sub">上传现场照片，提交审核</div>
            </div>
          </div>
          <button class="checkin-dialog-close" @click="checkinDialogVisible = false">×</button>
        </div>
      </template>

      <div class="checkin-form-body">
        <!-- 地点名称 -->
        <div class="form-field">
          <div class="field-label"><span class="field-required">*</span> 非遗地点名称</div>
          <el-input
            v-model="checkinForm.site_name"
            placeholder="请输入您打卡的非遗地点名称"
            size="large"
            class="field-input"
          >
            <template #prefix><el-icon style="color:var(--color-accent-teal)"><Location /></el-icon></template>
          </el-input>
        </div>

        <!-- 坐标定位 -->
        <div class="form-field">
          <div class="field-label">坐标定位</div>
          <div class="coord-input-row">
            <el-input v-model.number="checkinForm.longitude" placeholder="经度" class="coord-input" />
            <span class="coord-sep-icon">⇌</span>
            <el-input v-model.number="checkinForm.latitude" placeholder="纬度" class="coord-input" />
            <el-button
              :loading="locating"
              @click="useCurrentLocation"
              class="locate-btn-fancy"
              type="primary"
              plain
            >
              <el-icon><Aim /></el-icon>
              {{ locating ? '定位中…' : '获取位置' }}
            </el-button>
          </div>
          <div class="field-tip">
            <el-icon style="font-size:11px"><InfoFilled /></el-icon>
            坐标将显示在地图上，方便其他用户找到该地点
          </div>
        </div>

        <!-- 地点地址 -->
        <div class="form-field">
          <div class="field-label">详细地址 <span class="field-optional">（可选）</span></div>
          <el-input
            v-model="checkinForm.site_address"
            placeholder="地址将在定位后自动填入，也可手动输入"
            class="field-input"
          />
        </div>

        <!-- 打卡感想 -->
        <div class="form-field">
          <div class="field-label">✍️ 打卡感想 <span class="field-optional">（可选）</span></div>
          <el-input
            v-model="checkinForm.description"
            type="textarea"
            :rows="3"
            placeholder="分享您在这里的所见所感、文化体验……"
            maxlength="300"
            show-word-limit
            class="field-textarea"
          />
        </div>

        <!-- 打卡照片 -->
        <div class="form-field">
          <div class="field-label"><span class="field-required">*</span> 打卡照片</div>
          <div
            class="photo-drop-zone"
            :class="{ 'has-photo': !!photoPreview }"
            @click="triggerPhotoUpload"
            @dragover.prevent
            @drop.prevent="onDrop"
          >
            <img v-if="photoPreview" :src="photoPreview" class="photo-preview" />
            <div v-else class="photo-placeholder">
              <div class="photo-icon-wrap">
                <el-icon size="36" style="color:var(--color-accent-teal)"><UploadFilled /></el-icon>
              </div>
              <p class="photo-main-text">点击或拖拽照片到此处</p>
              <p class="photo-sub-text">支持 JPG / PNG，大小 ≤ 5MB</p>
            </div>
            <div v-if="photoPreview" class="photo-change-mask">
              <el-icon><UploadFilled /></el-icon> 更换照片
            </div>
          </div>
          <input ref="photoInput" type="file" accept="image/*" hidden @change="onPhotoChange" />
          <div class="field-tip">
            <el-icon style="font-size:11px"><InfoFilled /></el-icon>
            照片需通过管理员审核后才会公开展示
          </div>
        </div>
      </div>

      <template #footer>
        <div class="dialog-footer-bar">
          <el-button class="footer-cancel-btn" @click="checkinDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="doSubmitCheckin" class="footer-submit-btn">
            <el-icon><Check /></el-icon>
            提交打卡
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- ══ 打卡详情弹窗（含评论）══════════════════════════════ -->
    <el-dialog
      v-model="detailVisible"
      width="620px"
      :show-close="false"
      :close-on-click-modal="true"
      class="detail-dialog"
    >
      <template #header>
        <div class="detail-dialog-hero" v-if="detailItem">
          <div class="detail-hero-bg" v-if="detailItem.photo_data"
            :style="{ backgroundImage: `url(${detailItem.photo_data})` }"
          ></div>
          <div class="detail-hero-bg-fallback" v-else></div>
          <div class="detail-hero-overlay"></div>
          <button class="detail-close-btn" @click="detailVisible = false">×</button>
          <div class="detail-hero-content">
            <div class="detail-hero-badge">非遗打卡</div>
            <h2 class="detail-hero-title">{{ detailItem.site_name }}</h2>
            <div class="detail-hero-meta">
              <span class="detail-hero-meta-item">
                <el-icon><User /></el-icon> {{ detailItem.username }}
              </span>
              <span class="detail-hero-meta-sep">·</span>
              <span class="detail-hero-meta-item">
                <el-icon><Clock /></el-icon> {{ detailItem.created_at }}
              </span>
              <template v-if="detailItem.site_address">
                <span class="detail-hero-meta-sep">·</span>
                <span class="detail-hero-meta-item">
                  <el-icon><Location /></el-icon> {{ detailItem.site_address }}
                </span>
              </template>
            </div>
          </div>
        </div>
      </template>

      <div v-if="detailItem" class="detail-dialog-body">
        <!-- 打卡感想 -->
        <div class="detail-feeling" v-if="detailItem.description">
          <div class="detail-feeling-label">✍️ 打卡感想</div>
          <p class="detail-feeling-text">{{ detailItem.description }}</p>
        </div>

        <!-- 照片全图 -->
        <div class="detail-photo-full" v-if="detailItem.photo_data">
          <img :src="detailItem.photo_data" alt="打卡照片" />
        </div>

        <!-- 评论区 -->
        <div class="detail-comment-section">
          <div class="detail-comment-header">
            <span class="detail-comment-title">
              <el-icon><ChatDotSquare /></el-icon> 评论
            </span>
            <span class="detail-comment-count">{{ comments.length }} 条</span>
          </div>

          <div class="detail-comment-list" v-loading="commentLoading">
            <div v-if="comments.length === 0 && !commentLoading" class="detail-no-comment">
              <span>暂无评论</span>
            </div>
            <div v-for="c in comments" :key="c.id" class="detail-comment-item">
              <el-avatar :size="32" class="detail-comment-avatar">
                {{ c.username?.charAt(0)?.toUpperCase() }}
              </el-avatar>
              <div class="detail-comment-right">
                <div class="detail-comment-meta">
                  <span class="detail-comment-user">{{ c.username }}</span>
                  <span class="detail-comment-time">{{ c.created_at }}</span>
                  <el-button
                    v-if="c.can_delete"
                    size="small" type="danger" text
                    @click="doDeleteComment(c.id)"
                    class="detail-comment-del"
                  >删除</el-button>
                </div>
                <div class="detail-comment-text">{{ c.content }}</div>
              </div>
            </div>
          </div>

          <div class="detail-comment-input-wrap">
            <el-input
              v-model="newComment"
              placeholder="说点什么…"
              maxlength="200"
              show-word-limit
              @keyup.enter="doAddComment"
              class="detail-comment-input"
            />
            <el-button
              type="primary"
              :loading="commenting"
              @click="doAddComment"
              class="detail-send-btn"
            >发送</el-button>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- ══ 我的打卡记录弹窗 ══════════════════════════════════ -->
    <el-dialog v-model="myCheckinVisible" title="我的打卡记录" width="600px" class="heritage-dialog">
      <div class="my-list" v-loading="myLoading">
        <div v-if="myCheckins.length === 0 && !myLoading" class="empty-state">
          <el-empty description="您还没有打卡记录" :image-size="60" />
        </div>
        <div v-for="item in myCheckins" :key="item.id" class="my-item">
          <div class="my-item-left">
            <img v-if="item.photo_data" :src="item.photo_data" class="my-thumb" />
            <div class="my-thumb no-img" v-else><el-icon><Picture /></el-icon></div>
          </div>
          <div class="my-item-right">
            <div class="my-site">{{ item.site_name }}</div>
            <div class="my-time">{{ item.created_at }}</div>
            <el-tag :type="statusType(item.status)" size="small">{{ statusLabel(item.status) }}</el-tag>
            <div class="my-reject" v-if="item.status === 2 && item.reject_reason">
              拒绝原因：{{ item.reject_reason }}
            </div>
          </div>
        </div>
      </div>
      <div class="pagination-bar" v-if="myTotalPages > 1">
        <el-pagination small background layout="prev, pager, next"
          :total="myTotalCount" :page-size="10"
          v-model:current-page="myCurrentPage"
          @current-change="loadMyCheckins"
        />
      </div>
    </el-dialog>

  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Location, Plus, PictureFilled, Search, ZoomIn, Picture,
  ChatDotSquare, Tickets, UploadFilled, Aim, User, Clock,
  Check, InfoFilled
} from '@element-plus/icons-vue'
import {
  submitCheckin, listCheckins, getCheckinPins, getMyCheckins,
  getComments, addComment, deleteComment, getIpLocation
} from '@/api'

// ── 地图 ────────────────────────────────────────────────────
let mapInstance = null
let infoWindow = null
const pinMarkers = []
let previewMarker = null

function escapeMapHtml(text) {
  return String(text ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function truncateCheckinDesc(text, maxLen = 10) {
  const t = String(text || '').trim()
  if (!t) return ''
  return t.length > maxLen ? `${t.slice(0, maxLen)}…` : t
}

function buildCheckinPopupHtml(pin) {
  const name = escapeMapHtml(pin.site_name)
  const addr = escapeMapHtml(pin.address)
  const addrBlock = addr
    ? `<p class="checkin-popup-addr">${addr}</p>`
    : ''
  const descSnippet = truncateCheckinDesc(pin.description)
  const descBlock = descSnippet
    ? `<p class="checkin-popup-desc"><span class="checkin-popup-desc-label">打卡感想</span>${escapeMapHtml(descSnippet)}</p>`
    : '<p class="checkin-popup-hint">用户非遗打卡点</p>'
  return `<div class="checkin-popup-card">
    <p class="checkin-popup-name">${name}</p>
    ${addrBlock}
    ${descBlock}
  </div>`
}

function clearPinMarkers() {
  if (!mapInstance) return
  pinMarkers.forEach((m) => mapInstance.remove(m))
  pinMarkers.length = 0
}

function clearPreviewMarker() {
  if (mapInstance && previewMarker) {
    mapInstance.remove(previewMarker)
    previewMarker = null
  }
}

function updatePreviewMarker(lng, lat) {
  if (!mapInstance || lng == null || lat == null) return
  clearPreviewMarker()
  const labelName = checkinForm.value.site_name?.trim()
    || (checkinForm.value.site_address || '').slice(0, 14)
    || '当前位置'
  previewMarker = new window.AMap.Marker({
    position: [lng, lat],
    zIndex: 300,
    title: labelName,
    icon: new window.AMap.Icon({
      size: new window.AMap.Size(28, 28),
      image: 'https://webapi.amap.com/theme/v1.3/markers/n/mark_b.png',
      imageSize: new window.AMap.Size(28, 28),
    }),
  })
  mapInstance.add(previewMarker)
}

function initMap(center = [116.397428, 39.90923]) {
  if (typeof window.AMap === 'undefined') return
  mapInstance = new window.AMap.Map('community-map', {
    zoom: 12,
    center,
    mapStyle: 'amap://styles/dark',
  })
  infoWindow = new window.AMap.InfoWindow({
    isCustom: true,
    offset: new window.AMap.Pixel(0, -28),
    autoMove: true,
  })
  loadMapPins()
}

async function loadMapPins() {
  if (!mapInstance) return
  clearPinMarkers()
  try {
    const res = await getCheckinPins()
    res.data.pins?.forEach((pin) => {
      const marker = new window.AMap.Marker({
        position: [pin.lng, pin.lat],
        zIndex: 120,
        title: pin.site_name || '打卡点',
        icon: new window.AMap.Icon({
          size: new window.AMap.Size(26, 26),
          image: 'https://webapi.amap.com/theme/v1.3/markers/n/mark_r.png',
          imageSize: new window.AMap.Size(26, 26),
        }),
      })
      marker.on('click', () => {
        infoWindow.setContent(buildCheckinPopupHtml(pin))
        infoWindow.open(mapInstance, marker.getPosition())
      })
      mapInstance.add(marker)
      pinMarkers.push(marker)
    })
  } catch { /* silent */ }
}

// ── 替换原来的 useCurrentLocation 函数 ──────────────────────────
async function useCurrentLocation() {
  locating.value = true

  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lng = parseFloat(pos.coords.longitude.toFixed(6))
        const lat = parseFloat(pos.coords.latitude.toFixed(6))
        checkinForm.value.longitude = lng
        checkinForm.value.latitude  = lat

        if (mapInstance) {
          mapInstance.setCenter([lng, lat])
          mapInstance.setZoom(15)
          updatePreviewMarker(lng, lat)
        }

        if (window.AMap) {
          window.AMap.plugin('AMap.Geocoder', () => {
            const geocoder = new window.AMap.Geocoder()
            geocoder.getAddress([lng, lat], (status, result) => {
              if (status === 'complete' && result.regeocode) {
                checkinForm.value.site_address = result.regeocode.formattedAddress
                const poi = result.regeocode.pois?.[0]
                if (!checkinForm.value.site_name?.trim() && poi?.name) {
                  checkinForm.value.site_name = poi.name
                }
                updatePreviewMarker(lng, lat)
              }
            })
          })
        }

        ElMessage.success(`定位成功：${lng}, ${lat}`)
        locating.value = false
      },
      (err) => {
        console.warn('浏览器定位失败：', err.message)
        fallbackIpLocation()
      },
      { enableHighAccuracy: true, timeout: 8000, maximumAge: 0 }
    )
  } else {
    fallbackIpLocation()
  }
}

// ── 新增：IP 降级定位 ─────────────────────────────────────────────
async function fallbackIpLocation() {
  try {
    const res = await getIpLocation(true)
    const { city, lng, lat } = res.data
    if (lng != null && lat != null) {
      checkinForm.value.longitude = parseFloat(Number(lng).toFixed(6))
      checkinForm.value.latitude  = parseFloat(Number(lat).toFixed(6))
      checkinForm.value.site_address = city || ''
      if (mapInstance) {
        mapInstance.setCenter([lng, lat])
        updatePreviewMarker(lng, lat)
      }
      ElMessage.warning(`已使用IP定位到：${city || '当前城市'}，坐标仅供参考`)
    } else {
      ElMessage.error('定位失败，请手动输入坐标')
    }
    locating.value = false
  } catch {
    ElMessage.error('定位服务不可用，请手动输入坐标')
    locating.value = false
  }
}

// ── 打卡列表 ─────────────────────────────────────────────────
const checkins    = ref([])
const listLoading = ref(false)
const searchSite  = ref('')
const currentPage = ref(1)
const totalCount  = ref(0)
const totalPages  = ref(0)

async function loadCheckins(page = 1) {
  listLoading.value = true
  currentPage.value = page
  try {
    const res = await listCheckins(page, searchSite.value)
    checkins.value  = res.data.data
    totalCount.value = res.data.total
    totalPages.value = res.data.pages
  } finally {
    listLoading.value = false
  }
}

// ── 打卡提交 ─────────────────────────────────────────────────
const checkinDialogVisible = ref(false)
const submitting           = ref(false)
const locating             = ref(false)
const photoInput           = ref(null)
const photoPreview         = ref(null)
const photoBase64          = ref(null)

const checkinForm = ref({
  site_name: '', site_address: '', longitude: null, latitude: null, description: ''
})

watch(
  () => [checkinForm.value.site_name, checkinForm.value.longitude, checkinForm.value.latitude],
  () => {
    const { longitude: lng, latitude: lat } = checkinForm.value
    if (lng != null && lat != null && checkinDialogVisible.value) {
      updatePreviewMarker(lng, lat)
    }
  },
)

function openCheckinDialog() {
  checkinForm.value = { site_name: '', site_address: '', longitude: null, latitude: null, description: '' }
  photoPreview.value = null
  photoBase64.value  = null
  clearPreviewMarker()
  checkinDialogVisible.value = true
}

function triggerPhotoUpload() { photoInput.value?.click() }

function onPhotoChange(e) {
  const file = e.target.files[0]
  if (!file) return
  if (file.size > 5 * 1024 * 1024) { ElMessage.error('图片大小不能超过 5MB'); return }
  const reader = new FileReader()
  reader.onload = (ev) => {
    photoPreview.value = ev.target.result
    photoBase64.value  = ev.target.result
  }
  reader.readAsDataURL(file)
}

function onDrop(e) {
  const file = e.dataTransfer?.files?.[0]
  if (file) onPhotoChange({ target: { files: [file] } })
}

async function doSubmitCheckin() {
  if (!checkinForm.value.site_name.trim()) { ElMessage.error('请填写打卡地点名称'); return }
  if (!photoBase64.value) { ElMessage.error('请上传打卡照片'); return }
  submitting.value = true
  try {
    const res = await submitCheckin({ ...checkinForm.value, photo_data: photoBase64.value })
    if (res.data.status === 'success') {
      ElMessage.success(res.data.msg)
      checkinDialogVisible.value = false
      clearPreviewMarker()
      loadCheckins(1)
      loadMapPins()
    } else {
      ElMessage.error(res.data.msg)
    }
  } finally {
    submitting.value = false
  }
}

// ── 详情 + 评论 ──────────────────────────────────────────────
const detailVisible  = ref(false)
const detailItem     = ref(null)
const comments       = ref([])
const commentLoading = ref(false)
const newComment     = ref('')
const commenting     = ref(false)

async function openDetail(item) {
  detailItem.value = item
  detailVisible.value = true
  commentLoading.value = true
  comments.value = []
  newComment.value = ''
  try {
    const res = await getComments(item.id)
    comments.value = res.data.data
  } finally {
    commentLoading.value = false
  }
}

async function doAddComment() {
  if (!newComment.value.trim()) return
  commenting.value = true
  try {
    const res = await addComment(detailItem.value.id, newComment.value.trim())
    if (res.data.status === 'success') {
      comments.value.push(res.data.comment)
      newComment.value = ''
      detailItem.value.comment_count = (detailItem.value.comment_count || 0) + 1
    }
  } finally {
    commenting.value = false
  }
}

async function doDeleteComment(cid) {
  await ElMessageBox.confirm('确定删除该评论？', '提示', { type: 'warning' })
  try {
    await deleteComment(cid)
    comments.value = comments.value.filter(c => c.id !== cid)
    ElMessage.success('评论已删除')
  } catch {}
}

// ── 我的打卡 ─────────────────────────────────────────────────
const myCheckinVisible = ref(false)
const myCheckins       = ref([])
const myLoading        = ref(false)
const myCurrentPage    = ref(1)
const myTotalCount     = ref(0)
const myTotalPages     = ref(0)

async function loadMyCheckins(page = 1) {
  myLoading.value = true
  try {
    const res = await getMyCheckins(page)
    myCheckins.value  = res.data.data
    myTotalCount.value = res.data.total
    myTotalPages.value = res.data.pages
  } finally {
    myLoading.value = false
  }
}

const statusLabel = (s) => ({ 0: '待审核', 1: '已通过', 2: '已拒绝' }[s] || '未知')
const statusType  = (s) => ({ 0: 'warning', 1: 'success', 2: 'danger' }[s] || 'info')

// ── 挂载高德地图 ─────────────────────────────────────────────
onMounted(async () => {
  loadCheckins()
  loadMyCheckins()
  await nextTick()
  if (typeof window.AMap !== 'undefined') {
    initMap()
  } else {
    // 动态加载高德地图 JS
    const key = window.__AMAP_KEY__ || '6093701a8f925e7ac1af1156c7c5c30a'
    const script = document.createElement('script')
    script.src = `https://webapi.amap.com/maps?v=2.0&key=${key}`
    script.onload = () => initMap()
    document.head.appendChild(script)
  }
})
</script>

<style scoped>
.community-root {
  display: flex; height: 100%; overflow: hidden; gap: 0;
  background: var(--color-bg-base);
}

/* ── 左侧地图面板 ── */
.left-panel {
  width: 480px; flex-shrink: 0;
  display: flex; flex-direction: column;
  border-right: 1px solid var(--color-border);
}
.map-box { flex: 1; min-height: 0; }
.map-legend {
  display: flex; align-items: center; gap: 12px;
  padding: 8px 16px; font-size: 12px; color: var(--color-text-muted);
  background: var(--color-bg-panel); border-top: 1px solid var(--color-border);
  flex-shrink: 0;
}
.legend-dot {
  width: 10px; height: 10px; border-radius: 50%; display: inline-block;
}
.legend-dot.official { background: var(--color-accent-teal); }
.legend-dot.user      { background: #e74c3c; }

/* ── 右侧广场面板 ── */
.right-panel {
  flex: 1; display: flex; flex-direction: column; min-width: 0; overflow: hidden;
}
.panel-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px; flex-shrink: 0;
  background: var(--color-bg-panel); border-bottom: 1px solid var(--color-border);
}
.panel-title {
  display: flex; align-items: center; gap: 6px;
  font-family: var(--font-serif); font-size: 15px; color: var(--color-text-primary);
}

/* ── 打卡列表 ── */
.checkin-list {
  flex: 1; overflow-y: auto; padding: 12px;
  display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px; align-content: start;
}
.checkin-card {
  background: var(--color-bg-card); border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  overflow: hidden; cursor: pointer; transition: all 0.2s;
}
.checkin-card:hover { transform: translateY(-2px); border-color: var(--color-accent-teal); }

.card-photo {
  height: 150px; position: relative; overflow: hidden;
  background: var(--color-bg-hover);
}
.card-photo img { width: 100%; height: 100%; object-fit: cover; }
.card-overlay {
  position: absolute; inset: 0; background: rgba(0,0,0,0.4);
  display: flex; align-items: center; justify-content: center;
  opacity: 0; transition: opacity 0.2s; color: #fff; font-size: 24px;
}
.card-photo:hover .card-overlay { opacity: 1; }
.no-photo {
  display: flex; align-items: center; justify-content: center;
  color: var(--color-text-muted);
}

.card-body { padding: 10px 12px; }
.card-site {
  display: flex; align-items: center; gap: 5px;
  font-size: 13px; font-weight: 600; color: var(--color-accent-gold);
  margin-bottom: 4px;
}
.card-desc {
  font-size: 12px; color: var(--color-text-secondary);
  line-height: 1.5; margin-bottom: 8px;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.card-meta {
  display: flex; align-items: center; gap: 5px;
  font-size: 11px; color: var(--color-text-muted);
}
.meta-avatar { background: var(--color-accent-teal) !important; color: #fff !important; flex-shrink:0; }
.meta-user { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.meta-comment { margin-left: auto; }
.meta-comment-cnt { min-width: 16px; }

/* ── 分页 ── */
.pagination-bar {
  display: flex; justify-content: center; padding: 10px;
  border-top: 1px solid var(--color-border); flex-shrink: 0;
}
.my-checkin-btn {
  padding: 6px 12px; flex-shrink: 0;
  border-top: 1px solid var(--color-border);
  text-align: right;
}

/* ── 打卡表单字段 ── */
.coord-row { display: flex; align-items: center; flex-wrap: wrap; gap: 4px; }
.tip-text { font-size: 11px; color: var(--color-text-muted); margin-top: 4px; }

.photo-upload-area {
  width: 100%; height: 160px; border: 2px dashed var(--color-border);
  border-radius: var(--radius-md); cursor: pointer; overflow: hidden;
  display: flex; align-items: center; justify-content: center;
  transition: border-color 0.2s; background: var(--color-bg-hover);
}
.photo-upload-area:hover { border-color: var(--color-accent-teal); }
.photo-preview { width: 100%; height: 100%; object-fit: cover; }
.upload-placeholder {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  color: var(--color-text-muted); font-size: 13px;
}
.upload-hint { font-size: 11px; }

/* ── 详情弹窗 ── */
.detail-body { display: flex; flex-direction: column; gap: 14px; }
.detail-photo img { width: 100%; max-height: 300px; object-fit: cover; border-radius: var(--radius-md); }
.detail-info { display: flex; flex-direction: column; gap: 6px; }
.info-row {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; color: var(--color-text-secondary);
}
.info-divider { color: var(--color-text-muted); }
.detail-desc {
  font-size: 14px; color: var(--color-text-primary); line-height: 1.7;
  padding: 8px 12px; background: var(--color-bg-hover); border-radius: var(--radius-sm);
}

/* ── 评论区 ── */
.comment-section { display: flex; flex-direction: column; gap: 10px; }
.comment-title {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; font-weight: 600; color: var(--color-text-primary);
  padding-bottom: 6px; border-bottom: 1px solid var(--color-border);
}
.comment-list { max-height: 220px; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; }
.no-comment { text-align: center; font-size: 12px; color: var(--color-text-muted); padding: 16px; }
.comment-item { display: flex; gap: 8px; }
.comment-avatar { background: var(--color-accent-gold) !important; color:#1c1f27 !important; font-size:12px; flex-shrink:0; }
.comment-content { flex: 1; min-width: 0; }
.comment-header { display: flex; align-items: center; gap: 6px; margin-bottom: 3px; }
.comment-user { font-size: 12px; font-weight: 600; color: var(--color-accent-teal); }
.comment-time { font-size: 11px; color: var(--color-text-muted); }
.comment-text { font-size: 13px; color: var(--color-text-secondary); line-height: 1.5; word-break: break-all; }
.comment-input-row { display: flex; gap: 8px; align-items: center; }

/* ── 我的打卡列表 ── */
.my-list { display: flex; flex-direction: column; gap: 10px; max-height: 460px; overflow-y: auto; }
.my-item { display: flex; gap: 12px; padding: 10px; background: var(--color-bg-hover); border-radius: var(--radius-sm); }
.my-thumb { width: 64px; height: 64px; object-fit: cover; border-radius: var(--radius-sm); flex-shrink: 0; }
.my-thumb.no-img {
  width: 64px; height: 64px; background: var(--color-bg-card);
  border-radius: var(--radius-sm); display: flex; align-items: center; justify-content: center;
  color: var(--color-text-muted); flex-shrink: 0;
}
.my-item-right { display: flex; flex-direction: column; gap: 4px; }
.my-site { font-size: 14px; font-weight: 600; color: var(--color-text-primary); }
.my-time { font-size: 12px; color: var(--color-text-muted); }
.my-reject { font-size: 12px; color: var(--color-accent-red); margin-top: 2px; }

.empty-state { grid-column: 1 / -1; padding: 40px 0; }

/* ── 通用弹窗样式覆盖（详情、我的打卡等） ── */
/* heritage-dialog 覆盖已移至全局 style 块 */
</style>

<!-- ══ 打卡弹窗全局样式（必须全局，Dialog teleport 到 body 外，scoped 打不到）══ -->
<style>
/* ── 提交打卡弹窗壳：覆盖所有白色来源 ── */

.el-overlay:has(.checkin-dialog) {
  background-color: rgba(0, 0, 0, 0.72) !important;
}
.checkin-dialog.el-overlay-dialog {
  background: transparent !important;
}

/* 用 :has() 从 el-overlay 向下命中，确保 CSS 变量和 padding 都被覆盖 */
.el-overlay:has(.checkin-dialog) .el-dialog {
  --el-dialog-bg-color: #141820 !important;
  --el-dialog-padding-primary: 0px !important;
  --el-dialog-border-radius: 20px !important;
  background: #141820 !important;
  background-color: #141820 !important;
  padding: 0 !important;
  border: 1px solid rgba(61,158,140,0.35) !important;
  border-radius: 20px !important;
  overflow: hidden !important;
  box-shadow: 0 32px 80px rgba(0,0,0,0.75) !important;
}
.el-overlay:has(.checkin-dialog) .el-dialog__header { padding: 0 !important; margin: 0 !important; background: transparent !important; }
.el-overlay:has(.checkin-dialog) .el-dialog__body   { padding: 0 !important; background: #141820 !important; }
.el-overlay:has(.checkin-dialog) .el-dialog__footer { padding: 0 !important; background: transparent !important; }

/* 兼容旧选择器写法（双重保险） */
.checkin-dialog.el-overlay-dialog .el-dialog {
  --el-dialog-bg-color: #141820 !important;
  --el-dialog-padding-primary: 0px !important;
  background: #141820 !important;
  background-color: #141820 !important;
  padding: 0 !important;
  border: 1px solid rgba(61,158,140,0.35) !important;
  border-radius: 20px !important;
  overflow: hidden !important;
  box-shadow: 0 32px 80px rgba(0,0,0,0.75) !important;
}
.checkin-dialog.el-overlay-dialog .el-dialog__header { padding: 0 !important; margin: 0 !important; background: transparent !important; }
.checkin-dialog.el-overlay-dialog .el-dialog__body   { padding: 0 !important; background: #141820 !important; }
.checkin-dialog.el-overlay-dialog .el-dialog__footer { padding: 0 !important; background: transparent !important; }

/* ── 输入框全部深色 ── */
.checkin-dialog.el-overlay-dialog .el-input__wrapper,
.checkin-dialog .el-input__wrapper {
  background: #1e2433 !important;
  box-shadow: 0 0 0 1px #2d3548 !important;
  border-radius: 8px !important;
}
.checkin-dialog.el-overlay-dialog .el-input__wrapper:hover,
.checkin-dialog .el-input__wrapper:hover {
  box-shadow: 0 0 0 1px #3d9e8c !important;
}
.checkin-dialog.el-overlay-dialog .el-input__wrapper.is-focus,
.checkin-dialog .el-input__wrapper.is-focus {
  box-shadow: 0 0 0 2px rgba(61,158,140,0.45) !important;
}
.checkin-dialog.el-overlay-dialog .el-input__inner,
.checkin-dialog .el-input__inner {
  color: #d4dae8 !important;
  background: transparent !important;
}
.checkin-dialog .el-input__inner::placeholder { color: #4a5568 !important; }

.checkin-dialog.el-overlay-dialog .el-textarea__inner,
.checkin-dialog .el-textarea__inner {
  background: #1e2433 !important;
  color: #d4dae8 !important;
  box-shadow: 0 0 0 1px #2d3548 !important;
  border-radius: 8px !important;
  resize: none !important;
}
.checkin-dialog.el-overlay-dialog .el-textarea__inner:hover,
.checkin-dialog .el-textarea__inner:hover {
  box-shadow: 0 0 0 1px #3d9e8c !important;
}
.checkin-dialog.el-overlay-dialog .el-textarea__inner:focus,
.checkin-dialog .el-textarea__inner:focus {
  box-shadow: 0 0 0 2px rgba(61,158,140,0.45) !important;
}
.checkin-dialog .el-textarea__inner::placeholder { color: #4a5568 !important; }
.checkin-dialog .el-input__count,
.checkin-dialog .el-textarea .el-input__count { color: #4a5568 !important; background: transparent !important; }

/* ── 英雄顶部 ── */
.checkin-dialog-hero {
  position: relative;
  padding: 26px 28px 22px;
  background: linear-gradient(135deg, #1a2535 0%, #162420 60%, #1a1e2a 100%);
  border-bottom: 1px solid rgba(61,158,140,0.2);
  overflow: hidden;
}
.checkin-dialog-hero::before {
  content: '';
  position: absolute; top: -40px; right: -40px;
  width: 160px; height: 160px; border-radius: 50%;
  background: radial-gradient(circle, rgba(61,158,140,0.18) 0%, transparent 70%);
  pointer-events: none;
}
.checkin-dialog-hero::after {
  content: '';
  position: absolute; bottom: -20px; left: 30px;
  width: 100px; height: 100px; border-radius: 50%;
  background: radial-gradient(circle, rgba(192,161,80,0.07) 0%, transparent 70%);
  pointer-events: none;
}
.checkin-dialog-hero-inner {
  position: relative; display: flex; align-items: center; gap: 16px;
}
.checkin-dialog-hero-icon {
  width: 52px; height: 52px; border-radius: 14px; flex-shrink: 0;
  background: linear-gradient(135deg, rgba(61,158,140,0.3), rgba(61,158,140,0.1));
  border: 1px solid rgba(61,158,140,0.35);
  display: flex; align-items: center; justify-content: center;
  font-size: 26px;
  box-shadow: 0 4px 16px rgba(61,158,140,0.2);
}
.checkin-dialog-hero-title {
  font-size: 18px; font-weight: 700; color: #eaf0f8;
  letter-spacing: 0.3px; margin-bottom: 4px;
  font-family: 'STSong', 'SimSun', serif;
}
.checkin-dialog-hero-sub {
  font-size: 12px; color: #6b7a99; line-height: 1.4;
}
.checkin-dialog-close {
  position: absolute; top: 18px; right: 20px;
  width: 28px; height: 28px; border-radius: 8px;
  border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.04);
  color: #6b7a99; font-size: 16px; line-height: 1;
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  transition: all 0.18s;
}
.checkin-dialog-close:hover { background: rgba(192,57,43,0.4); color: #fff; border-color: transparent; }

/* ── 表单主体 ── */
.checkin-form-body {
  padding: 20px 28px;
  display: flex; flex-direction: column; gap: 16px;
  max-height: 55vh; overflow-y: auto;
  background: #141820;
}
.checkin-form-body::-webkit-scrollbar { width: 3px; }
.checkin-form-body::-webkit-scrollbar-track { background: transparent; }
.checkin-form-body::-webkit-scrollbar-thumb { background: rgba(61,158,140,0.25); border-radius: 2px; }

/* ── 字段 ── */
.form-field { display: flex; flex-direction: column; gap: 7px; }
.field-label {
  font-size: 12px; font-weight: 600; color: #8899bb;
  display: flex; align-items: center; gap: 5px;
  text-transform: uppercase; letter-spacing: 0.6px;
}
.field-required { color: #e05c5c; font-size: 13px; text-transform: none; }
.field-optional { font-size: 11px; color: #4a5568; font-weight: 400; text-transform: none; letter-spacing: 0; }
.field-tip {
  display: flex; align-items: center; gap: 5px;
  font-size: 11px; color: #4a5568; line-height: 1.5;
}

/* ── 坐标行 ── */
.coord-input-row { display: flex; align-items: center; gap: 8px; }
.coord-input { width: 108px !important; flex-shrink: 0; }
.coord-sep-icon { color: #3d9e8c; font-size: 13px; font-weight: 600; }
.locate-btn-fancy { flex-shrink: 0; }

/* ── 照片上传 ── */
.photo-drop-zone {
  position: relative; width: 100%; height: 148px;
  border: 1.5px dashed rgba(61,158,140,0.3);
  border-radius: 12px; cursor: pointer; overflow: hidden;
  display: flex; align-items: center; justify-content: center;
  background: #1a1f2e;
  transition: all 0.2s;
}
.photo-drop-zone:hover {
  border-color: #3d9e8c;
  background: rgba(61,158,140,0.06);
  box-shadow: 0 0 0 3px rgba(61,158,140,0.08);
}
.photo-drop-zone.has-photo { border-style: solid; border-color: rgba(61,158,140,0.4); }
.photo-placeholder { display: flex; flex-direction: column; align-items: center; gap: 10px; }
.photo-icon-wrap {
  width: 48px; height: 48px; border-radius: 12px;
  background: rgba(61,158,140,0.12); border: 1px solid rgba(61,158,140,0.2);
  display: flex; align-items: center; justify-content: center;
}
.photo-main-text { font-size: 13px; color: #8899bb; font-weight: 500; }
.photo-sub-text  { font-size: 11px; color: #4a5568; margin-top: -4px; }
.photo-preview   { width: 100%; height: 100%; object-fit: cover; }
.photo-change-mask {
  position: absolute; inset: 0;
  background: rgba(0,0,0,0.55);
  display: flex; align-items: center; justify-content: center; gap: 6px;
  color: #fff; font-size: 13px; font-weight: 600;
  opacity: 0; transition: opacity 0.18s;
}
.photo-drop-zone:hover .photo-change-mask { opacity: 1; }

/* ── 底部栏 ── */
.dialog-footer-bar {
  display: flex; align-items: center; justify-content: flex-end; gap: 10px;
  padding: 14px 28px;
  background: #111419;
  border-top: 1px solid rgba(255,255,255,0.06);
}
.footer-cancel-btn { min-width: 80px; }
.footer-submit-btn { min-width: 110px; }
</style>

<!-- ══ 打卡详情弹窗全局样式（teleport到body，必须全局）══ -->
<style>
/* ── 弹窗壳：覆盖所有可能的白色来源 ── */

/* 1. el-overlay 本身（半透明遮罩层） */
.el-overlay:has(.detail-dialog) {
  background-color: rgba(0, 0, 0, 0.72) !important;
}

/* 2. el-overlay-dialog 容器 */
.detail-dialog.el-overlay-dialog {
  background: transparent !important;
}

/* 3. 用 :has() 从 el-overlay 向下命中，确保 CSS 变量和 padding 都被覆盖（白边根本修复） */
.el-overlay:has(.detail-dialog) .el-dialog {
  --el-dialog-bg-color: #141820 !important;
  --el-dialog-padding-primary: 0px !important;
  --el-dialog-border-radius: 18px !important;
  background: #141820 !important;
  background-color: #141820 !important;
  padding: 0 !important;
  margin: 15vh auto 50px !important;
  border: 1px solid rgba(61,158,140,0.3) !important;
  border-radius: 18px !important;
  overflow: hidden !important;
  box-shadow: 0 32px 80px rgba(0,0,0,0.8) !important;
}

/* 4. 兼容旧选择器（双重保险） */
.detail-dialog.el-overlay-dialog .el-dialog {
  --el-dialog-bg-color: #141820 !important;
  --el-dialog-padding-primary: 0px !important;
  --el-dialog-border-radius: 18px !important;
  background: #141820 !important;
  background-color: #141820 !important;
  padding: 0 !important;
  margin: 15vh auto 50px !important;
  border: 1px solid rgba(61,158,140,0.3) !important;
  border-radius: 18px !important;
  overflow: hidden !important;
  box-shadow: 0 32px 80px rgba(0,0,0,0.8) !important;
}

/* 5. header / body / footer 各自清零 */
.el-overlay:has(.detail-dialog) .el-dialog__header,
.detail-dialog.el-overlay-dialog .el-dialog__header {
  padding: 0 !important;
  margin: 0 !important;
  background: transparent !important;
  border-radius: 18px 18px 0 0 !important;
  overflow: hidden !important;
}
.el-overlay:has(.detail-dialog) .el-dialog__body,
.detail-dialog.el-overlay-dialog .el-dialog__body {
  padding: 0 !important;
  background: #141820 !important;
}
.el-overlay:has(.detail-dialog) .el-dialog__footer,
.detail-dialog.el-overlay-dialog .el-dialog__footer {
  padding: 0 !important;
  background: transparent !important;
}

/* ── 英雄封面区 ── */
.detail-dialog-hero {
  position: relative;
  height: 200px;
  overflow: hidden;
  border-radius: 0;
}
.detail-hero-bg {
  position: absolute; inset: 0;
  background-size: cover;
  background-position: center;
  filter: blur(2px) brightness(0.55);
  transform: scale(1.05);
}
.detail-hero-bg-fallback {
  position: absolute; inset: 0;
  background: linear-gradient(135deg, #1a2535 0%, #162420 50%, #1a1530 100%);
}
.detail-hero-overlay {
  position: absolute; inset: 0;
  background: linear-gradient(
    to bottom,
    rgba(10,12,18,0.2) 0%,
    rgba(10,12,18,0.5) 60%,
    rgba(20,24,32,0.95) 100%
  );
}
.detail-close-btn {
  position: absolute; top: 14px; right: 16px; z-index: 10;
  width: 30px; height: 30px; border-radius: 8px;
  border: 1px solid rgba(255,255,255,0.15);
  background: rgba(0,0,0,0.35);
  color: rgba(255,255,255,0.8); font-size: 18px;
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  transition: all 0.18s; backdrop-filter: blur(4px);
}
.detail-close-btn:hover { background: rgba(192,57,43,0.6); color: #fff; border-color: transparent; }

.detail-hero-content {
  position: absolute; bottom: 0; left: 0; right: 0;
  padding: 0 24px 20px;
  z-index: 5;
}
.detail-hero-badge {
  display: inline-flex; align-items: center;
  font-size: 11px; color: #3d9e8c; font-weight: 600; letter-spacing: 0.5px;
  background: rgba(61,158,140,0.15); border: 1px solid rgba(61,158,140,0.3);
  padding: 2px 10px; border-radius: 20px; margin-bottom: 8px;
}
.detail-hero-title {
  font-family: 'STSong', 'Noto Serif SC', serif;
  font-size: 22px; font-weight: 700; color: #eaf0f8;
  letter-spacing: 0.5px; margin: 0 0 10px;
  text-shadow: 0 2px 8px rgba(0,0,0,0.6);
}
.detail-hero-meta {
  display: flex; align-items: center; flex-wrap: wrap; gap: 6px;
  font-size: 12px; color: rgba(180,195,220,0.85);
}
.detail-hero-meta-item {
  display: inline-flex; align-items: center; gap: 4px;
}
.detail-hero-meta-sep { color: rgba(180,195,220,0.4); }

/* ── 弹窗主体 ── */
.detail-dialog-body {
  padding: 20px 24px;
  display: flex; flex-direction: column; gap: 16px;
  max-height: 55vh; overflow-y: auto;
  background: #141820;
}
.detail-dialog-body::-webkit-scrollbar { width: 3px; }
.detail-dialog-body::-webkit-scrollbar-thumb { background: rgba(61,158,140,0.2); border-radius: 2px; }

/* ── 打卡感想 ── */
.detail-feeling {
  background: rgba(61,158,140,0.06);
  border: 1px solid rgba(61,158,140,0.15);
  border-left: 3px solid #3d9e8c;
  border-radius: 0 10px 10px 0;
  padding: 12px 16px;
}
.detail-feeling-label {
  font-size: 11px; font-weight: 600; color: #3d9e8c;
  text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;
}
.detail-feeling-text {
  font-size: 14px; color: #c8d0e0; line-height: 1.75; margin: 0;
}

/* ── 照片全图 ── */
.detail-photo-full {
  border-radius: 12px; overflow: hidden;
  border: 1px solid rgba(61,158,140,0.2);
}
.detail-photo-full img {
  width: 100%; display: block;
  max-height: 320px; object-fit: cover;
}

/* ── 评论区 ── */
.detail-comment-section {
  display: flex; flex-direction: column; gap: 12px;
}
.detail-comment-header {
  display: flex; align-items: center; justify-content: space-between;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(255,255,255,0.07);
}
.detail-comment-title {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; font-weight: 600; color: #c8d0e0;
}
.detail-comment-count {
  font-size: 11px; color: #4a5568;
  background: rgba(255,255,255,0.05);
  padding: 2px 8px; border-radius: 10px;
}
.detail-comment-list {
  display: flex; flex-direction: column; gap: 10px;
  max-height: 200px; overflow-y: auto;
}
.detail-comment-list::-webkit-scrollbar { width: 3px; }
.detail-comment-list::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius: 2px; }
.detail-no-comment {
  text-align: center; padding: 20px;
  font-size: 13px; color: #4a5568;
}
.detail-comment-item {
  display: flex; gap: 10px; align-items: flex-start;
}
.detail-comment-avatar {
  background: linear-gradient(135deg, #3d9e8c, #2a7a6e) !important;
  color: #fff !important; font-size: 13px; flex-shrink: 0;
}
.detail-comment-right { flex: 1; min-width: 0; }
.detail-comment-meta {
  display: flex; align-items: center; gap: 8px; margin-bottom: 4px;
}
.detail-comment-user {
  font-size: 12px; font-weight: 700; color: #3d9e8c;
}
.detail-comment-time {
  font-size: 11px; color: #4a5568;
}
.detail-comment-del {
  margin-left: auto; padding: 0 !important; height: auto !important;
  font-size: 11px !important;
}
.detail-comment-text {
  font-size: 13px; color: #98a0b8; line-height: 1.6;
  background: rgba(255,255,255,0.03);
  border-radius: 0 8px 8px 8px;
  padding: 8px 12px;
  word-break: break-all;
}

/* ── 评论输入框 ── */
.detail-comment-input-wrap {
  display: flex; gap: 8px; align-items: center;
  padding: 10px 14px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 12px;
}
.detail-comment-input-wrap .el-input__wrapper {
  background: transparent !important;
  box-shadow: none !important;
  padding: 0 !important;
}
.detail-comment-input-wrap .el-input__inner {
  color: #c8d0e0 !important;
  font-size: 13px !important;
}
.detail-comment-input-wrap .el-input__inner::placeholder { color: #4a5568 !important; }
.detail-comment-input-wrap .el-input__count { color: #4a5568 !important; background: transparent !important; }
.detail-send-btn { flex-shrink: 0; }

/* ══════════════════════════════════════════════════
   全局强杀：所有 heritage-dialog / detail-dialog
   el-overlay + el-dialog 全链路深色覆盖
   ══════════════════════════════════════════════════ */

/* 遮罩层 */
.el-overlay:has(.heritage-dialog),
.el-overlay:has(.detail-dialog) {
  background-color: rgba(0, 0, 0, 0.72) !important;
}

/* overlay-dialog 容器本身 */
.heritage-dialog.el-overlay-dialog,
.detail-dialog.el-overlay-dialog {
  background: transparent !important;
}

/* 用 :has() 从 el-overlay 向下命中（白边根本修复：CSS变量 + padding 双杀） */
.el-overlay:has(.heritage-dialog) .el-dialog,
.el-overlay:has(.detail-dialog) .el-dialog {
  --el-dialog-bg-color: #141820 !important;
  --el-dialog-padding-primary: 0px !important;
  --el-dialog-border-radius: 18px !important;
  background: #141820 !important;
  background-color: #141820 !important;
  padding: 0 !important;
  border: 1px solid rgba(61,158,140,0.25) !important;
  border-radius: 18px !important;
  overflow: hidden !important;
  box-shadow: 0 24px 64px rgba(0,0,0,0.8) !important;
}

/* 兼容旧选择器（双重保险） */
.heritage-dialog.el-overlay-dialog .el-dialog,
.detail-dialog.el-overlay-dialog .el-dialog {
  --el-dialog-bg-color: #141820 !important;
  --el-dialog-padding-primary: 0px !important;
  --el-dialog-border-radius: 18px !important;
  background: #141820 !important;
  background-color: #141820 !important;
  padding: 0 !important;
  border: 1px solid rgba(61,158,140,0.25) !important;
  border-radius: 18px !important;
  overflow: hidden !important;
  box-shadow: 0 24px 64px rgba(0,0,0,0.8) !important;
}

/* header / body / footer 各自清零 */
.el-overlay:has(.heritage-dialog) .el-dialog__header,
.el-overlay:has(.detail-dialog) .el-dialog__header,
.heritage-dialog.el-overlay-dialog .el-dialog__header,
.detail-dialog.el-overlay-dialog .el-dialog__header {
  padding: 0 !important;
  margin: 0 !important;
  background: #141820 !important;
}
.el-overlay:has(.heritage-dialog) .el-dialog__body,
.el-overlay:has(.detail-dialog) .el-dialog__body,
.heritage-dialog.el-overlay-dialog .el-dialog__body,
.detail-dialog.el-overlay-dialog .el-dialog__body {
  padding: 0 !important;
  background: #141820 !important;
}
.el-overlay:has(.heritage-dialog) .el-dialog__footer,
.el-overlay:has(.detail-dialog) .el-dialog__footer,
.heritage-dialog.el-overlay-dialog .el-dialog__footer,
.detail-dialog.el-overlay-dialog .el-dialog__footer {
  padding: 0 !important;
  background: #141820 !important;
}

/* 标题文字 */
.heritage-dialog.el-overlay-dialog .el-dialog__title,
.detail-dialog.el-overlay-dialog .el-dialog__title {
  color: #eaf0f8 !important;
  font-family: 'STSong', 'Noto Serif SC', serif;
}

/* 所有弹窗内 input 深色 */
.heritage-dialog.el-overlay-dialog .el-input__wrapper,
.detail-dialog.el-overlay-dialog .el-input__wrapper {
  background: #1e2433 !important;
  box-shadow: 0 0 0 1px #2d3548 !important;
  border-radius: 8px !important;
}
.heritage-dialog.el-overlay-dialog .el-input__wrapper:hover,
.detail-dialog.el-overlay-dialog .el-input__wrapper:hover {
  box-shadow: 0 0 0 1px #3d9e8c !important;
}
.heritage-dialog.el-overlay-dialog .el-input__inner,
.detail-dialog.el-overlay-dialog .el-input__inner {
  color: #d4dae8 !important;
  background: transparent !important;
}
.heritage-dialog.el-overlay-dialog .el-input__inner::placeholder,
.detail-dialog.el-overlay-dialog .el-input__inner::placeholder { color: #4a5568 !important; }
.heritage-dialog.el-overlay-dialog .el-input__count,
.detail-dialog.el-overlay-dialog .el-input__count { color: #4a5568 !important; background: transparent !important; }

/* 我的打卡弹窗 el-tag 深色 */
.heritage-dialog.el-overlay-dialog .el-tag {
  background: rgba(61,158,140,0.12) !important;
  border-color: rgba(61,158,140,0.25) !important;
}

/* ══ 打卡地图：标点标签 + 点击弹窗（深色底高对比，覆盖高德默认浅色标签）══ */
.amap-marker-label {
  border: none !important;
  background: transparent !important;
  padding: 0 !important;
}

.checkin-marker-label {
  display: inline-block;
  max-width: 200px;
  padding: 5px 12px;
  background: rgba(14, 16, 21, 0.94) !important;
  border: 1px solid rgba(201, 168, 76, 0.55);
  border-radius: 8px;
  box-shadow:
    0 4px 18px rgba(0, 0, 0, 0.65),
    0 0 0 1px rgba(255, 255, 255, 0.06) inset;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.checkin-marker-label.is-preview {
  border-color: rgba(61, 158, 140, 0.65);
  box-shadow:
    0 4px 18px rgba(61, 158, 140, 0.25),
    0 0 0 1px rgba(61, 158, 140, 0.2) inset;
}

.checkin-marker-label__text {
  font-size: 12px;
  font-weight: 700;
  color: #e8c96a !important;
  letter-spacing: 0.3px;
  font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
  line-height: 1.35;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.8);
}

.checkin-marker-label.is-preview .checkin-marker-label__text {
  color: #7ee8d8 !important;
}

.checkin-popup-card {
  min-width: 200px;
  max-width: 280px;
  padding: 12px 14px;
  background: linear-gradient(145deg, rgba(28, 31, 39, 0.98), rgba(18, 20, 28, 0.98));
  border: 1px solid rgba(61, 158, 140, 0.4);
  border-radius: 12px;
  box-shadow: 0 10px 32px rgba(0, 0, 0, 0.55);
  font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.checkin-popup-name {
  margin: 0 0 6px;
  font-size: 14px;
  font-weight: 700;
  color: #e8c96a;
  line-height: 1.4;
}

.checkin-popup-addr {
  margin: 0 0 8px;
  font-size: 11px;
  color: rgba(200, 210, 230, 0.92);
  line-height: 1.55;
  display: flex;
  align-items: flex-start;
  gap: 4px;
}

.checkin-popup-desc {
  margin: 0;
  padding-top: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  font-size: 12px;
  color: rgba(220, 225, 240, 0.9);
  line-height: 1.55;
}
.checkin-popup-desc-label {
  display: inline-block;
  margin-right: 6px;
  font-size: 10px;
  color: rgba(61, 158, 140, 0.95);
  font-weight: 600;
}
.checkin-popup-hint {
  margin: 0;
  padding-top: 6px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  font-size: 10px;
  color: rgba(138, 143, 168, 0.95);
}

#community-map .amap-info-content {
  padding: 0 !important;
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}

#community-map .amap-info-sharp,
#community-map .amap-info-close {
  display: none !important;
}

</style>