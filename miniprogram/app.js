// app.js
App({
  globalData: {
    userInfo: null,
    token: null,
    apiUrl: 'https://bot.2020310.xyz/api' // 后端API地址，根据实际情况修改
  },
  onLaunch() {
    // 检查本地存储的token
    const token = wx.getStorageSync('token')
    if (token) {
      this.globalData.token = token
    }
  },
  // 封装请求函数
  request(url, method = 'GET', data = {}) {
    const token = this.globalData.token
    const fullUrl = this.globalData.apiUrl + url
    console.log(`[Request] ${method} ${fullUrl}`)
    console.log(`[Request Data]`, data)
    console.log(`[Request Token]`, token)

    return new Promise((resolve, reject) => {
      wx.request({
        url: fullUrl,
        method: method,
        data: data,
        // 使用默认content-type
        header: {
          'content-type': 'application/json',
          // 使用存储的 Cookie 维持会话
          'Cookie': token || '',
          'Referer': 'https://bot.2020310.xyz/'
        },
        // 禁用自动重定向，手动处理
        followRedirect: false,
        // 禁用证书验证
        sslVerify: false,
        success: (res) => {
          console.log(`[Response] ${res.statusCode} ${fullUrl}`)
          console.log(`[Response Headers]`, res.header)

          // 如果响应内容是 HTML (通常以 <!DOCTYPE 开头)，说明 API 请求虽然返回 200，但实际是被重定向到了登录页 HTML
          if (typeof res.data === 'string' && (res.data.includes('<html') || res.data.includes('<!DOCTYPE'))) {
            console.error('API request was redirected to login page (HTML response detected)')
            this.globalData.token = null
            wx.removeStorageSync('token')
            const pages = getCurrentPages()
            const currentPage = pages[pages.length - 1]
            if (currentPage && currentPage.route !== 'pages/login/login') {
              wx.navigateTo({
                url: '/pages/login/login'
              })
            }
            resolve(res)
            return
          }

          console.log(`[Response Data]`, res.data)

          // 尝试解析字符串类型的 JSON（有时微信不自动解析）
          if (typeof res.data === 'string' && res.header &&
            (res.header['content-type'] || res.header['Content-Type'] || '').includes('application/json')) {
            try {
              res.data = JSON.parse(res.data)
            } catch (e) { }
          }

          // 将业务数据合并到响应对象，以便页面可以直接读取 res.code 等
          if (res.data && typeof res.data === 'object') {
            Object.assign(res, res.data)
          }

          // 处理 401 未登录 (在后端修改后的逻辑中，API 会返回 code: 401)
          if (res.code === 401) {
            console.warn('Session expired or not logged in, redirecting to login...')
            this.globalData.token = null
            wx.removeStorageSync('token')
            // 如果不是已经在登录页，则跳转
            const pages = getCurrentPages()
            const currentPage = pages[pages.length - 1]
            if (currentPage && currentPage.route !== 'pages/login/login') {
              wx.navigateTo({
                url: '/pages/login/login'
              })
            }
          }

          resolve(res)
        },
        fail: (err) => {
          console.error(`[Request Fail] ${fullUrl}:`, err)
          // 显示友好的错误提示
          wx.showToast({
            title: '网络请求失败，请检查网络设置',
            icon: 'none',
            duration: 3000
          })
          reject(err)
        }
      })
    })
  }
})