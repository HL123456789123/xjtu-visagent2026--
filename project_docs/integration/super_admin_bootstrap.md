# Docker 环境首次创建超级管理员

本流程适用于已经使用 Docker Compose 启动 VisAgent，但数据库中还没有有效超级管理员的电脑。初始化工具不会把账号或密码写入 `.env`、Git、PowerShell 历史或应用日志。

## 一、更新并重建后端

在 VisAgent 仓库根目录打开 PowerShell。先确认当前代码包含以下两个文件：

```text
scripts/bootstrap_super_admin.ps1
backend/scripts/bootstrap_super_admin.py
```

由于 Python 初始化工具需要进入后端镜像，因此第一次获取该功能后需要重建并重启后端：

```powershell
docker compose build backend
docker compose up -d --force-recreate backend
docker compose ps
```

确认 `backend` 为 `Up` 或 `healthy` 后继续。

## 二、运行一键初始化脚本

仍在仓库根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_super_admin.ps1
```

如果启动项目时显式使用了 Compose 项目名，例如 `docker compose -p visagent-demo up -d`，则执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap_super_admin.ps1 -ProjectName visagent-demo
```

## 三、根据提示创建或提升账号

### 方案 A：创建新账号

1. 输入新的用户名。
2. 输入未被使用的邮箱。
3. 输入至少 12 个字符且同时包含字母和数字的密码。
4. 再次输入密码。
5. 输入大写的 `CREATE` 确认。

密码输入时终端不会显示字符，这是正常的安全行为。

### 方案 B：提升已经注册的账号

1. 输入已存在且处于启用状态的用户名。
2. 脚本识别到账号后，输入大写的 `PROMOTE` 确认。

该操作会把此账号的产品角色统一调整为 `super_admin`。

## 四、登录验证

打开：

```text
http://127.0.0.1:3000
```

使用刚创建或提升的账号登录。顶部导航应出现“模型管理”和“用户管理”，用户信息接口返回的角色应包含 `super_admin`。

## 五、安全限制

- 数据库中已经存在有效超级管理员时，脚本会直接拒绝执行。
- 网页和普通管理 API 仍不能授予 `super_admin`，不会形成远程提权入口。
- 脚本不会显示、保存或记录密码。
- 不要把账号密码写进脚本、`.env`、README、聊天记录或 Git。
- 不要通过删除数据库卷来重新初始化管理员。
- 忘记密码时应使用管理员密码重置流程；不要重复运行 Bootstrap 创建第二个超级管理员。

## 六、常见问题

### 提示 backend service is not running

在仓库根目录执行：

```powershell
docker compose up -d
docker compose ps
```

### 提示脚本文件不存在

说明后端容器仍然使用旧镜像。执行：

```powershell
docker compose build backend
docker compose up -d --force-recreate backend
```

### 提示 active super administrator already exists

当前数据库已经有有效超级管理员，应由该账号在“用户管理”中管理普通管理员；Bootstrap 不允许再次创建超级管理员。
