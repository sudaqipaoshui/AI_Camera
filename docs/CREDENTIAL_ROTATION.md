# 凭据轮换手册

> 背景：这批凭据曾以明文形式散落在仓库多个文件、多台机器上，且仓库曾无版本控制（无法确认是否外传）。
> **仅从代码里删除不等于安全** —— 只要口令本身没变，任何曾经拿到过文件的人依然能登录。
> 因此必须做实际的轮换。

> 本文档**刻意不记录任何明文口令**。轮换完成前，明文出现在仓库里的任何一份文件中都是持续风险，
> 因此这里只描述"要改哪一个"，不写"改成什么"。需要比对时请查本机 `.env`（不入库）。

本文档只描述操作步骤。**涉及设备/平台侧的实际变更，需你确认后执行，不要擅自改。**

---

## 一、泄露清单

按风险从高到低。"原值特征"用于你核对是哪一条，不足以还原口令。

| # | 凭据（变量名） | 原值特征 | 曾出现位置 |
|---|---------------|---------|-----------|
| 1 | 设备 `root` SSH 口令<br>`CAMERA_SSH_PASSWORD` | 8 位小写字母 + 数字，开发默认值 | `config/test/camera.yaml`、`API/pytest_helper/e2e_helper.py`(6处)、`E2E/pytest_helper/e2e_helper.py`(6处)、`E2E/tests/run/test_00_run_20251111_800_4r_wtzx_sample_latest.py`(6处)、`deploy_camera.sh`、`docs/README_DEPLOY.md`(4处)、`Log/diag_60*.py`、`Log/tmp_status.py`、`Log/tmp_type3_*.py` |
| 2 | 设备 `rm` 用户 SSH 口令 | 9 位，含 `#` 符号 | `Stability/README.md`、`stability_test.sh` |
| 3 | MySQL 账号 `uad_test_rw` 口令<br>`UAD_MYSQL_PASSWORD` | 16 位，含 `!` | `config/test/yuntiyu.yaml`、`config/test/yunketang.yaml` |
| 4 | 云平台账号 `mqxx2024` 口令<br>`YUNTIYU_ACCOUNT_PASSWORD` | 10 位，含 `@` | `config/test/camera.yaml` |
| 4b | 同上口令的 MD5<br>`YUNTIYU_ACCOUNT_ENCODE_PASSWORD` | 32 位十六进制 | `config/test/camera.yaml`、`API/data/settings/test_login.yaml`(3处) |
| 5 | 摄像头接口 JWT<br>`YUNTIYU_X_TOKEN` | 标准 JWT，`sub=mqxx2024`，`exp` 约 2071 年 | `config/test/camera.yaml` |
| 6 | 应用签名 secret ×5<br>`YUNTIYU_SECRET_*` | 32 位十六进制 ×5 | `config/test/yuntiyu.yaml` |
| 7 | 设备授权码 `licence`<br>`CAMERA_LICENCE` | 64 位十六进制 | `config/test/camera.yaml` |
| 8 | OpenSSH 私钥 | 文件 `config/id_rsa_ai_camera`，**全项目无任何代码引用** | 文件本身 |
| 9 | 设备侧持久 token | 设备 `item.json` 的 `token` 字段，`loginAccount` 可见 | `Log/tmp_item*.json` 转储 |

---

## 二、轮换顺序

原则：**从影响面小、可回滚的开始；先确认新口令可用，再废掉旧的。**

### 第 0 步：准备（不碰任何线上）

- [ ] 确认项目根存在 `.env`，且内容已核对
- [ ] 备份当前 `.env`：`cp .env .env.bak_$(date +%Y%m%d)`
- [ ] 保留一个**已登录的 SSH 会话**不要退出（万一改密后新口令不生效，还能从这个会话救回来）

### 第 1 步：云平台账号口令（风险最低，可自行回滚）

1. 在 yuntiyu-test 平台修改 `mqxx2024` 的密码
2. 重新计算 MD5：`python -c "import hashlib;print(hashlib.md5('新密码'.encode()).hexdigest())"`
3. 更新 `.env`：
   - `YUNTIYU_ACCOUNT_PASSWORD`
   - `YUNTIYU_ACCOUNT_ENCODE_PASSWORD`（填上面算出的 MD5）
4. 重新登录一次拿新的 `YUNTIYU_X_TOKEN`，更新 `.env`
5. 验证：`python -m pytest API/tests/settings/test_login.py -v`

> **如何拿新的 X_TOKEN（2026-09-17 实测，无需网页验证码）**：
> 平台网页登录才要图形验证码；**设备 API 不需要**。直接
> `POST {host.camera}/camera/login`，body 为
> `{"username": <账号>, "encodePassword": <口令的MD5>}`，
> 返回 `code:0`，新 token 在 `data.authorization`（JWT，sub=账号名，
> 含 deviceUnicode 绑定设备，exp 约 50 年）。
> 拿到后：① 更新 `.env` 的 `YUNTIYU_X_TOKEN`；
> ② 验证 `GET {host.camera}/camera/ping`（header `x_token`）应返回 `code:0`。
> 注意账号必须已与该设备绑定，否则登录返回业务 405（换绑要走平台解绑/激活码，
> 见 MEMORY.md「换绑账号」）。
> `YUNTIYU_API_TOKEN` 是另一套 app 端 token（yuntiyu.yaml，配 secret 自动刷新），无需手动换。

### 第 2 步：MySQL 测试账号（需 DBA 配合）

建议借这次机会把 `uad_test_rw`（读写）**降级为只读账号** —— 自动化测试不需要写权限。

