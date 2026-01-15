// pages/index/index.js
Page({
  data: {
    loading: true,
    diskTotal: 0,
    diskUsed: 0,
    diskPercent: 0,
    memoryTotal: 0,
    memoryUsed: 0,
    memoryPercent: 0,
    systemLoad: '0.00',
    uptime: '0s',
    activeDownloadsCount: 0,
    activeDownloads: []
  },

  onLoad() {
    this.refreshData()
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({
        selected: 0
      })
    }
    this.refreshData()
  },

  onHide() {
    this.stopPolling()
  },

  onUnload() {
    this.stopPolling()
  },

  stopPolling() {
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer)
      this.refreshTimer = null
    }
  },

  formatUptime(seconds) {
    if (!seconds) return '0s'
    const days = Math.floor(seconds / (24 * 3600))
    const hours = Math.floor((seconds % (24 * 3600)) / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    const s = seconds % 60

    let res = ''
    if (days > 0) res += `${days}天 `
    if (hours > 0 || days > 0) res += `${hours}时 `
    if (minutes > 0 || hours > 0 || days > 0) res += `${minutes}分 `
    res += `${s}秒`
    return res
  },

  refreshData() {
    const app = getApp()
    // 每次请求前先清除旧的定时器
    this.stopPolling()

    app.request('/status', 'GET')
      .then(res => {
        if (res.code === 200) {
          const actualData = res.data
          const activeCount = actualData.active_count || 0

          this.setData({
            diskTotal: actualData.disk?.total || 0,
            diskUsed: actualData.disk?.used || 0,
            diskPercent: actualData.disk?.percent || 0,
            memoryTotal: actualData.memory?.total || 0,
            memoryUsed: actualData.memory?.used || 0,
            memoryPercent: actualData.memory?.percent || 0,
            systemLoad: actualData.load ? actualData.load[0].toFixed(2) : '0.00',
            uptime: this.formatUptime(actualData.uptime),
            activeDownloadsCount: activeCount,
            activeDownloads: actualData.active_downloads || [],
            loading: false
          })

          // 策略轮询：如果有活跃下载，15秒后再次刷新
          if (activeCount > 0) {
            this.refreshTimer = setTimeout(() => {
              this.refreshData()
            }, 15000)
          }
        } else {
          this.setData({ loading: false })
        }
      })
      .catch(err => {
        console.error('Failed to get status:', err)
        this.setData({ loading: false })
      })
  }
})