Component({
    data: {
        selected: 0,
        color: "#94A3B8",
        selectedColor: "#5271FF",
        list: [
            {
                pagePath: "/pages/index/index",
                icon: "🏠",
                text: "控制台"
            },
            {
                pagePath: "/pages/accounts/accounts",
                icon: "👤",
                text: "账号"
            },
            {
                pagePath: "/pages/channels/channels",
                icon: "📢",
                text: "频道"
            },
            {
                pagePath: "/pages/tasks/tasks",
                icon: "🕒",
                text: "任务"
            },
            {
                pagePath: "/pages/settings/settings",
                icon: "⚙️",
                text: "设置"
            }
        ]
    },
    methods: {
        switchTab(e) {
            const data = e.currentTarget.dataset
            const url = data.path
            wx.switchTab({ url })
            this.setData({
                selected: data.index
            })
        }
    }
})
