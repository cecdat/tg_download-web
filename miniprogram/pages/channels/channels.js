// pages/channels/channels.js
Page({
  data: {
    loading: true,
    channels: [],
    accounts: [],
    showModal: false,
    isEdit: false,
    error: '',
    accountIndex: 0,
    formData: {
      id: '',
      account_id: '',
      channel_id: '',
      channel_name: '',
      enabled: 1,
      custom_path: ''
    }
  },

  onLoad() {
    this.loadAccounts()
    this.loadChannels()
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({
        selected: 2
      })
    }
    this.loadChannels()
  },

  loadAccounts() {
    const app = getApp()
    app.request('/accounts', 'GET')
      .then(res => {
        if (res.code === 200) {
          this.setData({
            accounts: res.data
          })
        }
      })
      .catch(err => {
        console.error('Failed to load accounts:', err)
      })
  },

  loadChannels() {
    const app = getApp()
    this.setData({
      loading: true
    })
    app.request('/channels', 'GET')
      .then(res => {
        if (res.code === 200) {
          this.setData({
            channels: res.data,
            loading: false
          })
        }
      })
      .catch(err => {
        console.error('Failed to load channels:', err)
        this.setData({
          loading: false
        })
      })
  },

  showAddChannelModal() {
    this.setData({
      showModal: true,
      isEdit: false,
      error: '',
      accountIndex: 0,
      formData: {
        id: '',
        account_id: this.data.accounts.length > 0 ? this.data.accounts[0].id : '',
        channel_id: '',
        channel_name: '',
        enabled: 1,
        custom_path: ''
      }
    })
  },

  showEditChannelModal(e) {
    const channel = e.currentTarget.dataset.channel
    const accountIndex = this.data.accounts.findIndex(acc => acc.id === channel.account_id)
    this.setData({
      showModal: true,
      isEdit: true,
      error: '',
      accountIndex: accountIndex >= 0 ? accountIndex : 0,
      formData: {
        id: channel.id,
        account_id: channel.account_id,
        channel_id: channel.channel_id,
        channel_name: channel.channel_name || '',
        enabled: channel.enabled,
        custom_path: channel.custom_path || ''
      }
    })
  },

  hideModal() {
    this.setData({
      showModal: false
    })
  },

  hideError() {
    this.setData({
      error: ''
    })
  },

  onAccountChange(e) {
    const index = e.detail.value
    this.setData({
      accountIndex: index,
      'formData.account_id': this.data.accounts[index].id
    })
  },

  onChannelIdInput(e) {
    this.setData({
      'formData.channel_id': e.detail.value
    })
  },

  onChannelNameInput(e) {
    this.setData({
      'formData.channel_name': e.detail.value
    })
  },

  onCustomPathInput(e) {
    this.setData({
      'formData.custom_path': e.detail.value
    })
  },

  toggleEnabled() {
    this.setData({
      'formData.enabled': this.data.formData.enabled ? 0 : 1
    })
  },

  saveChannel() {
    const { account_id, channel_id } = this.data.formData

    if (!account_id || !channel_id) {
      this.setData({
        error: '请选择账号并填写频道ID'
      })
      return
    }

    const app = getApp()
    const data = this.data.formData

    wx.showLoading({
      title: '保存中...'
    })

    app.request('/channels', 'POST', data)
      .then(res => {
        wx.hideLoading()
        if (res.code === 200) {
          this.hideModal()
          this.loadChannels()
        } else {
          this.setData({
            error: res.message || '保存失败'
          })
        }
      })
      .catch(err => {
        wx.hideLoading()
        console.error('Failed to save channel:', err)
        this.setData({
          error: '保存失败，请检查网络连接'
        })
      })
  },

  toggleChannelStatus(e) {
    const id = e.currentTarget.dataset.id
    const enabled = e.currentTarget.dataset.enabled
    const app = getApp()

    wx.showLoading({
      title: '更新中...'
    })

    app.request(`/channels/toggle/${id}`, 'POST')
      .then(res => {
        wx.hideLoading()
        if (res.code === 200) {
          this.loadChannels()
        } else {
          wx.showToast({
            title: '更新失败',
            icon: 'none'
          })
        }
      })
      .catch(err => {
        wx.hideLoading()
        console.error('Failed to toggle channel status:', err)
        wx.showToast({
          title: '更新失败',
          icon: 'none'
        })
      })
  },

  confirmDeleteChannel(e) {
    const id = e.currentTarget.dataset.id
    wx.showModal({
      title: '确认删除',
      content: '确定要删除这个频道吗？',
      success: (res) => {
        if (res.confirm) {
          this.deleteChannel(id)
        }
      }
    })
  },

  deleteChannel(id) {
    const app = getApp()
    wx.showLoading({
      title: '删除中...'
    })

    app.request(`/channels/delete/${id}`, 'POST')
      .then(res => {
        wx.hideLoading()
        if (res.code === 200) {
          this.loadChannels()
        } else {
          wx.showToast({
            title: '删除失败',
            icon: 'none'
          })
        }
      })
      .catch(err => {
        wx.hideLoading()
        console.error('Failed to delete channel:', err)
        wx.showToast({
          title: '删除失败',
          icon: 'none'
        })
      })
  },

  // 阻止事件冒泡
  stopBubble() { }
})