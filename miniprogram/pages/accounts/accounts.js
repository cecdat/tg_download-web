// pages/accounts/accounts.js
Page({
  data: {
    loading: true,
    accounts: [],
    showModal: false,
    isEdit: false,
    error: '',
    formData: {
      id: '',
      name: '',
      api_id: '',
      api_hash: '',
      bot_token: ''
    }
  },

  onLoad() {
    this.loadAccounts()
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({
        selected: 1
      })
    }
    this.loadAccounts()
  },

  loadAccounts() {
    const app = getApp()
    this.setData({
      loading: true
    })
    app.request('/accounts', 'GET')
      .then(res => {
        if (res.code === 200) {
          this.setData({
            accounts: res.data,
            loading: false
          })
        }
      })
      .catch(err => {
        console.error('Failed to load accounts:', err)
        this.setData({
          loading: false
        })
      })
  },

  showAddAccountModal() {
    this.setData({
      showModal: true,
      isEdit: false,
      error: '',
      formData: {
        id: '',
        name: '',
        api_id: '',
        api_hash: '',
        bot_token: ''
      }
    })
  },

  showEditAccountModal(e) {
    const account = e.currentTarget.dataset.account
    this.setData({
      showModal: true,
      isEdit: true,
      error: '',
      formData: {
        id: account.id,
        name: account.name,
        api_id: account.api_id,
        api_hash: account.api_hash,
        bot_token: account.bot_token || ''
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

  onNameInput(e) {
    this.setData({
      'formData.name': e.detail.value
    })
  },

  onApiIdInput(e) {
    this.setData({
      'formData.api_id': e.detail.value
    })
  },

  onApiHashInput(e) {
    this.setData({
      'formData.api_hash': e.detail.value
    })
  },

  onBotTokenInput(e) {
    this.setData({
      'formData.bot_token': e.detail.value
    })
  },

  saveAccount() {
    const { name, api_id, api_hash } = this.data.formData

    if (!name || !api_id || !api_hash) {
      this.setData({
        error: '请填写账号名称、API ID和API Hash'
      })
      return
    }

    const app = getApp()
    const method = this.data.isEdit ? 'POST' : 'POST'
    const data = this.data.formData

    wx.showLoading({
      title: '保存中...'
    })

    app.request('/accounts', method, data)
      .then(res => {
        wx.hideLoading()
        if (res.code === 200) {
          this.hideModal()
          this.loadAccounts()
        } else {
          this.setData({
            error: res.message || '保存失败'
          })
        }
      })
      .catch(err => {
        wx.hideLoading()
        console.error('Failed to save account:', err)
        this.setData({
          error: '保存失败，请检查网络连接'
        })
      })
  },

  confirmDeleteAccount(e) {
    const id = e.currentTarget.dataset.id
    wx.showModal({
      title: '确认删除',
      content: '确定要删除这个账号吗？',
      success: (res) => {
        if (res.confirm) {
          this.deleteAccount(id)
        }
      }
    })
  },

  deleteAccount(id) {
    const app = getApp()
    wx.showLoading({
      title: '删除中...'
    })

    app.request(`/accounts/delete/${id}`, 'POST')
      .then(res => {
        wx.hideLoading()
        if (res.code === 200) {
          this.loadAccounts()
        } else {
          wx.showToast({
            title: '删除失败',
            icon: 'none'
          })
        }
      })
      .catch(err => {
        wx.hideLoading()
        console.error('Failed to delete account:', err)
        wx.showToast({
          title: '删除失败',
          icon: 'none'
        })
      })
  },

  // 阻止事件冒泡
  stopBubble() { }
})