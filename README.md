# 心域智链 (Health New) - 开发者完整启动指南 🚀

本文档专为项目新成员编写，旨在提供一份**详尽、傻瓜式、可执行**的前后端本地启动规范。通过严格遵守本指南，您可以在全新机器上一次性成功启动并联调整个心理健康管理系统。

***

## 1. 项目整体架构说明

本项目采用**前后端分离**架构，主要用于高校大学生的心理健康测评、AI分析、树洞社区互动及教师干预管理。

### 1.1 技术栈总览

- **前端 (Frontend)**
  - **核心框架**: Vue 3 (Composition API)
  - **构建工具**: Vite (极速开发服务器与生产打包)
  - **UI 组件库**: Element Plus (提供基础交互组件)
  - **图表可视化**: ECharts (用于历次测评趋势、风险分布等数据可视化)
  - **请求库**: Axios (基于 Promise 的 HTTP 客户端)
  - **性能优化**: Service Worker (拦截 API 请求实现离线与弱网缓存)、Infinite Scroll (无限滚动/懒加载)
- **后端 (Backend)**
  - **核心框架**: FastAPI (高性能异步 Python Web 框架)
  - **服务器**: Uvicorn (ASGI 服务器)
  - **数据库 ORM**: SQLAlchemy (对象关系映射)
  - **默认数据库**: SQLite (免安装、开箱即用，通过 `chroma.sqlite3` 存储，生产可切换 MySQL)
  - **数据校验**: Pydantic (基于类型提示的数据验证)
  - **AI 大模型引擎**: DeepSeek API (提供心理报告深度分析及对话支持)
  - **检索增强 (RAG)**: ChromaDB (用于心理知识库检索与生成增强)

### 1.2 核心目录结构

```text
health_new/
├── backend/                   # 🐍 后端代码根目录
│   ├── app/                   # 核心业务逻辑 (FastAPI App)
│   │   ├── routers/           # 路由层 (如 student.py, teacher.py 等)
│   │   ├── services/          # 服务层 (处理 RAG, DeepSeek 调用, 分析报告等)
│   │   ├── models.py          # SQLAlchemy 数据库模型定义
│   │   └── schemas.py         # Pydantic 数据验证模型
│   ├── scripts/
│   │   └── seed_demo_data.py  # ⚠️ 必须执行：自动建表并注入演示数据的初始化脚本
│   ├── .env.example           # 后端环境变量模板 (需复制为 .env)
│   └── requirements.txt       # Python 依赖清单
├── src/                       # ⚡ 前端源码目录
│   ├── assets/                # 静态资源 (CSS, Images)
│   ├── router/                # Vue Router 路由配置
│   ├── views/                 # 页面组件 (分 student/teacher 等模块)
│   └── main.js                # Vue 应用挂载与 Axios 拦截器全局配置
├── public/
│   └── sw.js                  # Service Worker 脚本 (处理 API 离线缓存)
├── package.json               # Node.js 依赖配置
└── vite.config.js             # Vite 构建与开发代理配置
```

***

<br />

## 2. 后端启动步骤

由于前端强依赖后端 API 接口，我们优先启动后端服务。

### 2.1 环境要求

- **Python**: `>= 3.10`
  - 推荐：`3.11.x`（长期稳定）
  - 可用：`3.14.x`（已兼容；emohaa SDK 自动切换 HTTP 回退，避免 pydantic.v1 告警链路）
- **包管理工具**: `pip`

### 2.2 依赖安装与初始化

1. **进入后端目录**:
   ```bash
   cd backend
   .\.venv\Scripts\Activate.ps1
   ```


确保虚拟环境处于激活状态，执行启动命令：

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- `--reload`: 开启代码热更新 (开发模式必备)
- `--port 8000`: 强制绑定 8000 端口

**✅ 验证标准**：终端输出 `Application startup complete.`，浏览器访问 `http://127.0.0.1:8000/docs` 能看到 Swagger UI 接口文档页面。

***

## 3. 前端启动步骤

### 3.1 环境要求

- **Node.js**: `>= 18.0.0` (推荐 LTS 版本)
- **包管理工具**: `npm` (随 Node.js 一起安装)

### 3.2 依赖安装

1. **打开新终端，确保位于项目根目录** **`health_new/`**
2. **安装所有 Node.js 依赖**:
   ```bash
   npm install
   ```
   *(若遇网络问题，建议使用淘宝镜像:* *`npm config set registry https://registry.npmmirror.com`* *后重试)*

