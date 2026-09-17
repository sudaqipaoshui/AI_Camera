# XStream AI 框架介绍

> 基于实际案例介绍 XStream 框架的工作原理和使用方法

## 📋 什么是 XStream？

**XStream** 是地平线（Horizon）开发的 AI 推理框架，用于构建复杂的 AI 应用流水线。它通过 JSON 配置文件定义工作流（Workflow），将多个 AI 方法（Method）组合成完整的 AI 解决方案。

### 核心概念

1. **Workflow（工作流）**: 定义多个方法的执行顺序和数据流
2. **Method（方法）**: AI 推理的基本单元（如检测、识别、跟踪等）
3. **Input/Output（输入/输出）**: 方法之间的数据传递
4. **Config（配置）**: 每个方法的参数配置

## 🎯 案例1: YOLO v8 姿态估计工作流

### 场景
**项目**: 跳绳、仰卧起坐、深蹲等需要姿态估计的运动项目

### 配置文件结构

#### 1. 解决方案入口 (`yolo_pose_solution.json`)

```json
{
  "xstream_workflow_file": "./body_solution/yolo_v8_pose/yolo_pose.json"
}
```

**作用**: 指向实际的工作流配置文件

---

#### 2. 工作流定义 (`yolo_pose.json`)

```json
{
  "inputs": ["image"],                    // 输入：图像
  "outputs": ["image", "body_box", "kps"], // 输出：图像、人体框、关键点
  "workflow": [
    {
      "thread_count": 2,
      "method_type": "InferMethod",       // 方法类型：推理方法
      "unique_name": "yolov8_pose",       // 唯一名称
      "timeout_duration": 2000,           // 超时时间（毫秒）
      "inputs": ["image"],                // 输入：图像
      "outputs": ["body_box_yolo", "kps"], // 输出：检测框、关键点
      "method_config_file": "infer_yolov8_pose.json"  // 方法配置文件
    },
    {
      "thread_list": [0],
      "method_type": "MOTMethod",         // 方法类型：多目标跟踪方法
      "unique_name": "yolo_pose_mot",
      "inputs": ["image", "body_box_yolo"], // 输入：图像、检测框
      "outputs": ["body_box", "body_disappeared_track_id_list"], // 输出：跟踪框、消失的ID列表
      "method_config_file": "iou2_euclid_method_param.json"  // 跟踪参数配置
    }
  ]
}
```

### 工作流执行流程

```
输入图像
    ↓
[InferMethod: yolov8_pose]
    ├─ 加载模型: yolov8s_pose_640x384_nv12.bin
    ├─ 图像预处理: resize(360, 640) → pad(384, 640)
    ├─ BPU推理: 在BPU核心1上运行
    ├─ 后处理: 解析检测框和17个关键点
    └─ 输出: body_box_yolo, kps
    ↓
[MOTMethod: yolo_pose_mot]
    ├─ 输入: image, body_box_yolo
    ├─ IOU匹配: 计算检测框与历史轨迹的IOU
    ├─ 欧氏距离匹配: 计算关键点的欧氏距离
    ├─ 卡尔曼滤波: 预测目标位置
    └─ 输出: body_box (带track_id), body_disappeared_track_id_list
    ↓
最终输出: image, body_box, kps
```

### 数据流示例

```python
# 输入
input_data = {
    "image": numpy_array  # 原始图像 (3840x2160)
}

# 经过 InferMethod 后
intermediate_data = {
    "body_box_yolo": [
        {
            "x1": 100, "y1": 200, "x2": 300, "y2": 500,
            "score": 0.95, "class_id": 0
        }
    ],
    "kps": [
        {
            "points": [
                {"x": 150, "y": 250, "score": 0.9},  # 鼻子
                {"x": 140, "y": 240, "score": 0.85}, # 左眼
                # ... 共17个关键点
            ]
        }
    ]
}

# 经过 MOTMethod 后
output_data = {
    "body_box": [
        {
            "x1": 100, "y1": 200, "x2": 300, "y2": 500,
            "score": 0.95, "track_id": 1  # 增加了 track_id
        }
    ],
    "kps": [...],  # 关键点保持不变
    "body_disappeared_track_id_list": []  # 当前没有消失的目标
}
```

---

## 🎯 案例2: 多任务模型工作流（人脸+人体）

### 场景
**项目**: 1000米跑、800米跑等需要同时检测人脸和人体姿态的项目

### 工作流定义 (`face_body.json`)

