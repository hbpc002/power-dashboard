# 系统资源仪表盘

局域网内实时监控 Linux 笔记本的电池、CPU、内存、磁盘、网络状态，附带文件管理功能。

## 文件

| 文件 | 说明 |
|---|---|
| `power-dashboard.py` | HTTP 服务器 (Python3, 无三方依赖)，端口 8899 |
| `power-dashboard.html` | 前端仪表盘，温度趋势图 + 文件浏览器 |
| `battery-monitor.sh` | 低电量 webhook 告警脚本 |
| `.battery-monitor.conf` | **(需手动创建)** 阈值与 webhook 配置 |
| `fix-filemgr-sudo.sh` | 一次性配免密删除规则(需 sudo 运行) |
| `sudoers.filemgr` | 免密删除的 sudoers 规则源文件(由脚本安装) |
| `KNOWN_PITFALLS.md` | 已知坑与使用注意(必读) |
| `systemd/power-dashboard.service` | 仪表盘自启服务 |
| `systemd/battery-monitor.timer` | 电池检查定时器 (每 5 分钟) |
| `systemd/battery-monitor.service` | 告警脚本 one-shot 服务 |

## 安装

```bash
# 1. 确保 Python3 可用 (默认已装)
python3 --version

# 2. 克隆到 ~/projects/power-dashboard
mkdir -p ~/projects
git clone https://github.com/hbpc002/power-dashboard.git ~/projects/power-dashboard

# 3. 单元文件装在 systemd/ 里，用符号链接挂进 ~/.config/systemd/user/
#    （若克隆到别的目录，改 systemd/*.service 里的 ExecStart 绝对路径）
ln -sfn ~/projects/power-dashboard/systemd/power-dashboard.service  ~/.config/systemd/user/
ln -sfn ~/projects/power-dashboard/systemd/battery-monitor.service  ~/.config/systemd/user/
ln -sfn ~/projects/power-dashboard/systemd/battery-monitor.timer    ~/.config/systemd/user/

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
- 批量删除、批量下载(zip)、上传文件

> **删除权限说明**（默认关闭，需一次性装 sudoers 规则，装完整个家目录都能免密删除，权衡后决定）: 服务器以 `hbpc` 运行，默认只能删 `hbpc` 属主的文件。
> 若 `video_projects_douyin/` 这类目录里的文件属主是别的用户，删除会提示
> `permission denied`。解决办法(一次性):
> `sudo bash ~/projects/power-dashboard/fix-filemgr-sudo.sh`
> 详情见 `KNOWN_PITFALLS.md` 中「删除其它用户拥有的文件夹」一节。

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
