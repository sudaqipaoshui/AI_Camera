# 日志格式说明
# Camera

(LongRace.cpp:1072): time:2025-11-18 11:58:38识别出在跑人员:1998864602tracker id:4838trackerTime:4inAreaCount:0sim:0.759479similerCount:2



# APP

## 底层
安卓日志目录
adb pull sdcard/DreamSports/log/20251113/

Powered by DsLog 1.3.6
APP_KEY: 60960c39-91e0-bcc1-480c-563db1f71dee
APP_INFO: 跳绳屏
CHANNEL: uniview
PACKAGE: com.dreamsport.aicamera.client
VERSION_CODE: 221  VERSION_NAME: 3.1.0

## 跳远

关键字：status
DEFAULT_STATUS
FINISH
FACE_RECOGNITED
SPORTING

按照顺序，左脚尖宽度、左脚尖高度，右脚尖宽度、右脚尖高度，同理：脚跟、脚踝｜对应到这个坐标。

		"pointArray" : 
		[
			0.28988713026046753,
			0.62738555669784546,
			0.27346643805503845,
			0.68394577503204346,
			0.25088796019554138,
			0.63468360900878906,
			0.24575646221637726,
			0.65475338697433472,
			0.25807201862335205,
			0.61643838882446289,
			0.25088796019554138,
			0.64380627870559692
		],


## 跳绳

--------运动状态变化
onSportDataChange

## 长跑

--------发现撞线 ｜ 原始数据从摄像头获取
2025-10-20 09:10:10.628 2000-2000 I/LongDistanceRaceFragmentViewModel: confirmTester ip=192.168.111.214, testerId=499343, name=赵威凯
检查是否撞线条件1
2025-10-20 09:10:10.629 2000-2000 I/LongDistanceRaceFragmentViewModel: checkCrossScoreValid 1, result=true
检查是否撞线条件2
2025-10-20 09:10:10.629 2000-2000 I/LongDistanceRaceFragmentViewModel: checkCrossScoreValid 2, result=true, bestSpeed=122.5, currSpeed=193
检查是否撞线条件3
2025-10-20 09:10:10.630 2000-2000 I/LongDistanceRaceFragmentViewModel: checkCrossScoreValid 3, result=true, bestSpeed=143.75, currSpeed=387
--------最终合并是否成功result=true
2025-10-20 09:10:10.631 2000-2000 I/LongDistanceRaceFragmentViewModel: checkCrossScoreValid result=true, crossCount=2, crossTime=1760922610498


--------撞线成功后的撞线信息
2025-10-20 09:10:10.632 2000-2000 I/LongDistanceRaceFragmentViewModel: addCircle ip=192.168.111.214, status=SPORTING, recordId=ceebb0223a7a43869f635fb067627253, testerId=499343, name=赵威凯, startTime=1760922455389, crossTime=1760922610498, crossCount=2, score=02:35, lastScore=01:18


--------发令按钮点击后
ongDistanceRaceFragment: btnStart onClick
--------所有的运动人员
testerListToSportList recordId=
--------补全  理论上同
esterListToSportList recordId=
addVideoToSportItem insert, ip=

# 日志分析工具使用说明

## 功能

1. **提取日志信息**：支持指定时间段过滤
2. **统计CSV**：生成详细的统计表格
3. **生成图表**：生成可视化图表（需要matplotlib）

## 使用方法

### 基本用法

```bash
python3 tools/analyze_log.py <日志文件路径>
```

### 指定时间段

# 长跑日志分析：analyze_log.py

### analyze_camera.py 

```bash
python3 tools/analyze_log.py <日志文件路径> 跑道圈长
```

```bash
python3 tools/analyze_log.py /path/to/log.log 跑道圈长\
  --start-time "2025-11-12 18:14:00" \
  --end-time "2025-11-12 18:22:00"
  跑道圈长目前：100，200，400
```

### 指定输出目录

```bash
python3 Log/analyze_log.py Log/run/134732541.log --output-dir allure-report/log_analysis
```

2. 指定时间段分析

```bash
python3 Log/analyze_log.py Log/run/app1-2.log \
  --start-time "2025-11-27 16:42:00" \
  --end-time "2025-11-27 16:59:00" \
  --output-dir allure-report/log_analysis
```