```json
{
  "inputs": ["image"],
  "outputs": ["image", "face_box", "body_box", "face_feature"],
  "workflow": [
    {
      "method_type": "InferMethod",
      "unique_name": "multitask_infer",
      "inputs": ["image"],
      "outputs": ["body_box", "head_box", "face_box", "hand_box", "kps"],
      "method_config_file": "infer_multitask.json"
    },
    {
      "method_type": "MergeMethod",
      "unique_name": "merge_head_body",
      "inputs": ["body_box", "head_box"],
      "outputs": ["merged_box"],
      "method_config_file": "merge_head_body.json"
    },
    {
      "method_type": "FeatureMethod",
      "unique_name": "face_feature_extract",
      "inputs": ["image", "face_box"],
      "outputs": ["face_feature"],
      "method_config_file": "infer_feature.json"
    }
  ]
}
```

### 工作流执行流程

```
输入图像
    ↓
[InferMethod: multitask_infer]
    ├─ 模型: multitask_body_head_face_hand_kps_960x544.hbm
    ├─ 同时检测: 人体、头部、人脸、手、关键点
    └─ 输出: body_box, head_box, face_box, hand_box, kps
    ↓
[MergeMethod: merge_head_body]
    ├─ 合并头部和人体检测框
    └─ 输出: merged_box
    ↓
[FeatureMethod: face_feature_extract]
    ├─ 提取人脸特征向量
    └─ 输出: face_feature (用于人脸识别)
    ↓
最终输出: image, face_box, body_box, face_feature
```

---

## 🎯 案例3: 球类项目工作流（篮球运球）- 真实案例

### 场景
**项目**: 篮球运球 - 需要检测人体、篮球，匹配关系，识别运球动作

### 工作流定义 (`dribble_workflow.json`) - 实际配置

这是一个包含 **9个方法** 的复杂工作流：

```json
{
  "inputs": ["image"],
  "outputs": [
    "image",
    "body_final_box",           // 跟踪后的人体框
    "disappeared_track_id",     // 消失的跟踪ID
    "kps",                      // 关键点
    "object_basketball_box",    // 篮球检测框
    "basketball_disappeared_track_id_list",  // 篮球消失的跟踪ID
    "foul_target_miss_event",   // 犯规/目标丢失事件
    "count_dribble"             // 运球计数
  ],
  "workflow": [
    // 步骤1: 人体姿态估计
    {
      "method_type": "InferMethod",
      "unique_name": "yolov8_pose",
      "inputs": ["image"],
      "outputs": ["body_box_yolo", "kps"],
      "method_config_file": "infer_yolov8_pose.json"
    },
    // 步骤2: 人体跟踪
    {
      "method_type": "MOTMethod",
      "unique_name": "yolo_pose_mot",
      "inputs": ["image", "body_box_yolo"],
      "outputs": ["body_final_box", "disappeared_track_id"],
      "method_config_file": "iou2_euclid_method_param.json"
    },
    // 步骤3: 篮球检测
    {
      "method_type": "InferMethod",
      "unique_name": "yolo_person_basketball",
      "inputs": ["image"],
      "outputs": ["basketball_bbox"],
      "method_config_file": "infer_yolov8_person_basketball.json"
    },
    // 步骤4: 过滤篮球检测框（按类别ID）
    {
      "method_type": "GetBoxByClsIdMethod",
      "unique_name": "getbox_by_clsid_basketball",
      "inputs": ["basketball_bbox"],
      "outputs": ["object_basketball_box_filter"],
      "method_config_file": "getbox_by_clsid_config_1.json"
    },
    // 步骤5: 篮球跟踪
    {
      "method_type": "MOTMethod",
      "unique_name": "basketball_mot",
      "inputs": ["image", "object_basketball_box_filter"],
      "outputs": ["object_basketball_box", "basketball_disappeared_track_id_list"],
      "method_config_file": "iou2_method_param.json"
    },
    // 步骤6: 按区域过滤（根据脚踝关键点）
    {
      "method_type": "FilterByAreaMethod",
      "unique_name": "filter_by_area",
      "inputs": ["body_final_box", "kps"],
      "outputs": ["filter_body_final_box", "filter_kps"],
      "method_config_file": "filter_area_by_ankle.json"
    },
    // 步骤7: 匹配篮球和人体（根据距离）
    {
      "method_type": "MatchByDistanceMethod",
      "unique_name": "basketball_match_by_distance",
      "inputs": ["object_basketball_box", "filter_kps"],
      "outputs": ["match_basketball", "match_kps"],
      "method_config_file": "match_basketball_by_distance.json"
    },
    // 步骤8: 运球动作识别
    {
      "method_type": "BehaviorMethod",
      "unique_name": "dribble",
      "inputs": ["match_basketball", "match_kps"],
      "outputs": ["count_dribble"],
      "method_config_file": "dribble/dribble.json"
    },
    // 步骤9: 检测目标丢失/犯规
    {
      "method_type": "BehaviorMethod",
      "unique_name": "detect_target_miss",
      "inputs": ["match_basketball", "match_kps", "count_dribble"],
      "outputs": ["foul_target_miss_event"],
      "method_config_file": "detect_target_miss.json"
    }
  ]
}
```

