# CI 接入指南

本仓库的 CI 是 `.github/workflows/ci.yml`（GitHub Actions），分两个 job：

| job | 跑什么 | 跑在哪 | 需要真机/凭据 |
|---|---|---|---|
| `unit-test` | 16 条纯函数回归（`API/tests/helper/`） | GitHub 云 runner（ubuntu） | 否 |
| `api-test` | 接口用例（`run.py api`） | **内网 self-hosted runner** | 是 |

## 为什么分两层

接口用例 100% 依赖内网设备 `192.168.2.60`（数据文件里的 `{{$.host.camera}}`），
GitHub 云 runner 访问不到内网，所以接口用例必须跑在一台**能访问内网设备**的机器上
（self-hosted runner）。纯函数回归测试不碰设备、不碰凭据，可以放心丢云上跑，保证
「至少有一层永远能绿」。

## 一次性配置步骤

### 1. 配置 GitHub Secrets

仓库 `Settings → Secrets and variables → Actions → New repository secret`，
把 `.env` 里这些值填进去（值别贴进仓库，只放 Secrets）：

| Secret 名 | 对应 .env 变量 | 用途 |
|---|---|---|
| `CAMERA_SSH_PASSWORD` | `CAMERA_SSH_PASSWORD` | 设备 SSH root 口令 |
| `YUNTIYU_ACCOUNT_USERNAME` | `YUNTIYU_ACCOUNT_USERNAME` | 云平台账号 |
| `YUNTIYU_ACCOUNT_PASSWORD` | `YUNTIYU_ACCOUNT_PASSWORD` | 云平台口令 |
| `YUNTIYU_ACCOUNT_ENCODE_PASSWORD` | `YUNTIYU_ACCOUNT_ENCODE_PASSWORD` | 口令 MD5 |
| `YUNTIYU_X_TOKEN` | `YUNTIYU_X_TOKEN` | 设备绑定 JWT（换设备需重新获取） |
| `CAMERA_LICENCE` | `CAMERA_LICENCE` | 设备授权码 |

> 只跑 `unit-test` 的话，一个 Secret 都不需要。

### 2. 注册 self-hosted runner

在一台**能访问 `192.168.2.60`** 的内网机器上：

1. 仓库 `Settings → Actions → Runners → New self-hosted runner`
2. 按提示下载 runner 并运行 `config.sh`，**打标签 `aicamlab`**
3. 用 `./run.sh` 常驻运行（建议配成 systemd / 开机自启）

runner 启动后，`api-test` job 才会被调度；没 runner 时该 job 会一直 pending（属预期）。

### 3. （可选）CI 结果入库

`api-test` 默认带 `--no-record`（结果以 pytest 退出码为准，不写本地结果库）。
若要 CI 也写结果库（用于趋势对比），需：

1. 删掉 `ci.yml` 里 `run.py api --no-record --json` 的 `--no-record`
2. 给 runner 机器配好 MySQL，并在 Secrets 加 `LOCAL_MYSQL_HOST` / `LOCAL_MYSQL_USER` /
   `LOCAL_MYSQL_PASSWORD` / `LOCAL_MYSQL_DATABASE` / `AICAM_MYSQL_PASSWORD`

## 退出码与结论

`run.py` 退出码固定：`0` 通过 / `1` 失败 / `2` 用法错 / `3` 前置不满足 / `4` 需确认。
GitHub Actions 按退出码判定 job 绿/红。接口用例的失败已按 `failure_class`
（env/case/product）归类，红的原因看 pytest 输出即可。

## 已知限制

- `unit-test` 只覆盖平台层的失败归因/脱敏/断言表述（16 条），不覆盖业务接口。
- 真机用例（E2E / ReplayLab / Stability）依赖 adb + 物理设备，**不进 CI**，保留本地手动跑。
- self-hosted runner 需长期开机；设备 `.60` 离线时 `api-test` 会红（环境类失败，非产品缺陷）。
