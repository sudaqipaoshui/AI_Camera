# AICameraTestLab

> X5 / X3 摄像头 AI 自动化测试框架

## 📋 项目概述

AICameraTestLab 为地平线 X5（兼容 X3）AI 摄像头提供完整的自动化测试能力，覆盖接口功能、端到端实机流程、模型性能、稳定性、安全与基准测试。此外还包含 **ReplayLab** —— 基于视频注入回放的算法准确率验证平台。

## 🗂️ 目录结构

```
AICameraTestLab/
├── API/                      # HTTP/WebSocket 接口测试
│   ├── pytest_helper/        #   测试框架插件（env fixture / 数据驱动 / 断言）
│   ├── data/                 #   用例数据（yaml）
│   └── tests/                #   62 个用例文件
│       ├── control/          #     设备控制（重启 / 升级 / 日志）
│       ├── face/             #     人脸识别
│       ├── items/            #     运动项目
│       ├── race/             #     赛事配置
│       ├── rtsp/             #     流媒体
│       └── settings/         #     系统设置
├── run.py                    # 统一测试平台入口（list/api/security/stability/.../gate/report）
├── aicamlab/                 # 平台层：runner / pytest_plugin / recorder / reporting / gating / failure / redact / inventory
├── gate.yaml                 # 发布门禁阈值（只阻塞"产品缺陷"类失败）
├── E2E/                      # 端到端实机测试（72 个文件 / 418 个用例，需显式指定）
│   ├── data/                 #   用例数据（yaml）
│   ├── pytest_helper/        #   仅 e2e_helper.py 在用，其余已删（见「已知问题」#2）
│   └── tests/                #   rope / run / longjump / situp / pullup / rush / highknee
├── ReplayLab/                # 视频注入回放测试平台（详见下节）
│   ├── run_test.py           #   一键流水线（命令行）
│   ├── items.json            #   项目知识库（itemId / golden / grid8 点位 / 多设备）
│   ├── web/app.py            #   Flask 平台
│   └── reports/              #   采集数据与报告产物（不入库）
├── Security/                 # 安全测试（6 个用例文件）
├── Performance/              # 模型性能测试
├── Stability/                # 24h SSH 稳定性监控
├── Benchmark/                # X5 芯片基准测试
├── Log/                      # 设备日志分析工具链（12 个工具脚本）+ golden/ 基准数据
├── docs/                     # 业务知识沉淀（模型说明 / 项目列表 / 问题分析等 18 份）
├── config/
│   ├── test/                 # camera.yaml / yuntiyu.yaml / yunketang.yaml
│   └── id_rsa_ai_camera      # ⚠️ 未被任何代码引用，建议移出仓库
├── .env                      # 真实凭据（不入库）
├── .env.example              # 凭据模板（入库）
├── envloader.py              # 统一凭据加载器
├── requirements.txt
└── pytest.ini
```

## 🔐 凭据管理（重要）

**仓库内不存放任何明文凭据。** YAML 配置里只写 `${VAR}` 占位符，真实值放在项目根的 `.env`（已被 `.gitignore` 排除）。

### 首次配置

```bash
cp .env.example .env
# 编辑 .env, 填入真实口令 / token
```

### 取值方式

统一走 `envloader`：

```python
from envloader import get, require, load_yaml

password = require("CAMERA_SSH_PASSWORD")   # 缺失即报错, 不提供兜底默认值
port     = get("CAMERA_SSH_PORT", "22")
config   = load_yaml("config/test/camera.yaml")   # 自动展开 ${VAR}
```

优先级：**真实环境变量 > `.env` 文件**。CI / 容器可直接注入环境变量，无需落盘。

### 规则

- 新增变量必须同步更新 `.env.example`
- 不要引入硬编码默认口令。历史遗留的兜底口令正是泄露根源，且设备改密后会导致静默连错设备
- Shell 脚本通过 `set -a; . ./.env; set +a` 载入，或依赖 `deploy_camera.sh` 内置的载入逻辑