### 工作流执行流程（详细）

```
输入图像 (3840x2160)
    ↓
[1. InferMethod: yolov8_pose]
    ├─ 模型: yolov8s_pose_640x384_nv12.bin
    ├─ 检测人体 + 17个关键点
    └─ 输出: body_box_yolo, kps
    ↓
[2. MOTMethod: yolo_pose_mot]
    ├─ 跟踪人体（IOU + 欧氏距离匹配）
    └─ 输出: body_final_box (带track_id), disappeared_track_id
    ↓
[3. InferMethod: yolo_person_basketball] (并行执行)
    ├─ 模型: yolov8_person_ball_pole_640x384_nv12.bin
    ├─ 检测: 人体、篮球、杆
    └─ 输出: basketball_bbox (包含多个类别)
    ↓
[4. GetBoxByClsIdMethod: getbox_by_clsid_basketball]
    ├─ 从检测结果中提取篮球类别 (class_id = 1)
    └─ 输出: object_basketball_box_filter
    ↓
[5. MOTMethod: basketball_mot]
    ├─ 跟踪篮球（IOU匹配）
    └─ 输出: object_basketball_box (带track_id)
    ↓
[6. FilterByAreaMethod: filter_by_area]
    ├─ 根据脚踝关键点位置过滤有效区域
    └─ 输出: filter_body_final_box, filter_kps
    ↓
[7. MatchByDistanceMethod: basketball_match_by_distance]
    ├─ 计算篮球与手部关键点的距离
    ├─ 匹配最近的篮球-人体对
    └─ 输出: match_basketball, match_kps
    ↓
[8. BehaviorMethod: dribble]
    ├─ 分析运球动作
    ├─ 检测球在手部附近的上下运动
    ├─ 计数运球次数
    └─ 输出: count_dribble
    ↓
[9. BehaviorMethod: detect_target_miss]
    ├─ 检测目标丢失（球离开手部）
    ├─ 检测犯规（球出界等）
    └─ 输出: foul_target_miss_event
    ↓
最终输出: 
  - body_final_box (跟踪的人体框)
  - kps (17个关键点)
  - object_basketball_box (跟踪的篮球框)
  - count_dribble (运球计数)
  - foul_target_miss_event (犯规/丢失事件)
```

### 数据流示例

```python
# 输入
input_data = {"image": numpy_array}

# 步骤1-2后: 人体检测和跟踪
body_data = {
    "body_final_box": [
        {"x1": 100, "y1": 200, "x2": 300, "y2": 500, "track_id": 1}
    ],
    "kps": [{
        "points": [
            {"x": 150, "y": 250},  # 鼻子
            {"x": 200, "y": 300},  # 左手腕
            {"x": 100, "y": 300},  # 右手腕
            # ... 共17个关键点
        ]
    }]
}

# 步骤3-5后: 篮球检测和跟踪
basketball_data = {
    "object_basketball_box": [
        {"x1": 180, "y1": 280, "x2": 220, "y2": 320, "track_id": 2}
    ]
}

# 步骤7后: 匹配结果
match_data = {
    "match_basketball": [
        {
            "basketball": {"x": 200, "y": 300, "track_id": 2},
            "person": {"track_id": 1},
            "distance": 15.5  # 像素距离
        }
    ],
    "match_kps": [{
        "hand_left": {"x": 200, "y": 300},
        "hand_right": {"x": 100, "y": 300}
    }]
}

# 步骤8后: 运球识别
dribble_data = {
    "count_dribble": {
        "total_count": 5,
        "current_state": "dribbling",  # dribbling, holding, lost
        "ball_hand_distance": 12.3
    }
}

# 步骤9后: 事件检测
event_data = {
    "foul_target_miss_event": {
        "has_foul": False,
        "target_miss": False,
        "ball_lost": False
    }
}
```

---

## 🔧 XStream 方法类型

### 1. InferMethod（推理方法）
- **作用**: 运行 AI 模型推理
- **配置**: `infer_*.json`
- **示例**: YOLO检测、姿态估计、人脸识别

### 2. MOTMethod（多目标跟踪方法）
- **作用**: 跟踪多个目标在不同帧中的位置
- **配置**: `*_method_param.json`
- **算法**: IOU匹配、卡尔曼滤波、欧氏距离匹配

### 3. MergeMethod（合并方法）
- **作用**: 合并多个检测结果
- **配置**: `merge_*.json`
- **示例**: 合并头部和人体检测框

### 4. FeatureMethod（特征提取方法）
- **作用**: 提取特征向量
- **配置**: `infer_feature.json`
- **示例**: 人脸特征提取

