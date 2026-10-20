# 心域智链

> owner: A ｜ version: 0.1 ｜ status: 评审 ｜ updated: 2026-10-20

心域智链是一个前后端分离的校园心理支持系统原型，包含学生端、教师端和后端 API。当前仓库仍处于 W0 基线阶段，**尚未达到上线标准**；校内 Linux + Docker 是目标，尚未实现。以仓库代码和 [基线报告](docs/test/基线报告.md) 为准。该报告由 W0 基线任务补齐；项目文档索引见 [docs/README.md](docs/README.md)。

## 本地启动

需要 Node.js 18+、Python 3.10+。后端命令必须从 `backend/` 目录运行。请勿覆盖已有数据库、上传文件或本地运行目录。

1. 在仓库根目录安装前端锁定依赖并启动 Vite：

   ```powershell
   npm ci
   npm run dev
   ```

2. 在仓库根目录创建 Python 3.12 虚拟环境；也可使用其他已安装的 Python 3.10+。本机默认 Python 3.9 不满足后端要求。

   ```powershell
   py -3.12 -m venv .venv
   cd backend
   ..\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

   Linux/macOS 在仓库根目录运行 `python3.12 -m venv .venv`（或使用已安装的 3.10+ 解释器），然后在 `backend/` 目录运行 `../.venv/bin/python -m pip install -r requirements.txt` 和 `../.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`。

   启动前确认本地后端配置满足要求；当前实现可能因缺少 `DATABASE_URL` 无法创建数据库引擎。可参考 `backend/.env.example`，不要将密钥写入文档或提交。环境自检仅输出变量名和设置状态，不展示 `.env` 值。完整 `requirements.txt` 含较重的 RAG/模型依赖，且当前依赖声明存在缺口；W0 未修订这些声明，因此安装和启动成功均未保证。

3. 打开 Vite 终端显示的本地地址（通常为 `http://localhost:5173`）；API 文档地址为 `http://127.0.0.1:8000/docs`。前端路由以 [src/router/index.js](src/router/index.js) 为准：学生端聊天页为 `/student/advanced-chat`，教师端入口为 `/teacher/advanced-dashboard`。历史账号、功能或运行说明须先对照代码及基线报告确认。

详见 [快速启动](QUICK_START.md)。旧的 SETUP_AND_RUN 文件保留为兼容入口，跳转至本页。

## 当前状态与文档

校内 Linux + Docker 部署尚未落地，现有功能、安全、数据保护、备份恢复和测试状态须以基线报告核验；本说明不构成部署或上线保证。文档状态及归档材料见 [文档索引](docs/README.md)。
