# 快速修复指南 - 黑屏问题

## 问题诊断

### 症状
- 前端黑屏
- 浏览器控制台显示API调用失败
- 后端报错: `OSError: [Errno 98] Address already in use`

### 原因
**默认后端端口被占用** - 之前的 Python 服务器进程没有正确关闭

---

## 快速修复

### 方法1: 使用自动化脚本（推荐）

```bash
cd cockpit_desktop
./start-dev.sh
```

这个脚本会：
1. ✅ 自动检测并释放默认后端端口（默认 `8079`）
2. ✅ 启动后端服务器
3. ✅ 启动前端开发服务器
4. ✅ 验证所有服务正常运行

### 方法2: 手动修复

```bash
# 1. 杀掉占用默认后端端口的进程
PID=$(lsof -ti :8079)
kill -9 $PID

# 2. 重新启动后端
cd ..
python3 session_bootstrap/demo/openamp_control_plane_demo/server.py --port 8079 &

# 3. 刷新浏览器
# Ctrl+Shift+R (强制刷新)
```

### 方法3: 更换端口

如果 `8079` 端口必须保留，可以使用其他端口：

```bash
# 后端使用 8081 端口
python3 session_bootstrap/demo/openamp_control_plane_demo/server.py --port 8081 &

# 然后在同一终端里设置 COCKPIT_BACKEND_PORT=8081 再启动前端 / Electron
```

---

## 验证服务

### 检查后端
```bash
curl http://localhost:8079/api/health
# 应该返回: {"status":"ok"}
```

### 检查端口占用
```bash
lsof -i :8079  # 查看后端
lsof -i :5173  # 查看前端
```

---

## 停止服务

### 使用脚本
```bash
./stop-dev.sh
```

### 手动停止
```bash
# 杀掉特定端口进程
kill -9 $(lsof -ti :8079)  # 后端
kill -9 $(lsof -ti :5173)  # 前端
```

---

## 预防措施

### 开发工作流

**启动开发环境**:
```bash
cd cockpit_desktop
./start-dev.sh
```

**停止开发环境**:
```bash
./stop-dev.sh
```

### 避免端口冲突

1. **总是使用脚本启动** - 自动处理端口冲突
2. **结束时正确停止** - 不要直接关闭终端
3. **检查僵尸进程** - 定期运行 `./stop-dev.sh`

---

## 常见错误

### ❌ "Address already in use"
**原因**: 之前的进程没有关闭
**解决**: 运行 `./start-dev.sh` 或手动杀掉进程

### ❌ "Connection refused"
**原因**: 后端服务器未启动
**解决**: 等待2-3秒让后端完全启动

### ❌ "黑屏 + API错误"
**原因**: 前端无法连接到后端
**解决**:
1. 检查后端是否运行: `curl http://localhost:8079/api/health`
2. 检查浏览器控制台错误
3. 强制刷新浏览器: Ctrl+Shift+R

---

## 文件说明

### start-dev.sh
- 自动启动前后端开发环境
- 处理端口冲突
- 验证服务状态
- 显示访问地址

### stop-dev.sh
- 优雅停止所有服务
- 清理僵尸进程
- 显示停止状态

---

## 技术细节

### 为什么默认后端端口会被占用？

1. **之前的dev服务器没有正确关闭**
   - 直接关闭终端窗口
   - 使用Ctrl+Z而不是Ctrl+C
   - 程序崩溃但端口未释放

2. **其他程序使用当前后端端口**
   - 其他Python服务
   - 系统服务

### 如何避免？

1. **使用启动/停止脚本**
2. **正确退出程序** (Ctrl+C)
3. **定期清理僵尸进程**

---

**Created**: 2026-03-30
**Last Updated**: 2026-03-30
**Status**: 端口冲突已修复，服务正常运行