# 指定2圈
python3 Log/analyze_log.py log_file.log --circles 2 --start-time "2025-12-04 15:00:00" --end-time "2025-12-04 16:00:00"

# 或使用简写
python3 Log/analyze_log.py log_file.log --r 2 --start-time "2025-12-04 15:00:00" --end-time "2025-12-04 16:00:00"


3. 分析其他日志文件

# 分析 112450309.log
python3 Log/analyze_log.py Log/run/112450309.log --output-dir allure-report/log_analysis

# 分析其他路径的日志
python3 Log/analyze_log.py Log/20251127/134732541.log --output-dir allure-report/log_analysis


参数说明
log_file: 日志文件路径（必需）
--start-time: 开始时间，格式："2025-11-27 13:30:00"（可选）
--end-time: 结束时间，格式："2025-11-27 13:50:00"（可选）
--output-dir: 输出目录，默认：allure-report/log_analysis（可选）


## 输出文件

所有文件默认保存在 `allure-report/log_analysis/` 目录：

- `{日志文件名}_statistics.csv` - 统计表格（CSV格式）
- `circle_completion_stats.png` - 圈数完成情况统计图
- `circle_1_performance.png` - 第一圈成绩分布图
- `circle_2_performance.png` - 第二圈成绩分布图
- `circle_3_performance.png` - 第三圈成绩分布图
- `circle_4_performance.png` - 第四圈成绩分布图
- `all_circles_performance_comparison.png` - 所有圈数成绩对比组合图（2x2布局）
- `person_circle_relationship_line.png` - 每个人在不同圈数的成绩对比（折线图）
- `person_circle_relationship_bar.png` - 每个人在不同圈数的成绩对比（分组柱状图）
- `face_recognition_status.png` - 人脸识别状态统计图（以姓名为横坐标）
- `timeline.png` - 圈数完成时间线图

## CSV表格列说明

- `name`: 姓名
- `id`: 测试者ID (testerId)
- `第一圈（crossCount=1）`: 第一圈成绩
- `第二圈`: 第二圈成绩
- `第三圈`: 第三圈成绩
- `第四圈`: 第四圈成绩
- `日志数量`: 相关日志条数
- `日志信息`: 详细日志记录

## 图表功能

如果遇到matplotlib/numpy兼容性问题，可以：

1. **降级numpy**（推荐）：
   ```bash
   pip install "numpy<2"
   ```

2. **升级matplotlib**：
   ```bash
   pip install --upgrade matplotlib
   ```

3. **跳过图表生成**：脚本会自动检测，如果matplotlib不可用，会跳过图表生成，只生成CSV

## 示例

```bash
# 分析完整日志
python3 tools/analyze_log.py /Users/sonic/Downloads/20251112/180844777.log

# 分析指定时间段
python3 tools/analyze_log.py /Users/sonic/Downloads/20251112/180844777.log \
  --start-time "2025-11-12 18:14:00" \
  --end-time "2025-11-12 18:22:00" \
  --output-dir docs
```

## 统计摘要

脚本运行后会显示：
- 总人数
- 完成4圈的人数
- 完成3圈的人数
- 完成2圈的人数
- 完成1圈的人数



# Name 和 TesterId 关联机制说明

## 概述

在 `analyze_log.py` 中，`name` 和 `testerId` 的关联关系通过以下两种方式建立：

## 1. 主要关联方式：从 addCircle 日志中提取

### 日志格式
当运动员完成一圈时，会记录 `addCircle` 日志，格式如下：
```
addCircle ip=192.168.127.119, status=SPORTING, recordId=..., testerId=1998863780, name=49, startTime=..., crossTime=..., crossCount=1, score=00:34, lastScore=00:00
```

### 解析逻辑（`parse_circle_data` 函数）

**位置**：`Log/analyze_log.py` 第 56-73 行

```python
def parse_circle_data(line):
    """解析长跑圈数数据"""
    # 匹配格式: testerId=1998863780, name=49, crossTime=..., crossCount=1, score=00:34, lastScore=00:00
    pattern = r'testerId=(\d+),\s*name=([^,]+),\s*startTime=\d+,\s*crossTime=(\d+),\s*crossCount=(\d+),\s*score=([^,]+),\s*lastScore=([^\s,]+)'
    match = re.search(pattern, line)
    
    if match:
        return {
            'testerId': match.group(1),  # 提取 testerId
            'name': match.group(2),       # 提取 name
            # ... 其他字段
        }
    return None
```

