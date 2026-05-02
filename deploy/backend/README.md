# 后端独立部署（CentOS/Rocky + Docker Compose）

本方案仅启动一个新的后端容器，使用独立端口 `18080`，不会覆盖你现有服务。

## 1) 服务器准备

```bash
dnf -y install git curl
dnf -y install docker
systemctl enable --now docker
docker --version
docker compose version || true
```

如果 `docker compose` 不可用，可安装插件：

```bash
mkdir -p ~/.docker/cli-plugins
curl -SL https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-x86_64 \
  -o ~/.docker/cli-plugins/docker-compose
chmod +x ~/.docker/cli-plugins/docker-compose
docker compose version
```

## 2) 拉取代码

```bash
mkdir -p /opt/health_new_deploy
cd /opt/health_new_deploy
git clone <你的仓库地址> health_new
cd health_new
```

## 3) 配置环境变量

编辑 `backend/.env`，至少确认以下字段：

- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `QWEN_API_KEY`
- `ZHIPU_API_KEY`
- `FRONTEND_ORIGIN`

> 建议使用与当前生产环境不同的数据库路径，避免互相影响。

## 4) 启动（独立项目名）

```bash
cd /opt/health_new_deploy/health_new
docker compose -f deploy/backend/docker-compose.backend.yml -p healthnew_backend up -d --build
```

## 5) 验证

```bash
docker ps | grep health-new-backend
curl -i http://127.0.0.1:18080/
curl -i http://127.0.0.1:18080/docs
```

## 6) 常用运维命令

查看日志：

```bash
docker compose -f deploy/backend/docker-compose.backend.yml -p healthnew_backend logs -f --tail=200
```

重启：

```bash
docker compose -f deploy/backend/docker-compose.backend.yml -p healthnew_backend restart
```

停止：

```bash
docker compose -f deploy/backend/docker-compose.backend.yml -p healthnew_backend down
```
