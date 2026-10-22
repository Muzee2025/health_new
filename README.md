# 心域智链

> owner: A ｜ version: 0.2 ｜ status: 评审 ｜ updated: 2026-10-22

心域智链是一个前后端分离的校园心理支持系统，包含学生端、教师端和后端 API。当前进入 W2 认证、师生权限与业务页面改造，**尚未达到上线标准**；校内 Linux + Docker 是部署目标。当前进度见[看板](docs/team/进度看板.md)，验证结论见[门禁记录](docs/team/门禁记录.md)，完整文档见[索引](docs/README.md)。

## 本地启动

完整前端工具链需要 Node.js 22.12+（22.x）、24.x或26+，推荐24.x；Python需要3.10+，本机使用3.12。Vite自身允许Node20.19，但当前Vitest5不支持Node20。下述后端安装及uvicorn命令从`backend/`目录运行，隔离测试runner从仓库根目录运行。请勿覆盖已有数据库、上传文件或本地运行目录。

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
   ..\.venv\Scripts\python.exe -m uvicorn app.main:app --env-file .env --reload --host 127.0.0.1 --port 8000
   ```

   Linux/macOS 在仓库根目录运行 `python3.12 -m venv .venv`（或使用已安装的 3.10+ 解释器），然后在 `backend/` 目录运行 `../.venv/bin/python -m pip install -r requirements.txt` 和 `../.venv/bin/python -m uvicorn app.main:app --env-file .env --reload --host 127.0.0.1 --port 8000`。

   启动前按 `backend/.env.example` 配置 `DATABASE_URL`、随机生成的 `JWT_SECRET_KEY` 与浏览器来源白名单；不提交真实密钥。应用不自动发现dotenv，以上命令通过`--env-file .env`明确选择`backend/.env`；也可由进程环境直接注入并省略该参数。签名密钥至少32字节，空值和占位值会拒绝启动；旧版凭据须重新登录。默认 `requirements.txt` 仅安装轻量 Web 依赖，向量索引默认关闭；`requirements-optional.txt` 为显式可选模型/RAG依赖，本轮未安装或验证真实模型。启用RAG还需显式索引路径与模型下载许可。应用不自动建表；现有数据库先备份再由操作员评审迁移，显式新空库初始化工具见[隔离验证说明](docs/ops/W2开发与隔离验证.md)。本轮未对运行库执行迁移。

3. 打开 Vite 终端显示的本地地址（通常为 `http://localhost:5173`）；API 文档地址为 `http://127.0.0.1:8000/docs`。前端路由以 [src/router/index.js](src/router/index.js) 为准：学生端聊天页为 `/student/advanced-chat`，教师端入口为 `/teacher/advanced-dashboard`。历史账号、功能或运行说明须先对照代码及基线报告确认。

详见 [快速启动](QUICK_START.md)。旧的 SETUP_AND_RUN 文件保留为兼容入口，跳转至本页。

## 隔离验证

在仓库根目录安装 `backend/requirements-test.txt` 后运行 `.\.venv\Scripts\python.exe scripts/run-backend-baseline.py`；该入口使用临时SQLite和上传目录，禁用dotenv/RAG并拦截Python层外连。直接收集后端测试会被拒绝，避免应用导入访问既有数据。它是防止测试误连的运行保护，不是隔离恶意原生代码的沙箱。

前端检查为 `npm test`、`npm run build`、`npm run assets:check`。业务截图通过合成API产生，不能据此声称真实学生数据、外部模型或生产部署已验证。

## 当前状态与文档

校内 Linux + Docker 部署尚未落地，现有功能、安全、数据保护、备份恢复和测试状态须以基线报告核验；本说明不构成部署或上线保证。文档状态及归档材料见 [文档索引](docs/README.md)。