### 3.3 启动命令

- **开发模式 (热更新)**:
  ```bash
  npm run dev
  ```
  - Vite 默认会在 `5173` 端口启动，若端口被占用会自动顺延至 `5174`, `5175` 等。
- **生产模式 (构建与预览)**:
  ```bash
  npm run build
  npm run preview
  ```

### 3.4 配置文件说明

前端环境变量统一在 `vite.config.js` 和根目录的 `.env.development` 中管理。
由于 `main.js` 配置了全局 Axios 拦截器，它会自动读取 `import.meta.env.VITE_API_BASE_URL` 并与后端的 `/api` 路径进行拼接。开发模式下，Vite Server 已配置代理，将 `http://localhost:5173/api` 转发至 `http://127.0.0.1:8000/api`。

***

## 4. 联调验证清单 (Integration Checklist)

启动完毕后，请对照以下清单进行健康检查：

- [ ] **后端接口联通性**: 访问 <http://127.0.0.1:8000/docs> 是否正常渲染 Swagger 页面。
- [ ] **前端页面连通性**: 访问终端提示的 Local URL (通常为 <http://localhost:5173>) 是否展示登录页。
- [ ] **账号登录测试**:
  - 学生端测试账号: `student` / `123456`
  - 教师端测试账号: `teacher` / `123456`
  - 登录成功后应能正常获取 `Token` 并跳转至对应 Dashboard。
- [ ] **AI 接口连通性**: 登录学生端后，点击【心理报告】或【AI 对话】，确认页面不会出现 `DeepSeek API call failed` 的红色报错，并能正常渲染大模型生成的文字。
- [ ] **缓存与热更新机制**:
  - 修改任意 Vue 文件保存，浏览器应自动更新且无需手动刷新。
  - 刷新心理报告页，确认控制台 Network 中 `/api/student/report/analysis` 接口返回 `304 Not Modified`（ETag 缓存命中）。

***

## 5. 故障排查附录 (Troubleshooting)

### 🚨 错误 1: 端口被占用 (Port is already in use)

**现象 (前端)**: `Port 5173 is in use, trying another one...`
**现象 (后端)**: `[Errno 10048] error while attempting to bind on address ('0.0.0.0', 8000)`
**排查解决**:

```powershell
# Windows (查找并杀死 8000 端口占用进程)
netstat -ano | findstr :8000
taskkill /PID <对应的PID> /F

# Mac/Linux
lsof -i :8000
kill -9 <对应的PID>
```

### 🚨 错误 2: 后端提示 ModuleNotFoundError

**现象**: `ModuleNotFoundError: No module named 'fastapi'` 或 `No module named 'app'`
**排查解决**:

1. 检查是否在执行 `uvicorn` 前**忘记激活虚拟环境** (`source .venv/bin/activate`)。
2. 检查命令执行目录：**必须在** **`backend`** **目录下**执行 `uvicorn app.main:app`，因为 Python 解释器需要将 `backend` 视为根路径来解析 `app.` 包。

### 🚨 错误 3: 前端 API 请求全部报 404 / 网络错误

**现象**: 登录点击无反应，Network 标签页显示 `http://localhost:5173/api/login` 返回 404，或连接被拒。
**排查解决**:
这说明前端 Vite 代理无法连接到后端。请确保：

1. 后端终端未报错退出，且 `uvicorn` 正在监听 `8000` 端口。
2. 检查 `vite.config.js` 的 `server.proxy` 配置目标地址是否为 `http://127.0.0.1:8000`。

### 🚨 错误 4: PowerShell 无法运行 .venv\Scripts\activate

**现象**: `无法加载文件 .venv\Scripts\activate.ps1，因为在此系统上禁止运行脚本。`
**排查解决**:
以管理员身份打开 PowerShell 并运行以下命令放开权限：

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 🚨 错误 5: AI 对话 / 心理报告模块返回报错

**现象**: 页面上方提示 `"AI 服务暂时不可用，请稍后再试。"` 或报告页面白屏卡死。
**排查解决**:
后端控制台会打印 `DeepSeek API call failed: ...`。这是由于 `backend/.env` 中的 `DEEPSEEK_API_KEY` 为空或无效。请申请有效的 Key 并填入 `.env` 文件后，**重启后端服务**。
