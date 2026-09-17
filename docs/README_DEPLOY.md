# Deploy 部署脚本使用说明

## 功能

自动化部署 Deploy 安装包到 AI 摄像头，包括：
1. 从指定 URL 下载 Deploy 安装包
2. SSH 连接到摄像头
3. 删除旧的 `/userdata/deploy` 目录（自动备份）
4. 解压安装新的 Deploy 包
5. 重启摄像头（可选）

## 使用方法

### 方法 1: 使用默认配置

```bash
./deploy_camera.sh
```

### 方法 2: 使用命令行参数

```bash
# 部署到单个摄像头（需要手动确认）
./deploy_camera.sh -u https://pic.dream-sports.cn/console/apk-file/2026/02/27/72c980789c9d4f5c9d4c6dd018e6aa6b.rm -i 192.168.2.30 -y

# 自动部署（跳过确认提示）

./deploy_camera.sh -u https://pic.dream-sports.cn/console/apk-file/2026/01/27/e4522f970fbb4149aee6b3f544899f57.rm -i 192.168.3.29 -y
# 部署到多个摄像头
./deploy_camera.sh -u https://pic.dream-sports.cn/console/apk-file/2026/03/18/e48e77a2d82e4208a8e21f44b7d2c682.rm-i 192.168.3.29,192.168.3.30 -y

# 部署后不重启
./deploy_camera.sh -u http://server/deploy.tar.gz -i 192.168.3.29 -n -y

# 使用自定义SSH凭证
./deploy_camera.sh -u http://server/deploy.tar.gz -i 192.168.3.29 -U root -P mypassword -y
```

### 方法 3: 使用配置文件

1. 修改 `deploy_config.sh` 中的配置：

```bash
# 编辑配置文件
vim deploy_config.sh
```

2. 使用配置文件运行：

```bash
source deploy_config.sh && ./deploy_camera.sh \
  -u "$DEPLOY_URL" \
  -i "$CAMERA_IPS" \
  -U "$SSH_USER" \
  -P "$SSH_PASS" \
  -d "$DEPLOY_DIR" \
  $([ "$NO_REBOOT" = true ] && echo "-n" || echo "")
```

## 参数说明

| 参数 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `--url` | `-u` | Deploy 安装包下载 URL | http://192.168.3.178/deploy/deploy_latest.tar.gz |
| `--ip` | `-i` | 摄像头 IP（多个用逗号分隔） | 192.168.3.29 |
| `--user` | `-U` | SSH 用户名 | root |
| `--password` | `-P` | SSH 密码 | 取项目根 `.env` 的 `CAMERA_SSH_PASSWORD` |
| `--deploy-dir` | `-d` | Deploy 目录 | /userdata/deploy |
| `--no-reboot` | `-n` | 部署后不重启 | false |
| `--yes` | `-y` | 跳过确认提示，自动开始部署 | false |
| `--help` | `-h` | 显示帮助信息 | - |

## 依赖工具

### macOS

```bash
# 安装 sshpass
brew install sshpass

# 或者使用 Homebrew 的第三方源
brew install hudochenkov/sshpass/sshpass
```

### Ubuntu/Debian

```bash
sudo apt-get update
sudo apt-get install sshpass
```

### CentOS/RHEL

```bash
sudo yum install sshpass
```

## 使用示例

### 示例 1: 部署到开发环境摄像头

```bash
./deploy_camera.sh \
  -u http://192.168.3.178/deploy/deploy_dev_20250108.tar.gz \
  -i 192.168.3.29
```

### 示例 2: 批量部署到多个测试摄像头

```bash
./deploy_camera.sh \
  -u http://192.168.3.178/deploy/deploy_test.tar.gz \
  -i 192.168.3.28,192.168.3.29,192.168.3.30
```

### 示例 3: 部署到生产环境（不自动重启）

```bash
./deploy_camera.sh \
  -u http://production-server/deploy/deploy_prod.tar.gz \
  -i 192.168.1.100 \
  -n
```

### 示例 4: 使用环境变量 / .env

推荐做法: 项目根放 `.env`(已被 .gitignore 排除), 内容 `CAMERA_SSH_PASSWORD=<真实口令>`,
脚本会自动读取, 无需在命令行传密码。

```bash
export DEPLOY_URL="http://192.168.3.178/deploy/deploy_latest.tar.gz"
export CAMERA_IP="192.168.3.29"
export SSH_PASS="$CAMERA_SSH_PASSWORD"   # 口令来自 .env / 环境变量

./deploy_camera.sh -u "$DEPLOY_URL" -i "$CAMERA_IP" -P "$SSH_PASS"
```

## 部署流程

脚本会按以下步骤执行：

```
1. 检查依赖 (sshpass, wget/curl)
   ↓
2. 下载 Deploy 安装包（到本地临时目录）
   ↓
3. SSH 连接测试
   ↓
4. 备份并删除旧的 /userdata/deploy 目录
   ↓
5. 上传压缩包到摄像头 /tmp 目录
   ↓
6. 在摄像头上解压安装包到 /userdata/ 目录
   ↓
7. 设置权限并清理摄像头上的临时文件
   ↓
8. 重启摄像头 (可选)
   ↓
9. 清理本地临时文件
```

