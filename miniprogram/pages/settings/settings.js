// pages/settings/settings.js
Page({
  data: {
    loading: true,
    settings: {
      DOWNLOAD_DIR: '',
      MAX_CONCURRENT_DOWNLOADS: '',
      FILE_RETENTION_DAYS: '',
      SEND_CHANNEL_LOGIN_MSG: ''
    },
    sendChannelLoginMsg: false,
    passwordData: {
      oldPassword: '',
      newPassword: '',
      confirmPassword: ''
    },
    passwordError: ''
  },

  onLoad() {
    this.loadSettings()
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({
        selected: 4
      })
    }
  },

  loadSettings() {
    const app = getApp()

    this.setData({
      loading: true
    })

    app.request('/settings', 'GET')
      .then(res => {
        if (res.code === 200) {
          const settings = res.data
          // 兼容处理：支持 'True' 字符串、true 布尔值或 1 数字
          const isEnabled = settings.SEND_CHANNEL_LOGIN_MSG === 'True' ||
            settings.SEND_CHANNEL_LOGIN_MSG === true ||
            settings.SEND_CHANNEL_LOGIN_MSG === 1 ||
            settings.SEND_CHANNEL_LOGIN_MSG === '1';

          this.setData({
            settings: settings,
            sendChannelLoginMsg: isEnabled,
            loading: false
          })
        }
      })
      .catch(err => {
        console.error('Failed to load settings:', err)
        this.setData({
          loading: false
        })
      })
  },

  onDownloadDirInput(e) {
    this.setData({
      'settings.DOWNLOAD_DIR': e.detail.value
    })
  },

  onMaxConcurrentDownloadsInput(e) {
    this.setData({
      'settings.MAX_CONCURRENT_DOWNLOADS': e.detail.value
    })
  },

  onFileRetentionDaysInput(e) {
    this.setData({
      'settings.FILE_RETENTION_DAYS': e.detail.value
    })
  },

  toggleSendChannelLoginMsg() {
    const newValue = !this.data.sendChannelLoginMsg;
    this.setData({
      sendChannelLoginMsg: newValue,
      'settings.SEND_CHANNEL_LOGIN_MSG': newValue
    })
  },

  saveSettings() {
    const app = getApp()
    const settings = this.data.settings

    wx.showLoading({
      title: '保存中...'
    })

    app.request('/settings', 'POST', settings)
      .then(res => {
        wx.hideLoading()
        if (res.code === 200) {
          wx.showToast({
            title: '保存成功',
            icon: 'success'
          })
        } else {
          wx.showToast({
            title: '保存失败',
            icon: 'none'
          })
        }
      })
      .catch(err => {
        wx.hideLoading()
        console.error('Failed to save settings:', err)
        wx.showToast({
          title: '保存失败',
          icon: 'none'
        })
      })
  },

  onOldPasswordInput(e) {
    this.setData({
      'passwordData.oldPassword': e.detail.value
    })
  },

  onNewPasswordInput(e) {
    this.setData({
      'passwordData.newPassword': e.detail.value
    })
  },

  onConfirmPasswordInput(e) {
    this.setData({
      'passwordData.confirmPassword': e.detail.value
    })
  },

  hidePasswordError() {
    this.setData({
      passwordError: ''
    })
  },

  changePassword() {
    const { oldPassword, newPassword, confirmPassword } = this.data.passwordData

    if (!oldPassword || !newPassword || !confirmPassword) {
      this.setData({
        passwordError: '请填写所有密码字段'
      })
      return
    }

    if (newPassword !== confirmPassword) {
      this.setData({
        passwordError: '新密码和确认密码不匹配'
      })
      return
    }

    const app = getApp()

    wx.showLoading({
      title: '修改中...'
    })

    app.request('/settings/password', 'POST', {
      old_password: oldPassword,
      new_password: newPassword
    })
      .then(res => {
        wx.hideLoading()
        if (res.code === 200) {
          wx.showToast({
            title: '密码修改成功',
            icon: 'success'
          })
          // 清空密码输入
          this.setData({
            passwordData: {
              oldPassword: '',
              newPassword: '',
              confirmPassword: ''
            }
          })
        } else {
          this.setData({
            passwordError: res.message || '密码修改失败'
          })
        }
      })
      .catch(err => {
        wx.hideLoading()
        console.error('Failed to change password:', err)
        this.setData({
          passwordError: '密码修改失败，请检查网络连接'
        })
      })
  },

  confirmLogout() {
    wx.showModal({
      title: '确认退出',
      content: '确定要退出登录吗？',
      success: (res) => {
        if (res.confirm) {
          this.logout()
        }
      }
    })
  },

  logout() {
    // 清除本地存储的token
    wx.removeStorageSync('token')
    const app = getApp()
    app.globalData.token = null

    // 跳转到登录页
    wx.redirectTo({
      url: '/pages/login/login'
    })
  }
})