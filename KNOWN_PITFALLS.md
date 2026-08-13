# 已知坑与使用注意 (Known Pitfalls)

系统仪表盘 (port 8899) 开发与运维中遇到的坑，按模块记录。

## 浏览器 DELETE 请求静默失败 (关键)

**现象:** 文件管理里点"删除选中"，确认框弹出后没有任何反应，刷新后文件还在。

**原因:** 浏览器对 `DELETE` 请求(以及其它非简单请求)会先发一个 `OPTIONS` 预检(preflight)。
若服务器没有实现 `do_OPTIONS` 处理器并返回 `Access-Control-Allow-*` 头，
真实请求永远发不出去——前端的 `fetch` 只表现为"没反应"，不会报错。

**修复:** 服务器必须实现 `do_OPTIONS`，返回:

```python
def do_OPTIONS(self):
    self.send_response(200)
    self.send_header("Access-Control-Allow-Origin", "*")
    self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
    self.send_header("Access-Control-Allow-Headers", "Content-Type")
    self.send_header("Access-Control-Max-Age", "86400")
    self.end_headers()
```

前端 `fetch` 侧给 DELETE/上传请求显式加上 `method` 与 `headers: {"Content-Type": "application/x-www-form-urlencoded"}`，
确保浏览器按"非简单请求"走完整预检。

## 批量删除的前端竞态

**现象:** "删除选中"有时只删了部分文件。

**原因:** 旧版用 `setTimeout(300)` 后刷新列表，不等所有 `DELETE` 返回就重渲染，
后发的请求被刷新打断/丢结果。

**修复:** 使用 `async` + `Promise.all`，等所有 `fetch` 都 resolve 后再重新加载列表:

```js
async function batchDel() {
    const items = [...document.querySelectorAll(".chk:checked")];
    await Promise.all(items.map(item =>
        fetch("/api/delete?file=" + encodeURIComponent(item.value), { method: "DELETE" })));
    reloadList();
}
```

## HTML 转义文件名: 只转义引号，不要全量转义

**现象:** 文件名含 `&`、`<`、`"` 时，删除/下载目标错误或失败。

**原因:** 把文件名写进 checkbox 的 `value` 属性时若做了完整 HTML 实体转义
(例如 `&` → `&amp;`)，浏览器读回 `value` 是原文，脚本用实体串去找文件自然找不到。

**修复:** `value` 只转义 `"` 为 `&quot;`，其余原样:

```js
value="${e.name.replace(/"/g,"&quot;")}"
```

## 内联 onclick 的单引号注入

**现象:** 文件名含 `'` 时点导航/预览报 JS 错误或行为异常。

**原因:** onclick 里用单引号包裹参数 `onclick="navDir('${name}')"`，文件名里的 `'`
提前闭合字符串。

**修复:** 拼 onclick 前把 `'` 转义为 `\\'`:

```js
onclick="navDir(${JSON.stringify(e.name).replace(/'/g,"\\'")})"
```

## 删除其它用户拥有的文件夹: PermissionError

**现象:** 面板能列出 `/home/hbpc/video_projects_douyin/` 等目录，
但删除提示 `permission denied`。

**原因:** 服务器以 `hbpc` 运行。`video_projects_douyin/` 下的项目文件夹
属主是别的用户(如 `postfix:crontab`)，`hbpc` 对子文件无写权限，
`shutil.rmtree` 直接抛 `PermissionError`。这不是代码 bug——能删自己的
文件，删不了别人属主的。

**修复(服务器侧降级):** 删除遇到 `PermissionError` 时，若目标在
允许的目录树下，用 passwordless sudo 重试:

```python
def _attempt_sudo_delete(path):
    allowed = os.path.expanduser("~")            # /home/hbpc
    real = os.path.realpath(path)
    if not (real == allowed or real.startswith(allowed + "/")):
        return
    if real == allowed:                          # 不允许删 home 根
        return
    subprocess.run(["sudo", "-n", "rm", "-rf", real], ...)
```

**修复(一次性配置):** 给 `hbpc` 配一条**只针对**删除的免密 sudo 规则:

```bash
sudo bash /home/hbpc/power-dashboard/fix-filemgr-sudo.sh
```

脚本安装 `sudoers.filemgr` 到 `/etc/sudoers.d/99-filemgr`,内容:

```
Cmnd_Alias FILEMGR_RM = /bin/rm -rf /home/hbpc/*, /usr/bin/rm -rf /home/hbpc/*
hbpc ALL=(root) NOPASSWD: FILEMGR_RM
```

- `/home/hbpc/*` glob 只匹配子项，**不含 home 根本身**，根目录不会被这条规则删掉。
- 面板端(上方 python)`_attempt_sudo_delete` 也做了二次防护，拒绝 `real == /home/hbpc`。
- 规则严格限定为 `rm -rf` 这一条命令，不授予任何其它 sudo 能力。

## sudoers 语法坑

- 用 `Cmnd_Alias` + `NOPASSWD:` 分两行写，别写成单行大长串。
- **命令路径和 `*` 通配都不要加引号**。`"/bin/rm -rf /home/hbpc/*"` 会把
  引号当路径的一部分，报 `expected a fully-qualified path name`。
- 参数里含 `user:group`(如 `chown -R hbpc:hbpc ...`)可能让解析器把冒号当成特殊
  符号报语法错。需要 chown 的规则建议多用纯 `rm` 规则代替。
- 改 `/etc/sudoers.d/` 前必须校验:

```bash
sudo /usr/sbin/visudo -c -f <新规则文件>
```

## bash: 后台 python 服务随 shell 退出被杀

**现象:** 用 `python3 app.py &` 起服务，一会儿就没了；或用 agent shell
跑后台进程常超时退出。

**原因:** 后台进程挂在 shell 会话下，会话结束即被杀;部分工具 shell 会等待
子进程导致 `&` 也不返回。

**修复:** 用 `setsid` 彻底脱离会话:

```bash
setsid python3 /home/hbpc/power-dashboard/power-dashboard.py < /dev/null > /dev/null 2>&1 &
```

生产环境请用 systemd 管理(见 README),不要裸跑。

## 端口/进程排查

```bash
pgrep -af power-dashboard    # 进程
ss -tlnp | grep 8899         # 端口占用
```

启动前记得清理旧版本进程(用 `pkill -f power-dashboard.py`)，否则新旧两份
抢 8899 端口，行为或为修改前。

## 文件路径引用

`power-dashboard.py` 用 `os.path.dirname(os.path.abspath(__file__))`
定位同目录的 `power-dashboard.html`，因此**整个目录可以整体移动**，
不需要改代码里的路径。别再用 `os.path.expanduser("~/power-dashboard.html")`
这种写死 home 的路径——换目录就坏。