**注意**：
- 解压操作在摄像头上执行，节省本地空间和传输时间
- 压缩包会解压到 `/userdata/` 目录，保留压缩包内的目录结构（如 `deploy/`）

## 安全注意事项

1. **密码安全**：
   - 不要在命令行中直接输入密码（会被记录在历史中）
   - 使用配置文件或环境变量
   - 或者使用 SSH 密钥认证

2. **备份**：
   - 脚本会自动备份旧版本到 `/userdata/deploy.backup`
   - 如果部署失败，可以手动恢复：
     ```bash
     ssh root@192.168.3.29 "mv /userdata/deploy.backup /userdata/deploy && reboot"
     ```

3. **测试环境**：
   - 建议先在测试环境验证
   - 确认新版本正常后再部署到生产环境

## 故障排查

### 问题 1: SSH 连接失败

```bash
# 手动测试 SSH 连接
ssh root@192.168.3.29

# 检查网络连通性
ping 192.168.3.29
```

### 问题 2: sshpass 未安装

```bash
# macOS
brew install hudochenkov/sshpass/sshpass

# Linux
sudo apt-get install sshpass  # Ubuntu/Debian
sudo yum install sshpass      # CentOS/RHEL
```

### 问题 3: 下载失败

```bash
# 手动测试下载
wget http://192.168.3.178/deploy/deploy_latest.tar.gz
# 或
curl -O http://192.168.3.178/deploy/deploy_latest.tar.gz
```

### 问题 4: 解压失败

```bash
# 检查压缩包是否完整
tar -tzf deploy_latest.tar.gz

# 手动解压测试
tar -xzf deploy_latest.tar.gz
```

## 日志和调试

启用详细输出：

```bash
# 添加调试信息
bash -x ./deploy_camera.sh -u URL -i IP
```

## 集成到 CI/CD

### Jenkins Pipeline 示例

```groovy
pipeline {
    agent any
    
    stages {
        stage('Deploy to Cameras') {
            steps {
                sh '''
                    ./deploy_camera.sh \
                        -u ${DEPLOY_URL} \
                        -i ${CAMERA_IPS} \
                        -U ${SSH_USER} \
                        -P ${SSH_PASS}
                '''
            }
        }
    }
}
```

### GitHub Actions 示例

```yaml
name: Deploy to Cameras

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Install sshpass
        run: sudo apt-get install -y sshpass
      
      - name: Deploy
        env:
          DEPLOY_URL: ${{ secrets.DEPLOY_URL }}
          CAMERA_IPS: ${{ secrets.CAMERA_IPS }}
          SSH_PASS: ${{ secrets.SSH_PASS }}
        run: |
          ./deploy_camera.sh \
            -u "$DEPLOY_URL" \
            -i "$CAMERA_IPS" \
            -P "$SSH_PASS"
```

## 配置文件模板

根据不同环境创建配置文件：

### 开发环境 (deploy_config_dev.sh)

```bash
DEPLOY_URL="http://192.168.3.178/deploy/deploy_dev.tar.gz"
CAMERA_IPS="192.168.3.29"
SSH_USER="root"
# 口令不写进配置文件, 从项目根 .env 的 CAMERA_SSH_PASSWORD 读取
SSH_PASS="${CAMERA_SSH_PASSWORD:?请先设置 CAMERA_SSH_PASSWORD}"
NO_REBOOT=false
```

### 测试环境 (deploy_config_test.sh)

```bash
DEPLOY_URL="http://192.168.3.178/deploy/deploy_test.tar.gz"
CAMERA_IPS="192.168.3.28,192.168.3.29"
SSH_USER="root"
# 口令不写进配置文件, 从项目根 .env 的 CAMERA_SSH_PASSWORD 读取
SSH_PASS="${CAMERA_SSH_PASSWORD:?请先设置 CAMERA_SSH_PASSWORD}"
NO_REBOOT=false
```

### 生产环境 (deploy_config_prod.sh)

```bash
DEPLOY_URL="http://prod-server/deploy/deploy_prod.tar.gz"
CAMERA_IPS="192.168.1.100,192.168.1.101"
SSH_USER="root"
SSH_PASS="prod_password"
NO_REBOOT=true  # 生产环境建议手动重启
```

## 高级用法

### 1. 部署前备份配置文件

```bash
# 修改脚本，在删除前备份配置
ssh root@192.168.3.29 "cp -r /userdata/deploy/configs /tmp/configs_backup"
```

### 2. 部署后验证

```bash
# 等待重启后验证服务
sleep 60
ssh root@192.168.3.29 "ps aux | grep daemon_services"
```

### 3. 批量部署脚本

创建 `batch_deploy.sh`：

```bash
#!/bin/bash
# 读取摄像头列表文件，批量部署
while IFS= read -r camera_ip; do
    echo "部署到: $camera_ip"
    ./deploy_camera.sh -u "$DEPLOY_URL" -i "$camera_ip" -n
done < camera_list.txt
```

## 相关文件

- `deploy_camera.sh` - 主部署脚本
- `deploy_config.sh` - 配置文件模板
- `README_DEPLOY.md` - 本使用说明
- `camera_list.txt` - 摄像头IP列表（可选）

## 技术支持

如有问题，请联系：
- 开发团队
- 提交 Issue 到代码仓库