### 存储方式（`parse_log_file` 函数）

**位置**：`Log/analyze_log.py` 第 111-121 行

```python
for line in lines:
    parsed = parse_circle_data(line)
    if parsed:
        tester_id = parsed['testerId']  # 使用 testerId 作为主键
        name = parsed['name']
        
        # 初始化：建立 name 和 testerId 的对应关系
        if not data[tester_id]['name']:
            data[tester_id]['name'] = name
            data[tester_id]['testerId'] = tester_id
```

**关键点**：
- 使用 `testerId` 作为数据的主键（字典的 key）
- 同时存储 `name` 和 `testerId` 的对应关系
- 这样可以通过 `testerId` 找到对应的 `name`

## 2. 补充关联方式：从所有日志行中提取（用于没有成绩数据的人）

### 使用场景
当某些人员只有人脸识别数据（`testerListToSportList`），但没有完成圈数数据（`addCircle`）时，需要从日志中补充提取 `name` 到 `testerId` 的映射。

### 提取逻辑（`generate_charts` 函数）

**位置**：`Log/analyze_log.py` 第 324-339 行

```python
# 首先从日志中提取name到testerId的映射（用于没有成绩数据的人）
name_to_testerid_from_log = {}
if log_file_path:
    try:
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                # 从addCircle日志中提取name和testerId的对应关系
                pattern = r'testerId=(\d+),\s*name=(\d+),'
                match = re.search(pattern, line)
                if match:
                    tester_id = match.group(1)
                    name = match.group(2)
                    if name not in name_to_testerid_from_log:
                        name_to_testerid_from_log[name] = tester_id
    except:
        pass
```

**关键点**：
- 扫描整个日志文件，查找所有包含 `testerId=..., name=...` 的行
- 建立 `name -> testerId` 的映射字典
- 用于处理只有人脸识别数据但没有成绩数据的人员

## 3. 关联关系的使用

### 在图表生成中的使用

**位置**：`Log/analyze_log.py` 第 341-354 行

```python
all_person_list = []
name_to_person_map = {info['name']: (info['name'], info['testerId']) for info in data.values()}

for name in all_recognized_names:
    if name in name_to_person_map:
        # 有成绩数据：从 data 中获取
        person_name, tester_id = name_to_person_map[name]
        all_person_list.append(f"{person_name}({tester_id})")
    elif name in name_to_testerid_from_log:
        # 没有成绩数据：从日志中补充提取
        tester_id = name_to_testerid_from_log[name]
        all_person_list.append(f"{name}({tester_id})")
    else:
        # 完全找不到 testerId：使用 ? 标记
        all_person_list.append(f"{name}(?)")
```

## 4. 数据流程图

```
日志文件
  │
  ├─ addCircle 日志行
  │   └─ parse_circle_data()
  │       ├─ 提取 testerId
  │       ├─ 提取 name
  │       └─ 存储到 data[testerId] = {name, testerId, circles, ...}
  │
  ├─ testerListToSportList 日志行（人脸识别）
  │   └─ parse_face_recognition_status()
  │       └─ 只提取 name（没有 testerId）
  │
  └─ 补充提取（用于没有成绩数据的人）
      └─ 扫描所有日志行
          └─ 提取 testerId=..., name=... 的对应关系
              └─ name_to_testerid_from_log[name] = testerId
```

## 5. 关键代码位置总结

| 功能 | 函数/位置 | 行号 |
|------|----------|------|
| 解析圈数数据（主要关联） | `parse_circle_data()` | 56-73 |
| 存储关联关系 | `parse_log_file()` | 111-121 |
| 补充提取关联关系 | `generate_charts()` | 324-339 |
| 使用关联关系构建人员列表 | `generate_charts()` | 341-354 |

## 6. 注意事项

1. **主键选择**：使用 `testerId` 作为主键，而不是 `name`，因为 `testerId` 是唯一标识符
2. **一对多关系**：理论上一个 `testerId` 对应一个 `name`，但在日志中可能出现 `name` 变化的情况
3. **缺失处理**：如果只有 `name` 没有 `testerId`，会尝试从日志中补充查找，如果找不到则标记为 `?`


