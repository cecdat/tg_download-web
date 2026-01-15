// pages/tasks/tasks.js
Page({
  data: {
    loading: true,
    tasks: [],
    currentPage: 1,
    pageSize: 20,
    totalCount: 0,
    totalPages: 0
  },

  onLoad() {
    this.loadTasks()
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({
        selected: 3
      })
    }
    this.loadTasks()
  },

  loadTasks() {
    const app = getApp()
    const { currentPage, pageSize } = this.data

    this.setData({
      loading: true
    })

    app.request(`/tasks?page=${currentPage}&limit=${pageSize}`, 'GET')
      .then(res => {
        if (res.code === 200) {
          const totalCount = res.count
          const totalPages = Math.ceil(totalCount / pageSize)

          // 处理图标显示
          const tasks = res.data.map(task => {
            const fileName = (task.file_name || '').toLowerCase();
            let icon = '📄'; // 默认文件图标

            if (fileName.match(/\.(mp4|mkv|avi|mov|wmv|flv|webm)$/)) {
              icon = '🎬'; // 视频
            } else if (fileName.match(/\.(jpg|jpeg|png|gif|webp|bmp|svg)$/)) {
              icon = '🖼️'; // 图片
            } else if (fileName.match(/\.(mp3|wav|flac|ogg|m4a)$/)) {
              icon = '🎵'; // 音乐
            } else if (fileName.match(/\.(zip|rar|7z|tar|gz|bz2)$/)) {
              icon = '📦'; // 压缩包
            } else if (fileName.match(/\.(pdf|doc|docx|ppt|pptx|xls|xlsx|txt)$/)) {
              icon = '📑'; // 文档
            } else if (fileName.match(/\.(apk|exe|dmg|pkg)$/)) {
              icon = '💿'; // 安装包
            }

            return { ...task, icon: icon };
          });

          this.setData({
            tasks: tasks,
            totalCount: totalCount,
            totalPages: totalPages,
            loading: false
          })
        }
      })
      .catch(err => {
        console.error('Failed to load tasks:', err)
        this.setData({
          loading: false
        })
      })
  },

  prevPage() {
    if (this.data.currentPage > 1) {
      this.setData({
        currentPage: this.data.currentPage - 1
      })
      this.loadTasks()
    }
  },

  nextPage() {
    if (this.data.currentPage < this.data.totalPages) {
      this.setData({
        currentPage: this.data.currentPage + 1
      })
      this.loadTasks()
    }
  },

  confirmDeleteTask(e) {
    const id = e.currentTarget.dataset.id
    wx.showModal({
      title: '确认删除',
      content: '确定要删除这个任务记录吗？',
      success: (res) => {
        if (res.confirm) {
          this.deleteTask(id)
        }
      }
    })
  },

  deleteTask(id) {
    const app = getApp()
    wx.showLoading({
      title: '删除中...'
    })

    app.request(`/tasks/delete/${id}`, 'POST')
      .then(res => {
        wx.hideLoading()
        if (res.code === 200) {
          this.loadTasks()
        } else {
          wx.showToast({
            title: '删除失败',
            icon: 'none'
          })
        }
      })
      .catch(err => {
        wx.hideLoading()
        console.error('Failed to delete task:', err)
        wx.showToast({
          title: '删除失败',
          icon: 'none'
        })
      })
  },

  confirmClearTasks() {
    wx.showModal({
      title: '确认清空',
      content: '确定要清空所有任务记录吗？',
      success: (res) => {
        if (res.confirm) {
          this.clearTasks()
        }
      }
    })
  },

  clearTasks() {
    const app = getApp()
    wx.showLoading({
      title: '清空记录中...'
    })

    app.request('/tasks/clear', 'POST')
      .then(res => {
        wx.hideLoading()
        if (res.code === 200) {
          this.setData({
            currentPage: 1
          })
          this.loadTasks()
        } else {
          wx.showToast({
            title: '清空失败',
            icon: 'none'
          })
        }
      })
      .catch(err => {
        wx.hideLoading()
        console.error('Failed to clear tasks:', err)
        wx.showToast({
          title: '清空失败',
          icon: 'none'
        })
      })
  }
})