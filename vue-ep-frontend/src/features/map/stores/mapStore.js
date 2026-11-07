// stores/mapStore.js
// 跨页面共享地图状态：识图 / Agent 对话结果 → 地图页标点与高亮
import { defineStore } from 'pinia'

export const useMapStore = defineStore('map', {
  state: () => ({
    pendingMarkers: [],
    pendingCity: '',
    pendingKeyword: '',
    /** 'source' | 'agent' */
    pendingSource: '',
    hasPendingUpdate: false,
    // Agent 最近一次地标（用于再次点击「打开地图」）
    lastAgentMarkers: [],
    lastAgentCity: '',
    lastAgentKeyword: '',
    /** 浏览器 GPS 缓存，供对话 Agent 附近检索 / 路线 */
    lastGps: null, // { lng, lat, accuracy?, city?, citycode?, source?, ts }
  }),

  actions: {
    setLastGps(coords) {
      if (!coords || coords.lng == null || coords.lat == null) return
      this.lastGps = {
        lng: coords.lng,
        lat: coords.lat,
        accuracy: coords.accuracy,
        city: coords.city || this.lastGps?.city || '',
        citycode: coords.citycode || this.lastGps?.citycode || '',
        source: coords.source || 'browser-gps',
        ts: Date.now(),
      }
    },
    pushMarkersFromSource(markers, city) {
      this.pendingMarkers = markers || []
      this.pendingCity = city || ''
      this.pendingKeyword = ''
      this.pendingSource = 'source'
      this.hasPendingUpdate = true
    },

    pushMarkersFromAgent(markers, city, keyword = '') {
      const list = markers || []
      this.pendingMarkers = list
      this.pendingCity = city || ''
      this.pendingKeyword = keyword || ''
      this.pendingSource = 'agent'
      this.hasPendingUpdate = true
      this.lastAgentMarkers = list
      this.lastAgentCity = city || ''
      this.lastAgentKeyword = keyword || ''
    },

    /** 再次从对话跳转地图时，恢复最近一次 Agent 标点 */
    rearmAgentPending() {
      if (!this.lastAgentMarkers?.length) return false
      this.pendingMarkers = this.lastAgentMarkers
      this.pendingCity = this.lastAgentCity
      this.pendingKeyword = this.lastAgentKeyword
      this.pendingSource = 'agent'
      this.hasPendingUpdate = true
      return true
    },

    consumeUpdate() {
      this.hasPendingUpdate = false
    },
  },
})