### 5. MatchMethod（匹配方法）
- **作用**: 匹配不同检测结果之间的关系
- **配置**: `match_*.json`
- **示例**: 匹配球和人体、匹配手部和物体

### 6. ActionMethod（动作识别方法）
- **作用**: 识别动作和行为
- **配置**: `*_solution.json`
- **示例**: 运球检测、踩球检测

### 7. FilterMethod（过滤方法）
- **作用**: 过滤检测结果
- **配置**: `*_filter.json`
- **示例**: IOU过滤、置信度过滤

### 8. GetBoxByClsIdMethod（按类别ID提取方法）
- **作用**: 从多类别检测结果中提取特定类别
- **配置**: `getbox_by_clsid_config.json`
- **示例**: 从检测结果中提取篮球类别

### 9. FilterByAreaMethod（按区域过滤方法）
- **作用**: 根据关键点位置过滤有效区域
- **配置**: `filter_area_by_*.json`
- **示例**: 根据脚踝关键点过滤有效检测区域

### 10. MatchByDistanceMethod（距离匹配方法）
- **作用**: 根据距离匹配不同检测结果
- **配置**: `match_*_by_distance.json`
- **示例**: 匹配篮球和手部关键点

### 11. BehaviorMethod（行为识别方法）
- **作用**: 识别复杂的行为和动作
- **配置**: `*_solution.json` 或 `*/dribble.json`
- **示例**: 运球识别、踩球识别、犯规检测

---

## 📊 XStream 工作流设计模式

### 模式1: 串行流水线

```
输入 → Method1 → Method2 → Method3 → 输出
```

**示例**: 检测 → 跟踪 → 过滤

### 模式2: 并行处理

```json
{
  "workflow": [
    {
      "unique_name": "detect_person",
      "inputs": ["image"],
      "outputs": ["person_box"]
    },
    {
      "unique_name": "detect_ball",
      "inputs": ["image"],  // 并行使用同一个输入
      "outputs": ["ball_box"]
    },
    {
      "unique_name": "match",
      "inputs": ["person_box", "ball_box"],  // 合并两个并行结果
      "outputs": ["matched"]
    }
  ]
}
```

### 模式3: 条件分支

通过不同的 `method_config_file` 实现条件逻辑：

```json
{
  "workflow": [
    {
      "unique_name": "detect",
      "method_config_file": "detect_config_v1.json"  // 根据条件选择不同配置
    }
  ]
}
```

---

## 🎨 实际应用案例总结

### 案例对比表

| 项目类型 | 工作流复杂度 | 方法数量 | 主要方法 |
|---------|------------|---------|---------|
| 跳绳 | 简单 | 2 | InferMethod, MOTMethod |
| 仰卧起坐 | 简单 | 2 | InferMethod, MOTMethod |
| 1000米跑 | 中等 | 3 | InferMethod, MergeMethod, FeatureMethod |
| 篮球运球 | **复杂** | **9** | InferMethod×2, MOTMethod×2, GetBoxByClsIdMethod, FilterByAreaMethod, MatchByDistanceMethod, BehaviorMethod×2 |
| 引体向上 | 中等 | 2 | InferMethod (多任务), MOTMethod |

---

## 💡 XStream 的优势

1. **模块化设计**: 每个方法独立配置，易于维护和替换
2. **灵活组合**: 通过 JSON 配置快速组合不同的 AI 能力
3. **性能优化**: 支持多线程、异步执行
4. **易于扩展**: 新增方法只需添加配置，无需修改代码
5. **可视化调试**: 可以查看每个方法的输入输出

---

## 📚 相关文件位置

- **工作流配置**: `/Users/sonic/DreamSports/X5/deploy/body_solution/*/`
- **方法配置**: `/Users/sonic/DreamSports/X5/deploy/body_solution/*/infer_*.json`
- **参数配置**: `/Users/sonic/DreamSports/X5/deploy/body_solution/*/*_param.json`
- **解决方案配置**: `/Users/sonic/DreamSports/X5/deploy/body_solution/*/*_solution.json`

---

## 🔍 调试技巧

1. **查看工作流**: 检查 `*_solution.json` 指向的 workflow 文件
2. **查看方法配置**: 检查每个方法的 `method_config_file`
3. **查看数据流**: 跟踪 `inputs` 和 `outputs` 的传递
4. **性能分析**: 检查 `timeout_duration` 和 `thread_count`
5. **日志分析**: 查看 XStream 框架的执行日志

---

## 📖 参考资料

- XStream 框架文档: 地平线官方文档
- 配置文件示例: `/Users/sonic/DreamSports/X5/deploy/body_solution/`
- 模型配置文件说明: `docs/model_config_files_guide.md`