## 🚀 快速开始

```bash
pip install -r requirements.txt
cp .env.example .env      # 填入凭据

# 默认跑接口类用例（不需要真机，175 个）
python -m pytest

# 收集但不执行，查看清单
python -m pytest --collect-only -q
```

## 🎛️ 统一测试平台（run.py）

一条命令跑任意模块、结果自动落库、出趋势报告、执行发布门禁。详见 skill `aicamlab-平台操作`。

```bash
python run.py list                  # 列出所有测试目标
python run.py api --tag baseline    # 跑 API（结果写入测试库）
python run.py smoke                 # 环境自检（解释器/配置/凭据/库/表/设备）
python run.py report                # 生成趋势报告 reports/latest.html
python run.py gate                  # 发布门禁（只阻塞"产品缺陷"类失败）
```

- **结果库**：`test_run` / `case_result` / `metric` 三张表（`SQL/04_schema_runs.sql`，幂等，绝不 DROP）。
- **失败归因**：每条失败自动归类 `env`（环境）/ `case`（用例自身）/ `product`（产品缺陷）/ `unknown`，
  门禁只对 `product` 卡流水线（口径见 `aicamlab/failure.py` 与 `gate.yaml`）。
- **退出码**：0 通过 / 1 失败 / 2 用法 / 3 前置缺失 / 4 需确认。长任务（24h 监视）需 `--yes`。

## 🧪 各模块运行方式

### 1. API 接口测试

```bash
python -m pytest API/tests/ -v
python -m pytest API/tests/control/ -v     # 设备控制
python -m pytest API/tests/face/ -v        # 人脸
python -m pytest API/tests/rtsp/ -v        # 流媒体
```

`--env` / `--config` 已由 `pytest.ini` 的 addopts 预设为 `test` / `camera.yaml`，需要切换时显式覆盖：

```bash
python -m pytest API/tests/ --env=test --config=yuntiyu.yaml
```

### 2. E2E 实机测试

⚠️ **E2E 不在 `pytest.ini` 的 `testpaths` 里**（它依赖真机 + adb + airtest，放进默认路径会让裸跑 `pytest` 直接失败）。必须显式指定：

```bash
python -m pytest E2E/tests --env=test --config=camera.yaml
```

用例命名约定：`test - rtsp服务器 - 项目名 - 日期 - 距离 - 圈数 - 学校名 - 编号`

⚠️ **用例文件名必须全局唯一**。`E2E/tests/*` 子目录没有 `__init__.py`，pytest 在默认导入模式下按文件名识别模块，**跨目录同名文件会直接导致 import mismatch、整个收集中断**（已踩过一次）。同一天、同一场地的多次测试用 `_01` / `_02` 序号区分（见 `E2E/tests/rope/`）。

### 3. 性能测试

```bash
./performance_test.sh
# 或
python -m pytest Performance/ -v
```

### 4. 稳定性测试（24h SSH 监控）

```bash
./stability_test.sh
# 或
python -m pytest Stability/test_x5_ssh_24h_monitoring.py -v

# 事后补出报告
python Stability/generate_report_from_csv.py allure-report/<批次>/ssh_monitoring_data.csv
```

### 5. 安全测试

注意脚本在 `Security/` 目录下，不在仓库根目录：

```bash
./Security/security_tests.sh
# 或
python -m pytest Security/ -v
```

### 6. 基准测试

```bash
./benchmark_test.sh
# 或
python -m pytest Benchmark/ -v
```

### 7. 部署 Deploy 包 / 固件

```bash
./deploy_camera.sh -u <包URL> -i <摄像头IP> -y
```

口令默认从 `.env` 的 `CAMERA_SSH_PASSWORD` 读取。详见 `docs/README_DEPLOY.md`。

## 🎬 ReplayLab —— 视频注入回放验证

用**视频注入**替代真人实拍：把一段视频灌进设备当直播流，采集设备的识别结果，与预置 golden 基准对比，自动算出准确率。

