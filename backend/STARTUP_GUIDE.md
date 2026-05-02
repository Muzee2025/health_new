# 🚀 项目启动问题排查指南

## ❌ 常见问题及解决方案

### 问题1：PyCharm 无法识别模块 (Import Error)
**症状**：运行时报 `ModuleNotFoundError` 或 `Cannot import name 'xxx'`

**原因**：PyCharm 的 Python 解释器没有正确配置

**解决方案**：
1. 打开 PyCharm 设置：`File` → `Settings` → `Project` → `Python Interpreter`
2. 点击右上角的 ⚙️ 设置图标
3. 选择 `Add...` 添加新的解释器
4. 选择 `Existing environment`
5. 浏览选择 `.venv\Scripts\python.exe`（注意：是 **Scripts** 目录下的 python.exe，不是根目录的）
6. 点击 `OK` 确认

或者更简单的方法：
1. `Settings` → `Python Interpreter`
2. 点击下拉框，选择 `.venv\Scripts\python.exe`

---

### 问题2：环境变量没有加载 (.env)
**症状**：报 `DATABASE_URL` 相关的错误

**原因**：`.env` 文件没有被加载

**解决方案**：

**方案A：PyCharm 配置运行参数（推荐）**
1. 点击 `Run` → `Edit Configurations...`
2. 选择或创建 `app.main` 的运行配置
3. 在 `Working directory` 中设置为：`D:\Muzee\develop\IDEA_code\health_new\backend`
4. 在 `Environment variables` 中添加：
   ```
   PYTHONPATH=D:\Muzee\develop\IDEA_code\health_new\backend
   ```
5. 点击 `Apply` → `OK`

**方案B：修改代码确保加载 .env（已配置）**
检查 `backend/app/main.py` 是否已加载 `.env`：
```python
from dotenv import load_dotenv
load_dotenv()  # 只需要这一行，会自动找 .env 文件
```

---

### 问题3：直接在 PyCharm 中运行 main.py 失败
**症状**：点击绿色运行按钮直接运行 `main.py` 报错

**原因**：
1. 工作目录不对
2. 没有使用虚拟环境中的 Python

**解决方案**：

**正确的方式**：
1. 右键点击 `main.py`
2. 选择 `Run 'main'` - 前提是 Python 解释器已正确配置

**或者使用 uvicorn 命令启动**：
1. 打开 PyCharm 的 Terminal
2. 进入 backend 目录：`cd backend`
3. 激活虚拟环境：`.venv\Scripts\activate`
4. 运行：`uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

---

### 问题4：端口被占用
**症状**：`Port 8000 is already in use`

**解决方案**：
1. 打开任务管理器，结束 `python.exe` 或 `uvicorn` 相关进程
2. 或者更换端口：`uvicorn app.main:app --port 8001`

---

## ✅ 正确的启动方式

### 方式一：使用 PyCharm（推荐）

**Step 1：配置 Python 解释器**
```
Settings → Project → Python Interpreter
→ Add → Existing environment
→ 选择: D:\Muzee\develop\IDEA_code\health_new\backend\.venv\Scripts\python.exe
```

**Step 2：配置运行配置**
```
Run → Edit Configurations
→ + New Configuration
→ Module name: uvicorn
→ Parameters: app.main:app --reload --host 0.0.0.0 --port 8000
→ Working directory: D:\Muzee\develop\IDEA_code\health_new\backend
→ Python interpreter: 选择上面的 .venv
```

**Step 3：运行**
直接点击绿色 ▶️ 运行按钮

---

### 方式二：使用终端命令行

**Step 1：打开终端**
```powershell
cd D:\Muzee\develop\IDEA_code\health_new\backend
```

**Step 2：激活虚拟环境**
```powershell
.venv\Scripts\activate
```
（如果提示执行策略错误，先运行：`Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`）

**Step 3：运行**
```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Step 4：看到以下输出表示成功**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

---

### 方式三：直接运行脚本（不推荐）

如果一定要直接运行 `main.py`：

1. 在 `backend/app/main.py` 开头添加：
```python
import sys
import os
from pathlib import Path

# 将 backend 目录加入 Python 路径
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))
os.chdir(backend_dir)

from dotenv import load_dotenv
load_dotenv()  # 加载 .env 文件
```

2. 右键 `main.py` → `Run 'main'`

---

## 🔧 快速检查清单

在运行前，请确认以下几点：

- [ ] **Python 解释器**：PyCharm 中选择的是 `.venv\Scripts\python.exe`
- [ ] **工作目录**：`backend` 文件夹
- [ ] **依赖安装**：终端中运行 `.venv\Scripts\activate` 后没有报错
- [ ] **端口空闲**：8000 端口没有被其他程序占用

---

## 📝 常见错误对照表

| 错误信息 | 原因 | 解决方法 |
|---------|------|---------|
| `ModuleNotFoundError: No module named 'fastapi'` | 虚拟环境未激活或未安装依赖 | 运行 `pip install -r requirements.txt` |
| `ModuleNotFoundError: No module named 'app'` | 工作目录不对或 PYTHONPATH 未设置 | 设置 Working directory 为 backend 目录 |
| `can't open file 'app\main:app'` | 命令格式错误 | 使用 `uvicorn app.main:app` |
| `Port 8000 is already in use` | 端口被占用 | 结束相关进程或换端口 |
| `DATABASE_URL not found` | .env 未加载 | 确保 `load_dotenv()` 被调用 |

---

## 🎯 推荐的 PyCharm 配置步骤

1. **设置项目根目录**
   - `File` → `Settings` → `Project Structure`
   - 将 `backend` 目录标记为 `Sources`

2. **配置 Python 解释器**
   - `Settings` → `Python Interpreter`
   - 选择 `.venv\Scripts\python.exe`

3. **创建运行配置**
   - `Run` → `Edit Configurations`
   - Type: `Module name`
   - Module: `uvicorn`
   - Parameters: `app.main:app --reload --host 0.0.0.0 --port 8000`
   - Working directory: `D:\Muzee\develop\IDEA_code\health_new\backend`

4. **运行**
   - 点击 ▶️ 运行

---

## 📞 如果还有问题

请告诉我：
1. PyCharm 报错的具体信息（完整的错误文字）
2. 你使用的启动方式（点击运行按钮 / 使用终端 / 其他）
3. Python Interpreter 显示的路径是什么

我会帮您进一步排查！
