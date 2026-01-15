// pages/login/login.js
Page({
  data: {
    username: '',
    password: '',
    error: '',
    rememberMe: false
  },

  onLoad() {
    // 初始化Canvas绘制背景
    this.initBackground()

    // 加载记住的账号密码
    this.loadRememberedCredentials()
  },

  onUsernameInput(e) {
    this.setData({
      username: e.detail.value
    })
  },

  onPasswordInput(e) {
    this.setData({
      password: e.detail.value
    })
  },

  hideError() {
    this.setData({
      error: ''
    })
  },

  toggleRemember() {
    this.setData({
      rememberMe: !this.data.rememberMe
    })
  },

  loadRememberedCredentials() {
    const remembered = wx.getStorageSync('rememberedCredentials')
    if (remembered) {
      this.setData({
        username: remembered.username,
        password: remembered.password,
        rememberMe: true
      })
    }
  },

  saveRememberedCredentials() {
    const { username, password, rememberMe } = this.data
    if (rememberMe) {
      wx.setStorageSync('rememberedCredentials', {
        username: username,
        password: password
      })
    } else {
      wx.removeStorageSync('rememberedCredentials')
    }
  },

  onUnload() {
    this.stopBackgroundAnimation()
  },

  initBackground() {
    // 获取屏幕尺寸
    wx.getSystemInfo({
      success: (res) => {
        this.canvasWidth = res.windowWidth
        this.canvasHeight = res.windowHeight
        this.startBackgroundAnimation()
      }
    })
  },

  startBackgroundAnimation() {
    this.ctx = wx.createCanvasContext('backgroundCanvas')
    this.lines = []

    // 初始化线条
    for (let i = 0; i < 20; i++) {
      this.lines.push(this.createLine())
    }

    this.animationRunning = true
    this.animate()
  },

  stopBackgroundAnimation() {
    this.animationRunning = false
  },

  createLine() {
    const colors = ['#667eea', '#764ba2', '#5271FF', '#FF52AF', '#00D68F']
    return {
      x: Math.random() * this.canvasWidth,
      y: Math.random() * this.canvasHeight,
      length: Math.random() * 400 + 200,
      angle: Math.random() * Math.PI * 2,
      speed: Math.random() * 0.8 + 0.3,
      opacity: Math.random() * 0.3 + 0.05,
      width: Math.random() * 4 + 1,
      color: colors[Math.floor(Math.random() * colors.length)]
    }
  },

  animate() {
    if (!this.animationRunning) return

    const ctx = this.ctx
    const w = this.canvasWidth
    const h = this.canvasHeight

    // 清除画布
    ctx.clearRect(0, 0, w, h)
    ctx.setFillStyle('#f8fafc')
    ctx.fillRect(0, 0, w, h)

    // 绘制并更新线条
    this.lines.forEach((line, index) => {
      // 计算终点
      const endX = line.x + Math.cos(line.angle) * line.length
      const endY = line.y + Math.sin(line.angle) * line.length

      // 绘制渐变线条
      const grd = ctx.createLinearGradient(line.x, line.y, endX, endY)
      grd.addColorStop(0, 'transparent')
      grd.addColorStop(0.5, line.color)
      grd.addColorStop(1, 'transparent')

      ctx.beginPath()
      ctx.setStrokeStyle(grd)
      ctx.setGlobalAlpha(line.opacity)
      ctx.setLineWidth(line.width)
      ctx.moveTo(line.x, line.y)
      ctx.lineTo(endX, endY)
      ctx.stroke()

      // 更新位置
      line.x += Math.cos(line.angle) * line.speed
      line.y += Math.sin(line.angle) * line.speed

      // 边界检测与重置
      if (line.x < -line.length || line.x > w + line.length ||
        line.y < -line.length || line.y > h + line.length) {
        this.lines[index] = this.createLine()
        // 确保从边缘进入
        const side = Math.floor(Math.random() * 4)
        if (side === 0) { line.x = -line.length; line.y = Math.random() * h; }
        else if (side === 1) { line.x = w + line.length; line.y = Math.random() * h; }
        else if (side === 2) { line.y = -line.length; line.x = Math.random() * w; }
        else { line.y = h + line.length; line.x = Math.random() * w; }
      }
    })

    ctx.draw()

    // 小程序中使用 setTimeout 模拟动画帧 (由于 canvasContext.draw 的异步特性)
    setTimeout(() => {
      this.animate()
    }, 30)
  },

  login() {
    const { username, password } = this.data

    if (!username || !password) {
      this.setData({
        error: '请输入用户名和密码'
      })
      return
    }

    wx.showLoading({
      title: '登录中...'
    })

    // 使用 API 登录接口
    wx.request({
      url: 'https://bot.2020310.xyz/api/login',
      method: 'POST',
      data: {
        username: username,
        password: password
      },
      header: {
        'content-type': 'application/json',
        'Accept': 'application/json'
      },
      success: (res) => {
        wx.hideLoading()

        console.log('Login response status:', res.statusCode)
        console.log('Login response headers:', res.header)
        console.log('Login response data:', res.data)

        // 关键检查：如果返回的是字符串并且包含 HTML 标签，说明后端没返回 JSON，而是重定向到了 HTML 页面
        if (typeof res.data === 'string' && (res.data.includes('<html') || res.data.includes('<!DOCTYPE'))) {
          this.setData({
            error: '后端配置未生效，请重启后端服务'
          })
          return
        }

        // 登录成功判定：状态码 200 或数据中 code 为 200
        const isSuccess = res.statusCode === 200 && (res.code === 200 || (res.data && res.data.code === 200))

        if (isSuccess) {
          // 保存记住的账号密码
          this.saveRememberedCredentials()

          // 提取 Session Cookie
          let sessionCookie = ''

          // 1. 尝试从 res.cookies 提取 (部分基础库支持)
          if (res.cookies && res.cookies.length > 0) {
            for (let cookie of res.cookies) {
              if (cookie.startsWith('session=')) {
                sessionCookie = cookie
                break
              }
            }
          }

          // 2. 尝试从 header['Set-Cookie'] 提取
          if (!sessionCookie && res.header) {
            const setCookie = res.header['Set-Cookie'] || res.header['set-cookie']
            if (setCookie) {
              // Set-Cookie 可能是字符串也可能是数组
              const cookies = Array.isArray(setCookie) ? setCookie : setCookie.split(',')
              for (let cookie of cookies) {
                if (cookie.trim().startsWith('session=')) {
                  sessionCookie = cookie.trim().split(';')[0]
                  break
                }
              }
            }
          }

          console.log('Final Session Cookie:', sessionCookie)

          // 如果提取到了 cookie，保存它。如果没有，可能后端没设置（比如已经登录过了）
          if (sessionCookie) {
            wx.setStorageSync('token', sessionCookie)
            const app = getApp()
            app.globalData.token = sessionCookie
          }

          wx.showToast({
            title: '登录成功',
            icon: 'success',
            duration: 1500,
            success: () => {
              setTimeout(() => {
                wx.switchTab({
                  url: '/pages/index/index'
                })
              }, 1500)
            }
          })
        } else {
          this.setData({
            error: res.data.message || '用户名或密码错误'
          })
        }
      },
      fail: (err) => {
        wx.hideLoading()
        console.error('Login failed:', err)
        this.setData({
          error: `登录失败: ${err.errMsg || '请检查网络连接'}`
        })
      }
    })
  }
})