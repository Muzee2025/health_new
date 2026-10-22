# 心域智链

> owner: A ｜ version: 0.3 ｜ status: 评审 ｜ updated: 2026-10-22

心域智链是一个前后端分离的校园心理支持系统，包含学生端、教师端和后端 API。当前进入 W2 认证、师生权限与业务页面改造，**尚未达到上线标准**；校内 Linux + Docker 是部署目标。当前进度见[看板](docs/team/进度看板.md)，验证结论见[门禁记录](docs/team/门禁记录.md)，完整文档见[索引](docs/README.md)。

## 本地启动

完整前端工具链需要 Node.js 22.12+（22.x）、24.x或26+，推荐24.x；Python需要3.10+，本机使用3.12。Vite自身允许Node20.19，但当前Vitest5不支持Node20。以下命令从仓库根目录运行。请勿覆盖已有数据库、上传文件或本地运行目录。

1. 在仓库根目录安装前端锁定依赖并启动 Vite：

   ```powershell
   npm ci
   npm run dev
   ```

2. 本机已经准备并启动独立SQLite副本，后端绑定 `127.0.0.1:18080`。重启电脑后，可使用已安装的虚拟环境启动当前部署：

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/start-local-backend.ps1
   ```

   后端已运行时无需再次启动；脚本遇到占用端口会退出，不停止其他进程。`backend/runtime/current.json` 指向本地私有部署目录，数据库、备份、签名配置和日志全部Git忽略。该文件不随源码分发，新检出或新机器须先按[本地数据库部署](docs/ops/本地数据库部署与登录.md)准备新部署；使用 `py -3.12 -m venv .venv`、`.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt` 安装本地环境。

   原数据库与原 `backend/.env` 保留；运行副本只补齐缺失的空分配表，没有自动授权关系。新服务使用独立随机签名配置，不复制外部模型凭据；模型调用尚未联调。准备工具拒绝缺列的旧schema，不把 `create_all` 当通用迁移。禁止运行会删表的旧 `backend/scripts/init_db.py`。这次本地部署发现并保留了1条原有孤儿报告记录，待确认归属。

3. 打开 `http://127.0.0.1:5173/`；API文档为 `http://127.0.0.1:18080/docs`。`/api/health/ready`须返回`service: health-new`与`schema_ready: true`。前端默认代理18080；18081仅供显式隔离验证，8000属于另一项目，禁止回退。前端路由以 [src/router/index.js](src/router/index.js) 为准：学生端聊天页为 `/student/advanced-chat`，教师端入口为 `/teacher/advanced-dashboard`。公开注册只创建学生；教师只能查看明确分配的学生。

详见 [快速启动](QUICK_START.md)。旧的 SETUP_AND_RUN 文件保留为兼容入口，跳转至本页。

## 隔离验证

在仓库根目录安装 `backend/requirements-test.txt` 后运行 `.\.venv\Scripts\python.exe scripts/run-backend-baseline.py`；该入口使用临时SQLite和上传目录，禁用dotenv/RAG并拦截Python层外连。直接收集后端测试会被拒绝，避免应用导入访问既有数据。它是防止测试误连的运行保护，不是隔离恶意原生代码的沙箱。

前端检查为 `npm test`、`npm run build`、`npm run assets:check`。历史业务截图通过合成API产生；本轮另用全新临时SQLite验证真实注册/登录/会话链路，没有使用真实学生账号、模型提供商或生产部署。

## 当前状态与文档

校内 Linux + Docker 部署尚未落地，现有功能、安全、数据保护、备份恢复和测试状态须以基线报告核验；本说明不构成部署或上线保证。文档状态及归档材料见 [文档索引](docs/README.md)。
