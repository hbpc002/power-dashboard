# 系统资源仪表盘

局域网内实时监控 Linux 笔记本的电池、CPU、内存、磁盘、网络状态，附带文件管理功能。

## 文件

| 文件 | 说明 |
|---|---|
| `power-dashboard.py` | HTTP 服务器 (Python3, 无三方依赖)，端口 8899 |
| `power-dashboard.html` | 前端仪表盘，温度趋势图 + 文件浏览器 |
| `battery-monitor.sh` | 低电量 webhook 告警脚本 |
| `.battery-monitor.conf` | **(需手动创建)** 阈值与 webhook 配置 |
| `.config/systemd/user/power-dashboard.service` | 仪表盘自启服务 |
| `.config/systemd/user/battery-monitor.timer` | 电池检查定时器 (每 5 分钟) |
| `.config/systemd/user/battery-monitor.service` | 告警脚本 one-shot 服务 |

## 安装

```bash
# 1. 确保 Python3 可用 (默认已装)
python3 --version

# 2. 将项目放到 ~/power-dashboard (或直接放 ~/)
cd ~
git clone https://github.com/hbpc002/power-dashboard.git
cd power-dashboard

# 3. 如果放在别的目录，编辑 .config/systemd/user/* 中的 ExecStart 路径

# 4. 启用用户 linger，确保用户服务在登录前启动
sudo loginctl enable-linger $USER

# 5. 重载 systemd 用户服务
systemctl --user daemon-reload

# 6. 启动仪表盘
systemctl --user enable --now power-dashboard

# 7. （可选）启动低电量告警
systemctl --user enable --now battery-monitor.timer
```

## 配置

### 低电量阈值

创建 `~/.battery-monitor.conf`：

```ini
THRESHOLD=20
WEBHOOK_URL=http://192.168.1.114:8644/webhooks/power-alert
WEBHOOK_SECRET=your_secret_here
```

### 防火墙

确保 8899 端口可达：

```bash
sudo ufw allow 8899  # 如有 ufw
# 或
sudo firewall-cmd --add-port=8899/tcp --permanent
```

## 使用

浏览器打开 `http://<你的局域网IP>:8899`

### 系统监控

- **电池**: 电量、充放电功率、USB-C 适配器能力、循环次数、低电量阈值设置
- **CPU**: Tctl 温度、频率、总体/单核使用率(柱形图)、负载均值、2 小时温度趋势
- **内存**: 总量/已用、详情(可用/缓存/缓冲)、使用率趋势
- **磁盘**: 分区使用率(进度条)、I/O 累计读写
- **网络**: 实时速率、接收/发送 2 小时趋势、接口列表

### 文件管理

- 浏览目录、导航上级
- 图片/音频/视频预览、文本查看与编辑
- 批量删除、上传文件

## systemd 管理

```bash
# 仪表盘
systemctl --user status power-dashboard
systemctl --user restart power-dashboard
journalctl --user -u power-dashboard -f

# 电池告警
systemctl --user status battery-monitor.timer
systemctl --user list-timers
```