1. 请 DBA 改密并调整权限
2. 更新 `.env` 的 `UAD_MYSQL_PASSWORD`
3. 验证：跑一遍用到 DB 的用例

### 第 3 步：设备 SSH 口令（影响面最大，最后做）

设备：X5 `192.168.2.60`（当前主用）、以及所有其他在用的 X3/X5 机器。

**单台操作顺序：**

1. SSH 登录设备
2. 改密：`passwd root`（或 `passwd rm`）
3. **先不退出当前会话**，另开一个终端用新口令登录，确认能进
4. 确认成功后更新 `.env` 的 `CAMERA_SSH_PASSWORD`
5. 逐台重复

⚠️ 注意：`config/test/camera.yaml` 里 `ssh_user: root`，而 `Stability/README.md` 里用的是 `rm` 用户 —— 两台机器的账号体系不一致。改密前先确认每台机器实际用哪个账号。

⚠️ 另有一处**仓库外**的同口令残留：设备本机 `/userdata/camera_config/rtsp_config.json` 里
`rtsp_link_info.channel0.passwd` 存着同一个口令（用于拉取 sensor 相机流）。
该文件在设备上，不随改密自动更新 —— 改设备口令时一并核对，否则注入/拉流可能失效。

> **2026-09-17 实测补充（.60 出厂态）**：`rtsp_config.json` 的 `channel0` 是
> `user=admin`、`camera_ip=192.168.1.167`（sensor 摄像头模块），passwd 与设备 root
> SSH 口令**当前同值**。两者是独立系统、各自校验：只改设备 root 密码不影响拉流
> （rtsp 配置与 sensor 模块侧都不动）；但若改 sensor 模块的 admin 密码，必须同步
> 设备上的 `rtsp_config.json` 并 reboot。

**所有设备改完后**，仓库里 7 个文件的残留明文就彻底失效了。

### 第 4 步：私钥处置

`config/id_rsa_ai_camera` 是明文私钥，但**全项目搜不到任何引用**。

- [ ] 确认没有仓库外的脚本/工具在用（问一下同事）
- [ ] 若无引用 → 移出仓库（如 `~/.ssh/`）或直接删除
- [ ] 若曾在生产环境用过 → 从目标机器的 `authorized_keys` 中移除对应公钥
- [ ] 已在 `.gitignore` 中排除，不会再入库

### 第 5 步：视为无法轮换的项

| 项 | 说明 | 处理 |
|---|------|------|
| `licence` | 设备授权码，通常与硬件绑定、由厂商签发 | 风险接受；确认它是否真的敏感（部分产品 licence 只是功能开关） |
| app secret ×5 | 平台侧签名密钥 | 若平台支持重置则重置；否则记录在风险台账 |
| 设备侧持久 token | 设备 `item.json` 里的 token | 重新登录/同步会刷新；已通过 `.gitignore` 阻止转储文件入库 |

---

## 三、轮换后的验证清单

```bash
# 1. 凭据加载正常
python envloader.py

# 2. 配置可解析且占位符全部展开
python -c "
import envloader
for f in ['config/test/camera.yaml','config/test/yuntiyu.yaml','config/test/yunketang.yaml']:
    envloader.load_yaml(f); print('OK', f)
"

# 3. 用例仍可收集
python -m pytest --collect-only -q

# 4. 设备连通性（会真实连设备）
python -c "
import sys; sys.path.insert(0,'.')
import envloader, paramiko
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.2.30', 22, 'root', envloader.require('CAMERA_SSH_PASSWORD'), timeout=8)
_, so, _ = c.exec_command('hostname; uptime')
print(so.read().decode())
c.close()
"

# 5. 仓库内不应再有任何明文凭据(通用模式扫描, 不列举具体值)
git grep -nIE "(password|passwd|secret|token|licence|license)\s*[:=]\s*[\"']?[A-Za-z0-9!@#$%^&*_+=-]{8,}" \
  -- ':!*.md' ':!*.example' || echo "干净"
```

---

## 四、回滚

- **云平台 / MySQL**：管理员改回原值即可
- **设备 SSH**：若新口令登录失败，用第 0 步保留的旧会话重新 `passwd`
- **`.env`**：从 `.env.bak_YYYYMMDD` 恢复

---

## 五、后续防复发

- [ ] 提交前自查：`git diff --cached | grep -iE "password|token|secret|passwd"`（推荐做成 pre-commit hook）
- [ ] `.env` 永不入库；新增变量同步 `.env.example`
- [ ] 代码里禁止出现口令兜底默认值（`envloader.require` 会直接报错，这是刻意设计）
- [ ] 定期轮换（建议随固件大版本发布同步做）
- [ ] 条件允许时改用密钥认证替代口令，或上堡垒机统一管控

---

## 六、执行进度

| 日期 | 项 | 结果 |
|---|---|---|
| 2026-09-17 | 第 0 步准备 | `.env` 已备份（`.env.bak_20260917_152147`） |
| 2026-09-17 | 第 1 步 X_TOKEN | 旧 token 已失效（403）；经设备 API 重新登录（免验证码，方法见第 1 步内注释）取得新设备绑定 token，已写入 `.env` 并用 `/camera/ping` 验证 `code:0`；`test_login.py` 2 passed |
| 2026-09-17 | 第 3 步设备 SSH | **用户决定暂不改**（维持现值）；另 `config/id_rsa_ai_camera` 已移出仓库留档 |
| 待办 | 第 2/3 步 | MySQL 账号降级+改密（需 DBA）、设备 SSH 改密（影响面最大） |