### 一键流水线

```bash
python ReplayLab/run_test.py --item kaihetiao --video E:/TestTools/kaihetiao_8grid_12m.mp4
python ReplayLab/run_test.py --item kaihetiao --video <video> --grid8 --duration 800
python ReplayLab/run_test.py --item kaihetiao --video <video> --dry-run       # 只看计划, 不动设备
python ReplayLab/run_test.py --item rope --analyze-only <已采集.jsonl>         # 离线重分析
```

流程：视频准备（可选 8 格拼贴）→ 部署（上传 / 改点位 / 切流 / 重启）→ 等待就位 → 采集 → golden 对齐分析 → 报告归档

### 跑后自动还原设备

流水线会改设备两处状态，且改完要 reboot，**设备不会自己恢复**：

- `camera_config/rtsp_config.json` 的注入参数（`is_rtsp_in` / `rtsp_camera_type` / `video_url`）
- 启用 `--grid8` 时，`item.json` 里 `item{ID}.init_area` 的 8 格点位

所以现在**跑前自动快照、跑完自动还原**（用 `try/finally` 兜住异常与 Ctrl-C）：

| 参数 | 作用 |
|---|---|
| （默认） | 把两个文件按**原内容 + 原属主/权限**写回并重启，同时删除已上传的视频回收空间 |
| `--no-restore` | 保持注入态，仅手工调试时用 |
| `--keep-video` | 还原时保留设备上的视频 |

快照落在 `ReplayLab/_state/<设备>_<时间戳>/`（不入库，可人工回滚）。

⚠️ 另有一个坑：**出厂态设备无法直接跑注入**——出厂是 `is_rtsp_in=false` / `rtsp_camera_type=1`，早期版本只 sed 改 `video_url`，注入不会生效（设备仍走 sensor 采集），之所以"看起来能用"是因为手工预配过注入参数的设备。现在流水线会把 3 个字段一起置位，出厂态设备（如 192.168.2.60）可直接跑。

### Web 平台

```bash
ReplayLab/start_replaylab.bat
# 本机   http://localhost:5000
# 视频源 http://<本机IP>:8000   (设备 wget 拉视频用)
```

### 指标体系

| 指标 | 含义 |
|------|------|
| **准确率%** | 设备得分 / golden 基准得分 |
| **极差** | 同一轮内 8 路得分的最大差值（一致性） |
| **inArea** | 人处于有效区域内的帧占比 |

### 两种 golden 类型

- `piecewise`：分段折线基准，按 `frame_idx % loop_frames` 对齐视频时间轴（计数类项目，如开合跳）
- `final`：per-area 最终成绩基准（计时计数类项目，如跳绳）

### 8 格拼贴（grid8）

单人视频经 ffmpeg 拼成 4K 8 格画布，一次测试覆盖 8 路；同时会把设备 `item.json` 的 `init_area` 改写成对应 8 个归一化点位。

### 已实测结果

| 项目 | itemId | 准确率 | 极差 | inArea |
|------|--------|--------|------|--------|
| 开合跳 | 28 | 101.1 ~ 103.0% | 1 ~ 6 | 93 ~ 96% |
| 跳绳 | 17 | 84.8 ~ 105.9%（**7 路**，area6 无有效数据） | 28 | 100% |

⚠️ **跳绳 area6 无有效数据**：深挖原始采集数据确认，area6 **全程未进入 `SPORTING`**
（6858/6858 次采样停在 `DEFAULT_STATUS`，`in=true` 但计时器 `tm` 恒为 0）。
**业务确认根因是人物遮挡**，且遮挡本身当前无法解决。

⚠️ **同时发现并已修复一个坐标错位缺陷**（2026-09-17）：
`polys8()` 下发点位未叠加 `origin`，比实际画面偏 (+24,+45) 像素；且 `grid8.layouts` 第 2 行
`y=1125+1080=2205 > 2160` 导致**底部 45px 被裁**。两者叠加会把"仅剩的可见人体"切出框外，
放大遮挡后果。现已修正（`origin` 归零、`polys8()` 与贴图对齐）。

