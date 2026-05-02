# 心域智链 - 项目启动指南

## 环境要求

- **Node.js**: 18.x 或更高版本 ([下载链接](https://nodejs.org/))
- **Python**: 3.10 或更高版本 ([下载链接](https://www.python.org/downloads/))
- **数据库**: SQLite (随项目自动创建，无需安装)

---

## 快速启动（推荐）

### 方式一：使用批处理文件一键启动

#### 启动后端
```bash
双击运行 "启动后端.bat"
```
脚本会自动：
1. 检测/创建 Python 虚拟环境
2. 安装后端依赖
3. 初始化数据库
4. 启动 FastAPI 服务 (http://127.0.0.1:8000)

#### 启动前端
```bash
双击运行 "启动前端.bat"
```
脚本会自动：
1. 检测 Node.js 是否安装
2. 安装前端依赖（首次运行）
3. 启动 Vite 开发服务器 (http://localhost:5173)

---

### 方式二：命令行手动启动

#### 步骤 1：启动后端

```powershell
# 进入后端目录
cd d:\Muzee\develop\IDEA_code\health_new\backend

# 激活虚拟环境
.venv\Scripts\activate

# 安装依赖（首次运行）
pip install -r requirements.txt

# 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 步骤 2：启动前端

```powershell
# 新开一个终端，进入项目根目录
cd d:\Muzee\develop\IDEA_code\health_new

# 安装依赖（首次运行）
npm install

# 启动开发服务器
npm run dev
```

---

## 验证启动成功

### 后端验证
- 访问 http://127.0.0.1:8000/docs
- 应该看到 FastAPI 自动生成的 API 文档

### 前端验证
- 访问 http://localhost:5173
- 应该看到登录页面

### 登录测试账号
| 角色 | 用户名 | 密码 |
|------|--------|------|
| 学生 | `student` | `123456` |
| 教师 | `teacher` | `123456` |

---

## AI 对话功能说明

学生端的 AI 心理助手功能位于 `/student/chat` 路由。

### 工作原理
1. 前端发送消息到 `POST /api/student/chat`
2. 后端通过 `student.py` 的 `chat_with_ai` 函数处理
3. 使用 DeepSeek API 生成回复

### 故障排查
如果 AI 对话功能不可用，请检查：
1. `.env` 文件中是否配置了 `DEEPSEEK_API_KEY`
2. 后端控制台是否有报错
3. API Key 是否有效

---

## 常见问题

### Q1: 双击 .bat 文件没有反应
**解决方案**：
1. 右键 .bat 文件，选择"用PowerShell运行"或"用命令提示符运行"
2. 或者在文件所在目录打开终端，手动运行 bat 文件

### Q2: 端口被占用 (Port 8000/5173 is already in use)
**解决方案**：
```powershell
# 查找占用端口的进程
netstat -ano | findstr :8000
# 结束进程（将 PID 替换为实际进程ID）
taskkill /PID <PID> /F
```

### Q3: pip install 报错
**解决方案**：
```powershell
# 确保使用虚拟环境中的 pip
.venv\Scripts\pip install -r requirements.txt
```

### Q4: npm install 失败
**解决方案**：
```powershell
# 清除缓存后重试
npm cache clean --force
npm install
```

---

## 目录结构说明

```
health_new/
├── 启动前端.bat          # 前端启动脚本
├── 启动后端.bat          # 后端启动脚本
├── backend/
│   ├── app/
│   │   ├── main.py      # FastAPI 入口
│   │   ├── routers/     # API 路由
│   │   │   ├── student.py  # 学生端 API (含 chat)
│   │   │   └── teacher.py  # 教师端 API
│   │   └── services/    # 业务逻辑
│   │       └── local_llm_service.py  # LLM 服务
│   ├── .env             # 环境配置
│   └── requirements.txt # Python 依赖
├── src/
│   └── views/
│       └── student/
│           └── Chat.vue # AI 对话界面
└── package.json         # 前端依赖
```
