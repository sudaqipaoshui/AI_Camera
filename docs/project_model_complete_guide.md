# X5 摄像头项目-模型完整指南

> 综合文档：包含项目列表、模型映射、配置文件说明和 XStream 框架介绍

## 📋 目录

1. [概述](#概述)
2. [项目列表-模型关系表](#项目列表-模型关系表)
3. [项目类型与配置目录映射](#项目类型与配置目录映射)
4. [模型文件列表](#模型文件列表)
5. [模型配置文件说明](#模型配置文件说明)
6. [XStream AI 框架介绍](#xstream-ai-框架介绍)

---

## 概述

### 目录结构

- **项目列表 API**: `/camera/getProjectsList` (测试: `API/tests/items/test_getProjectsList.py`)
- **模型切换 API**: `/camera/changeModel` (测试: `API/tests/items/test_changeModel.py`)
- **模型部署目录**: `/Users/sonic/DreamSports/X5/deploy`
- **配置文件**: `/Users/sonic/DreamSports/X5/deploy/configs/item.json`

### 数据流

```
API请求 (/camera/getProjectsList)
    ↓
读取 item.json 配置
    ↓
返回项目列表
    ↓
用户选择项目
    ↓
API请求 (/camera/changeModel)
    ↓
加载对应的 body_solution/{project_type}_configs/ 配置
    ↓
加载对应的 models/ 模型文件
    ↓
启动 XStream AI 推理服务
```

---

## 项目列表-模型关系表

> 基于 `/camera/getProjectsList` API 响应的实际项目数据生成

### 数据来源

- **API接口**: `GET /camera/getProjectsList`
- **数据文件**: `test_result.log` (2025-11-11)
- **项目总数**: 32 个

### 关系表

| 项目ID | 项目 | 分类 | 模型 | 模型分类 |
|--------|------|------|------|----------|
| 5 | 坐位体前屈 | **体测项目** | yolov8s_pose_640x384_nv12.bin | yolov8s_pose |
| 24 | 肺活量 | | 未知模型 | 未知模型 |
| 19 | 教学项目 | **其他项目** | yolov8s_pose_640x384_nv12.bin | yolov8s_pose |
| 27 | 高抬腿 | | yolov8s_pose_640x384_nv12.bin | yolov8s_pose |
| 51 | 提膝击掌 | | gestureDet_32x21.hbm, handLMKs.hbm | gestureDet |
| 11 | 引体向上 | **力量项目** | multitask_body_head_face_hand_kps_960x544.hbm | multitask_body_head_face_hand_kps |
| 12 | 仰卧起坐 | | yolov8s_pose_640x384_nv12.bin | yolov8s_pose |
| 30 | 深蹲 | | yolov8s_pose_640x384_nv12.bin | yolov8s_pose |
| 153 | 侧向蹲起 | | yolov8s_pose_640x384_nv12.bin | yolov8s_pose |
| 249 | 半蹲 | | yolov8s_pose_640x384_nv12.bin | yolov8s_pose |
| 250 | 足球踩球 | **球类项目** | yolov8s_pose_640x384_nv12.bin, yolov8_person_ball_pole_640x384_nv12.bin | yolov8s_pose |
| 251 | 篮球运球 | | yolov8s_pose_640x384_nv12.bin, yolov8_person_ball_pole_640x384_nv12.bin | yolov8s_pose |
| 3 | 50米跑 | **跑步项目** | person_head_640x384_nv12.bin | person_head |
| 14 | 1000米跑 | | multitask_body_head_face_hand_kps_960x544.hbm, faceLandmark106pts.hbm | multitask_body_head_face_hand_kps |
| 15 | 800米跑 | | multitask_body_head_face_hand_kps_960x544.hbm, faceLandmark106pts.hbm | multitask_body_head_face_hand_kps |
| 50 | 50x8往返跑 | | 未知模型 | 未知模型 |
| 74 | 3000米跑 | | multitask_body_head_face_hand_kps_960x544.hbm, faceLandmark106pts.hbm | multitask_body_head_face_hand_kps |
| 92 | 100米跑 | | person_head_640x384_nv12.bin | person_head |
| 154 | 200米跑 | | person_head_640x384_nv12.bin | person_head |
| 155 | 400米跑 | | person_head_640x384_nv12.bin | person_head |
| 166 | 跑圈训练 | | multitask_body_head_face_hand_kps_960x544.hbm, faceLandmark106pts.hbm | multitask_body_head_face_hand_kps |
| 244 | 1500米跑 | | multitask_body_head_face_hand_kps_960x544.hbm, faceLandmark106pts.hbm | multitask_body_head_face_hand_kps |
| 254 | 5000米跑 | | multitask_body_head_face_hand_kps_960x544.hbm, faceLandmark106pts.hbm | multitask_body_head_face_hand_kps |
| 255 | 30米跑 | | person_head_640x384_nv12.bin | person_head |
| 258 | 60米跑 | | person_head_640x384_nv12.bin | person_head |
| 9 | 立定跳远 | **跳跃项目** | person_head_640x384_nv12.bin, multitask_body_head_face_hand_kps_960x544.hbm | person_head |
| 17 | 跳绳 | | rope_640x384_nv12.bin, yolov8s_pose_640x384_nv12.bin | rope |
| 28 | 开合跳 | | yolov8s_pose_640x384_nv12.bin | yolov8s_pose |
| 31 | 蹲跳 | | yolov8s_pose_640x384_nv12.bin | yolov8s_pose |
| 126 | 弓步跳 | | yolov8s_pose_640x384_nv12.bin | yolov8s_pose |
| 127 | 纵跳 | | yolov8s_pose_640x384_nv12.bin | yolov8s_pose |
| 152 | 左右跳 | | yolov8s_pose_640x384_nv12.bin | yolov8s_pose |

### 统计信息

#### 按项目分类统计

| 项目分类 | 数量 | 占比 |
|---------|------|------|
| 跑步项目 | 12 | 37.5% |
| 跳跃项目 | 7 | 21.9% |
| 力量项目 | 5 | 15.6% |
| 体测项目 | 2 | 6.3% |
| 球类项目 | 2 | 6.3% |
| 其他项目 | 4 | 12.5% |
| **总计** | **32** | **100%** |

#### 常用模型文件

1. **yolov8s_pose_640x384_nv12.bin** - 最常用，用于15个项目
2. **person_head_640x384_nv12.bin** - 用于8个跑步和跳跃项目
3. **multitask_body_head_face_hand_kps_960x544.hbm** - 用于6个长跑项目
4. **faceLandmark106pts.hbm** - 用于6个长跑项目
5. **yolov8_person_ball_pole_640x384_nv12.bin** - 用于2个球类项目
6. **rope_640x384_nv12.bin** - 用于1个跳绳项目

### Excel使用提示

1. 打开 `project_list_model_relationship.csv` 文件
2. 选择"分类"列中相同分类的单元格
3. 使用Excel的"合并单元格"功能
4. 调整列宽以便查看完整的模型文件名

---

## 项目类型与配置目录映射

根据 `body_solution/` 目录结构，项目类型与配置目录的对应关系：

| 配置目录 | 项目类型 | 说明 |
|---------|---------|------|
| `around_pole_configs/` | 绕杆项目 | 绕杆运动相关配置 |
| `face_configs/` | 人脸识别 | 人脸检测、识别、特征提取 |
| `face_body_configs/` | 人脸+人体 | 同时检测人脸和人体 |
| `hand_lmk_configs/` | 手势识别 | 手势检测和关键点识别 |
| `item_kps_configs/` | 物品关键点 | 物品关键点检测（如球类） |
| `item_kps_object_configs/` | 物品关键点+物体 | 物品关键点+物体检测 |
| `person_head_configs/` | 人体头部 | 人体头部检测 |
| `point_17_configs/` | 17点姿态 | 17个关键点的姿态估计 |
| `point_25_configs/` | 25点姿态 | 25个关键点的姿态估计 |
| `pose_bytetrack_configs/` | 姿态跟踪 | 姿态估计+目标跟踪 |
| `race_configs/` | 竞速项目 | 竞速类运动项目 |
| `rope_body_configs/` | 跳绳 | 跳绳运动项目 |
| `top_down_pose/` | 自上而下姿态 | 俯视角度姿态估计 |
| `yolo_v11_detect/` | YOLO v11检测 | YOLO v11 目标检测 |
| `yolo_v11_pose/` | YOLO v11姿态 | YOLO v11 姿态估计 |
| `yolo_v8_pose/` | YOLO v8姿态 | YOLO v8 姿态估计 |
| `yolo_v8_pose_byte_track/` | YOLO v8姿态跟踪 | YOLO v8 姿态+跟踪 |
| `yolo_v8_pose_object_byte_track/` | YOLO v8姿态物体跟踪 | YOLO v8 姿态+物体+跟踪 |

---

## 模型文件列表

模型文件位于 `/Users/sonic/DreamSports/X5/deploy/models/`：

### 姿态估计模型
- `emopose_s_4mshe_delattn_negative_ep158_725.bin` - EmoPose 姿态模型（版本1）
- `emopose_s_4mshe_delattn_negative_ep160_723.bin` - EmoPose 姿态模型（版本2）
- `emopose_s_mshe_delattn_ep415_748.bin` - EmoPose 姿态模型（版本3）
- `emopose_s_mshe_delattn_merge2_ep415_748.bin` - EmoPose 姿态模型（合并版本）
- `rtmpose_17s_256.bin` - RTMPose 17点姿态模型
- `rtmpose_26s_256.bin` - RTMPose 26点姿态模型
- `pose_power.bin` - 姿态估计模型（Power版本）
- `point_17_nv12.bin` - 17点关键点模型
- `point_25_nv12.bin` - 25点关键点模型

### 目标检测模型
- `yolov11_bayese_640x640_nv12.bin` - YOLO v11 检测模型
- `yolo11n_detect_bayese_640x640_nv12_modified.bin` - YOLO v11n 检测模型（修改版）
- `yolov11_bk_fb_vb_modified.bin` - YOLO v11 检测模型（修改版）
- `yolov8_person_ball_pole_640x384_nv12.bin` - YOLO v8 人体+球+杆检测
- `yolov8_vb_640x384_nv12.bin` - YOLO v8 检测模型
- `yolov8_sxq_640x384_nv12.bin` - YOLO v8 检测模型（SXQ版本）

### 姿态估计模型（YOLO系列）
- `yolo11n_pose_bayese_640x640_nv12_modified.bin` - YOLO v11n 姿态模型
- `yolov8s_pose_640x384_nv12.bin` - YOLO v8s 姿态模型

### 人脸相关模型
- `faceLandmark106pts.hbm` - 人脸106点关键点模型
- `pytorch_face_landmarks_pfld.bin` - PyTorch 人脸关键点模型
- `webface_r50.bin` - WebFace 人脸识别模型（ResNet50）
- `person_head_640x384_nv12.bin` - 人体头部检测模型

### 手势识别模型
- `gestureDet_32x21.hbm` - 手势检测模型（32x21）
- `gestureDet_8x21.hbm` - 手势检测模型（8x21）
- `handLMKs.hbm` - 手部关键点模型

### 多任务模型
- `multitask_body_head_face_hand_kps_960x544.hbm` - 多任务模型（人体+头部+人脸+手+关键点）

### OCR模型
- `ppocrv5_mobile_det_numberplate_train_static.bin` - OCR 车牌检测模型
- `ppocrv5_mobile_rec_numberplate_train_static.bin` - OCR 车牌识别模型

### 其他模型
- `edgenext_base.bin` - EdgeNeXt 基础模型
- `edgenext_base_int16.bin` - EdgeNeXt 基础模型（INT16量化）
- `ktx_best.bin` - KTX 模型
- `rope_640x384_nv12.bin` - 跳绳检测模型

---

## 模型配置文件说明

### 配置文件类型

配置文件通常包括：

1. **推理配置文件** (`infer_*.json`): 定义模型的前处理、推理、后处理流程
2. **解决方案配置文件** (`*_solution.json`): 定义整个AI流水线的workflow
3. **参数配置文件** (`*_param.json`): 定义算法参数（如IOU阈值、跟踪参数等）
4. **工作流配置文件** (`*.json`): 定义多个方法的组合流程

### 主要模型配置文件

#### 1. yolov8s_pose_640x384_nv12

**模型说明**: YOLO v8 姿态估计模型（17点关键点）

**配置目录**: `body_solution/yolo_v8_pose/`

**配置文件**:

| 文件名 | 作用 | 关键配置 |
|--------|------|---------|
| `infer_yolov8_pose.json` | 模型推理配置 | - 模型路径: `yolov8s_pose_640x384_nv12.bin`<br>- 输入尺寸: 640x384<br>- 置信度阈值: 0.3<br>- NMS阈值: 0.45<br>- 关键点数: 17 |
| `yolo_pose_solution.json` | 解决方案入口 | 指向 `yolo_pose.json` |
| `yolo_pose.json` | 工作流配置 | - 推理方法: `InferMethod`<br>- 跟踪方法: `MOTMethod`<br>- 线程数: 2 |
| `iou2_euclid_method_param.json` | IOU匹配参数 | 用于目标跟踪的IOU和欧氏距离匹配 |

**使用项目**: 跳绳、仰卧起坐、深蹲、开合跳、蹲跳、左右跳、高抬腿、半蹲、坐位体前屈、教学项目

#### 2. multitask_body_head_face_hand_kps_960x544

**模型说明**: 多任务模型（同时检测人体、头部、人脸、手和关键点）

**配置目录**: `body_solution/face_body_configs/`

**配置文件**:

| 文件名 | 作用 | 关键配置 |
|--------|------|---------|
| `infer_multitask.json` | 多任务模型推理配置 | - 模型路径: `multitask_body_head_face_hand_kps_960x544.hbm`<br>- 输入尺寸: 960x544 |
| `face_body.json` | 人脸+人体工作流 | 组合多个检测和识别方法 |
| `merge_head_body.json` | 头部和人体合并配置 | 合并头部检测和人体检测结果 |

**使用项目**: 引体向上、1000米跑、800米跑、3000米跑、1500米跑、5000米跑、跑圈训练、立定跳远

#### 3. person_head_640x384_nv12

**模型说明**: 人体头部检测模型

**配置目录**: `body_solution/person_head_configs/`

**配置文件**:

| 文件名 | 作用 | 关键配置 |
|--------|------|---------|
| `infer_person_head.json` | 头部检测推理配置 | - 模型路径: `person_head_640x384_nv12.bin`<br>- 输入尺寸: 640x384 |
| `person_head_solution.json` | 头部检测解决方案 | 定义头部检测工作流 |

**使用项目**: 50米跑、100米跑、200米跑、400米跑、30米跑、60米跑、立定跳远

#### 4. rope_640x384_nv12

**模型说明**: 跳绳检测模型

**配置目录**: `body_solution/rope_body_configs/`

**配置文件**:

| 文件名 | 作用 | 关键配置 |
|--------|------|---------|
| `infer_yolov8_rope.json` | 跳绳检测推理配置 | - 模型路径: `rope_640x384_nv12.bin` |
| `yolo_pose_solution.json` | 姿态估计解决方案 | 结合姿态估计进行跳绳计数 |

**使用项目**: 跳绳

#### 5. yolov8_person_ball_pole_640x384_nv12

**模型说明**: YOLO v8 人体+球+杆检测模型

**配置目录**: `body_solution/item_kps_object_configs/`

**配置文件**:

| 文件名 | 作用 | 关键配置 |
|--------|------|---------|
| `infer_yolov8_person_basketball.json` | 篮球检测推理配置 | 检测人体和篮球 |
| `infer_yolov8_person_football.json` | 足球检测推理配置 | 检测人体和足球 |
| `dribble_solution.json` | 运球解决方案 | 篮球运球动作识别 |
| `step_football_solution.json` | 踩球解决方案 | 足球踩球动作识别 |

**使用项目**: 足球踩球、篮球运球

#### 6. gestureDet_32x21

**模型说明**: 手势检测模型（32x21输入）

**配置目录**: `body_solution/hand_lmk_configs/`

**配置文件**:

| 文件名 | 作用 | 关键配置 |
|--------|------|---------|
| `infer_static_gesture_det.json` | 静态手势检测推理配置 | - 模型路径: `gestureDet_32x21.hbm` |
| `gesture_voting.json` | 手势投票配置 | 多帧手势识别结果的投票机制 |

**使用项目**: 提膝击掌

#### 7. handLMKs

**模型说明**: 手部关键点检测模型

**配置目录**: `body_solution/hand_lmk_configs/`

**配置文件**:

| 文件名 | 作用 | 关键配置 |
|--------|------|---------|
| `infer_hand_lmk.json` | 手部关键点推理配置 | - 模型路径: `handLMKs.hbm` |
| `body_hand_lmk_solution.json` | 人体+手部关键点解决方案 | 组合人体和手部检测 |

**使用项目**: 提膝击掌

#### 8. faceLandmark106pts

**模型说明**: 人脸106点关键点检测模型

**配置目录**: `body_solution/face_configs/`

**配置文件**:

| 文件名 | 作用 | 关键配置 |
|--------|------|---------|
| `infer_lmk_106pts.json` | 106点关键点推理配置 | - 模型路径: `faceLandmark106pts.hbm` |
| `face_landmarks.json` | 人脸关键点工作流 | 定义人脸关键点检测流程 |

**使用项目**: 1000米跑、800米跑、3000米跑、1500米跑、5000米跑、跑圈训练

### 配置文件之间的关系

```
项目选择
    ↓
workflow_file_v2 (解决方案配置文件)
    ↓
yolo_pose_solution.json (指向工作流文件)
    ↓
yolo_pose.json (定义工作流步骤)
    ↓
infer_yolov8_pose.json (定义推理方法)
    ↓
yolov8s_pose_640x384_nv12.bin (模型文件)
```

### 配置文件关键参数说明

#### 推理配置文件 (`infer_*.json`)

```json
{
  "model_preprocess": {
    "image_process_pipeline": ["resize(360, 640)", "pad(384, 640)"]
  },
  "model_predict": {
    "model_file_path": "../../models/yolov8s_pose_640x384_nv12.bin",
    "run_mode": {"bpu_core": 1}
  },
  "model_post_process": {
    "conf_threshold": 0.3,
    "nms_threshold": 0.45,
    "num_keypoints": 17
  }
}
```

#### 工作流配置文件 (`*.json`)

```json
{
  "workflow": [
    {
      "method_type": "InferMethod",
      "method_config_file": "infer_yolov8_pose.json"
    },
    {
      "method_type": "MOTMethod",
      "method_config_file": "iou2_euclid_method_param.json"
    }
  ]
}
```

### 配置文件的作用总结

1. **模型加载**: 指定模型文件路径和加载方式
2. **图像预处理**: 定义输入图像的尺寸调整、填充等操作
3. **推理执行**: 定义如何在BPU上运行模型推理
4. **后处理**: 定义如何解析模型输出（检测框、关键点等）
5. **目标跟踪**: 定义如何跟踪多帧中的目标
6. **结果合并**: 定义如何合并多个检测结果
7. **参数调优**: 定义各种阈值和算法参数

---

## XStream AI 框架介绍

### 什么是 XStream？

**XStream** 是地平线（Horizon）开发的 AI 推理框架，用于构建复杂的 AI 应用流水线。它通过 JSON 配置文件定义工作流（Workflow），将多个 AI 方法（Method）组合成完整的 AI 解决方案。

### 核心概念

1. **Workflow（工作流）**: 定义多个方法的执行顺序和数据流
2. **Method（方法）**: AI 推理的基本单元（如检测、识别、跟踪等）
3. **Input/Output（输入/输出）**: 方法之间的数据传递
4. **Config（配置）**: 每个方法的参数配置

### 案例1: YOLO v8 姿态估计工作流

**项目**: 跳绳、仰卧起坐、深蹲等需要姿态估计的运动项目

#### 工作流定义 (`yolo_pose.json`)

```json
{
  "inputs": ["image"],
  "outputs": ["image", "body_box", "kps"],
  "workflow": [
    {
      "thread_count": 2,
      "method_type": "InferMethod",
      "unique_name": "yolov8_pose",
      "inputs": ["image"],
      "outputs": ["body_box_yolo", "kps"],
      "method_config_file": "infer_yolov8_pose.json"
    },
    {
      "method_type": "MOTMethod",
      "unique_name": "yolo_pose_mot",
      "inputs": ["image", "body_box_yolo"],
      "outputs": ["body_box", "body_disappeared_track_id_list"],
      "method_config_file": "iou2_euclid_method_param.json"
    }
  ]
}
```

#### 工作流执行流程

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
    ├─ IOU匹配: 计算检测框与历史轨迹的IOU
    ├─ 欧氏距离匹配: 计算关键点的欧氏距离
    ├─ 卡尔曼滤波: 预测目标位置
    └─ 输出: body_box (带track_id)
    ↓
最终输出: image, body_box, kps
```

### 案例2: 篮球运球工作流（9个方法）

**项目**: 篮球运球 - 需要检测人体、篮球，匹配关系，识别运球动作

#### 工作流步骤

1. **InferMethod: yolov8_pose** - 人体姿态估计
2. **MOTMethod: yolo_pose_mot** - 人体跟踪
3. **InferMethod: yolo_person_basketball** - 篮球检测
4. **GetBoxByClsIdMethod** - 按类别提取篮球
5. **MOTMethod: basketball_mot** - 篮球跟踪
6. **FilterByAreaMethod** - 按区域过滤
7. **MatchByDistanceMethod** - 距离匹配
8. **BehaviorMethod: dribble** - 运球识别
9. **BehaviorMethod: detect_target_miss** - 犯规检测

详细流程和数据流示例请参考完整文档。

### XStream 方法类型

1. **InferMethod** - 推理方法：运行 AI 模型推理
2. **MOTMethod** - 多目标跟踪方法：跟踪多个目标在不同帧中的位置
3. **MergeMethod** - 合并方法：合并多个检测结果
4. **FeatureMethod** - 特征提取方法：提取特征向量
5. **MatchMethod** - 匹配方法：匹配不同检测结果之间的关系
6. **ActionMethod** - 动作识别方法：识别动作和行为
7. **FilterMethod** - 过滤方法：过滤检测结果
8. **GetBoxByClsIdMethod** - 按类别ID提取方法
9. **FilterByAreaMethod** - 按区域过滤方法
10. **MatchByDistanceMethod** - 距离匹配方法
11. **BehaviorMethod** - 行为识别方法：识别复杂的行为和动作

### XStream 的优势

1. **模块化设计**: 每个方法独立配置，易于维护和替换
2. **灵活组合**: 通过 JSON 配置快速组合不同的 AI 能力
3. **性能优化**: 支持多线程、异步执行
4. **易于扩展**: 新增方法只需添加配置，无需修改代码
5. **可视化调试**: 可以查看每个方法的输入输出

---

## 📝 使用说明

### 1. 获取项目列表

```bash
pytest API/tests/items/test_getProjectsList.py -v
```

### 2. 切换模型

```bash
pytest API/tests/items/test_changeModel.py -v
```

### 3. 查看项目配置

```bash
cat /Users/sonic/DreamSports/X5/deploy/configs/item.json
```

### 4. 查看模型配置

```bash
ls -la /Users/sonic/DreamSports/X5/deploy/body_solution/*_configs/
```

---

## 📚 相关文件

### 数据文件
- `project_list_model_relationship.csv` - 项目列表关系数据（CSV格式）
- `project_model_mapping.json` - 项目模型映射数据（JSON格式）

### 测试文件
- `API/tests/items/test_getProjectsList.py` - 项目列表测试
- `API/tests/items/test_changeModel.py` - 模型切换测试
- `API/data/items/test_getProjectsList.yaml` - 测试数据

### 配置文件位置
- **项目配置**: `/Users/sonic/DreamSports/X5/deploy/configs/item.json`
- **模型配置**: `/Users/sonic/DreamSports/X5/deploy/body_solution/{project_type}_configs/`
- **模型文件**: `/Users/sonic/DreamSports/X5/deploy/models/`

---

## 🔄 更新说明

- **最后更新**: 2025-11-11
- **数据来源**: `test_result.log` (API响应)
- **配置文件路径**: `/Users/sonic/DreamSports/X5/deploy/configs/item.json`
- **模型目录**: `/Users/sonic/DreamSports/X5/deploy/models/`
- **配置目录**: `/Users/sonic/DreamSports/X5/deploy/body_solution/`