详见 `ReplayLab/reports/_诊断_rope_area6失败_20260917.md`。

### 分析口径（重要）

- **极差 / 均值只统计"有效路"** —— 必须真正进入过 `SPORTING` 的路才参与计算。
  某路全程未进 `SPORTING`（遮挡、点位错位等）时，其成绩 0 **不计入极差**，
  报告会单列「无效路」并在「数据完整性」段落说明，避免把"无数据"误读成"算法全错"。
- 采集结束后残留的零星采样点（点数 < 200）视为**尾部残轮**，自动忽略。

## 📊 测试报告

- Allure 结果目录：`allure-report/allure-results`（由 `pytest.ini` addopts 指定）

```bash
allure generate allure-report/allure-results -o allure-report/http-report --clean
allure open allure-report/http-report
```

- 稳定性监控报告：`Stability/generate_report_from_csv.py` 生成硬件 / 视频性能图表
- ReplayLab 报告：`ReplayLab/reports/*.md`（Markdown，含逐轮得分、准确率、极差、inArea）

## ⚠️ 已知问题

按处理优先级排列，均已在代码中定位。

| # | 问题 | 位置 |
|---|------|------|
| 1 | ~~`config/id_rsa_ai_camera` 明文 OpenSSH 私钥~~ **已移出仓库**：全项目零引用，已移到 `E:\AI_Camera_backup_20260917\_credentials_archive\` 留档；仍需确认是否吊销（见 `docs/CREDENTIAL_ROTATION.md` 第 4 步） | `config/` |
| 2 | ~~`E2E/pytest_helper/` 与 `API/pytest_helper/` 重复~~ **已清理**：仅保留被 17 处引用的 `e2e_helper.py` + `__init__.py`，其余 7 个漂移副本（assertions/common/encryption/http_client/plugin/server/yapi_to_）已删除 | `E2E/pytest_helper/` |
| 3 | `Log/` 混入约 100 个 `tmp_*.py` 探索脚本与设备 `item.json` 转储（含 device token / license）。已在 `.gitignore` 排除 `Log/tmp_*` | `Log/` |
| 4 | 存在硬编码绝对路径（`E:\TestTools\...`、`192.168.2.124`）与写死的 venv 解释器路径 | `ReplayLab/run_test.py`、`ReplayLab/web/app.py`、`ReplayLab/start_replaylab.bat` |
| 5 | ~~无 CI~~ **已接入**：`.github/workflows/ci.yml` 分层 CI —— `unit-test`（纯函数回归，云 runner 已跑绿）+ `api-test`（内网 self-hosted runner，需配 6 个 Secrets + 打 `aicamlab` 标签的 runner，暂未启用） | 仓库根 |
| 6 | ~~报告是孤岛~~ **已解决**：`run.py report` 从结果库生成跨固件/批次趋势报告（MD+HTML），ReplayLab 网站有「历史与趋势」页 | 全局 |
| 7 | E2E 用例是「录制」而非「用例」：`rope/` 下 22 个文件差异仅在时间戳与学校名。`E2E/data/*.yaml` 已有数据驱动雏形，建议收敛为「一个用例 + 一份 yaml」 | `E2E/tests/` |
| 8 | ~~`longjump/` 用例沿用跳绳模板的 allure 标签~~ **已修复**：8 个文件 15 处错标签改为「跳远/立定跳远」 | `E2E/tests/longjump/` |
| 9 | ~~`camera.yaml` 的 `host` 段残留历史死键~~ **已归一**：`camera-prod` 死键已删，单设备死键归到 active `.60`；`cameraA`/`cameraB`/`camera175` 是双路 RTSP 起点/终点相机语义键（E2E 双机用例合法引用），保留并补注释 | `config/test/camera.yaml` |

### ✅ 近期已修复

> ⚠️ 2026-09-17 仓库重建，**历史提交号已失效**（原 `.git` 对象库损坏）。
> 下表按内容记录，提交号不再可查；重建基线为 `b2b1aa8`。

| 修复内容 | 日期 |
|---|---|
| 凭据全部移出仓库（`envloader` + `.env`，YAML 改 `${VAR}` 占位符）；清理 7 个文件的硬编码口令 | 2026-09-16 |
| E2E 两处收集错误：`pullup/` 下 4 个放错目录的跳远用例归位到 `longjump/`（同名冲突按序号惯例改名 `_02`）；`test_ry30_run_20251117_800m_4r_01.py` 的失效 datafile 引用改为 `type_channel4-5.yaml` | 2026-09-16 |
| **ReplayLab 分析口径修正**：极差/均值排除未进 `SPORTING` 的无效路；报告区分"0 分"与"无数据"；识别并忽略尾部残轮 | 2026-09-17 |
| **ReplayLab 坐标错位修复**：`polys8()` 叠加 `origin` 与 `make_grid8()` 对齐；`items.json` 的 `grid8` 布局消除第 2 行 45px 溢出；`--analyze-only` 路径的 `RESTORE_NOTE` 崩溃 | 2026-09-17 |
| 测试数据库接通（`ai_camera_test` + `DbClient` + `is_fixture` 造数/清数约定），自检 10/10 | 2026-09-17 |
| **统一测试平台建成**：`run.py` 入口 + 结果库 + 趋势报告 + 发布门禁 + 设备单一来源 + ReplayLab 历史页 | 2026-09-17 |
| **失败表述层修复**：非 JSON 响应不再伪装成业务断言；修掉一个"设备不可达却判通过"的假通过缺陷（`False == 0`） | 2026-09-17 |
| **失败归因 + 门禁口径**：`failure_class` 自动归类，门禁只阻塞"产品缺陷"类失败 | 2026-09-17 |
| 清理死代码：`log_analyze.sh`/`http_test.sh`、`E2E/pytest_helper/` 7 个漂移副本；`longjump/` allure 错标签 | 2026-09-17 |

## 🛠️ 开发指南

### 新增接口用例

1. 在 `API/tests/<模块>/` 下创建 `test_*.py`
2. 用例数据放 `API/data/<模块>/*.yaml`，用 `@pytest.mark.datafile('API/data/...yaml')` 引用
3. 测试方法签名使用框架 fixture：`(self, env, inputs, requests, expectation, case)`
4. 数据文件内可用 `{{$.path}}`（jsonpath 语法）引用 `env` 中的值，避免硬编码

### 新增 ReplayLab 项目

复制 `ReplayLab/items.json` 里的 `_template` 节点，填入实测值：

- `itemId` / `score_field`：项目 ID 与得分字段名
- `timer`：计时项目填秒数，计数项目填 `null`
- `need_start_sport`：join 前是否需要先 startSport（跳绳需要，否则报 10002）
- `golden`：基准数据，`piecewise` 或 `final`
- `grid8`：8 格拼贴的裁剪 / 缩放 / 点位参数

### 新增监控指标

1. 监控脚本中增加采集逻辑
2. 更新 CSV 字段定义
3. 同步修改 `Stability/generate_report_from_csv.py` 与图表逻辑

## 📈 监控与阈值

硬件：CPU / 内存 / 磁盘 / 温度 / 系统负载
视频：FPS / 码率 / 分辨率 / GOP / 延迟
网络：TCP 连接数 / 延迟 / 带宽

默认异常阈值（**通用经验值，尚未按 X5 实测校准**）：

| 指标 | 阈值 |
|------|------|
| 温度 | > 80°C |
| CPU | > 95% |
| 内存 / 磁盘 | > 90% |
| FPS | < 20 |

## 📄 许可证

本项目为内部项目，暂无开源许可证文件（此前 README 提到的 LICENSE 文件并不存在）。
