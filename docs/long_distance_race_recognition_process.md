# 长跑识别过程中的运动识别流程

## 📋 概述

长跑识别系统基于 XStream 框架，通过多阶段的人体检测、跟踪、人脸识别和特征匹配，实现对跑步人员的识别和圈数统计。

## 🔄 完整识别流程

### 阶段1: 多任务检测（Multitask Detection）

**配置文件**: `race_configs/infer_multitask.json`  
**模型**: `multitask_body_head_face_hand_kps_960x544.hbm`  
**输入**: 原始图像 (3840x2160)  
**输出**: 
- `body_box`: 人体检测框
- `head_box`: 头部检测框
- `face_box`: 人脸检测框
- `hand_box`: 手部检测框
- `kps`: 人体关键点（17个关键点）

**处理流程**:
```
原始图像 (3840x2160)
    ↓
图像预处理: resize(540, 960) → pad(544, 960)
    ↓
模型推理 (multitask_body_head_face_hand_kps_960x544)
    ↓
后处理: FasterRCNN Postprocess (NMS threshold: 0.3)
    ↓
输出: body_box, head_box, face_box, hand_box, kps
```

### 阶段2: 多目标跟踪（MOT - Multiple Object Tracking）

**配置文件**: `race_configs/iou_method_param.json`  
**跟踪对象**: 人脸、头部、人体分别独立跟踪

#### 2.1 人脸跟踪 (`face_mot`)
- **输入**: `face_box`
- **输出**: `face_bbox_list`, `face_disappeared_track_id_list`
- **算法**: IOU匹配
- **参数**:
  - `vanish_frame_count`: 4 (目标消失4帧后移除)
  - `time_gap`: 40
  - `max_track_target_num`: 512

#### 2.2 头部跟踪 (`head_mot`)
- **输入**: `head_box`
- **输出**: `head_bbox_list`, `head_disappeared_track_id_list`
- **算法**: IOU匹配

#### 2.3 人体跟踪 (`body_mot`)
- **输入**: `body_box`
- **输出**: `body_bbox_list`, `body_disappeared_track_id_list`
- **算法**: IOU匹配

**跟踪目的**: 
- 为每个检测到的目标分配唯一的 `track_id`
- 在连续帧中保持目标身份一致性
- 处理目标遮挡、消失和重新出现的情况

### 阶段3: 合并跟踪结果（Merge Tracking Results）

**配置文件**: `race_configs/merge_head_body.json`  
**方法**: `MergeMethod` (merge_type: "head_body")

**输入**:
- `face_bbox_list` (带track_id)
- `head_bbox_list` (带track_id)
- `body_bbox_list` (带track_id)
- `face_disappeared_track_id_list`
- `head_disappeared_track_id_list`
- `body_disappeared_track_id_list`

**输出**:
- `face_final_box`: 合并后的人脸框（带track_id）
- `head_final_box`: 合并后的头部框（带track_id）
- `body_final_box`: 合并后的人体框（带track_id）
- `disappeared_track_id`: 消失的跟踪ID列表

**合并策略**:
- `match_threshold`: 0.4 (IOU重合区域占比阈值)
- `conflict_threshold`: 0.8 (冲突阈值)
- `head_extend_ratio`: 0.05 (头部扩展比例)
- 根据空间位置关系匹配同一人的头部、人脸和人体

### 阶段4: 人脸裁剪（Face Crop）

**配置文件**: `race_configs/face_crop.json`  
**方法**: `FaceCropMethod`

**输入**: 
- `image`: 原始图像
- `face_final_box`: 人脸检测框

**输出**:
- `crop_list`: 裁剪后的人脸图像列表
- `crop_box`: 裁剪框信息

**参数**:
- `snap_size`: 40 (快照尺寸)
- `snap_score`: 0.9 (快照质量阈值)
- `max_num`: 30 (最大数量)

### 阶段5: 人脸关键点检测（Face Landmarks Detection）

**配置文件**: `race_configs/infer_lmk_106pts.json`  
**模型**: `faceLandmark106pts.hbm`

**输入**: `crop_box`, `image`  
**输出**: `lmk_106pts_infer`, `lmk_106pts_task`

**处理流程**:
```
裁剪后的人脸图像
    ↓
预处理: pyramid_roi_resizer_preprocess (norm_by_lside_ratio: 1.25)
    ↓
模型推理 (faceLandmark106pts)
    ↓
后处理: lmks4_postprocess (106个关键点)
    ↓
输出: 106个人脸关键点坐标
```

**后处理**: `PostMethod` (lmk_106pts_post)
- 将106个关键点转换为5个关键点 (`lmk_5pts`)
- 用于后续的人脸对齐

### 阶段6: 人脸对齐（Face Alignment）

**配置文件**: `race_configs/face_align.json`  
**方法**: `FaceAlignMethod`

**输入**:
- `crop_list`: 裁剪后的人脸图像
- `lmk_5pts`: 5个人脸关键点

**输出**: `align_snap_list` (对齐后的人脸图像列表)

**目的**: 
- 根据关键点位置对齐人脸
- 消除旋转、缩放等变换
- 提高后续特征提取的准确性

### 阶段7: 人脸姿态估计（Face Pose Estimation）

**配置文件**: `race_configs/infer_face_pose.json`  
**模型**: `pose_power.bin`

**输入**: `align_snap_list`  
**输出**: `face_pose` (yaw, pitch, roll角度)

**目的**: 评估人脸角度，过滤侧脸、低头等不适合识别的人脸

### 阶段8: 快照过滤（Snap Filter）

**配置文件**: `race_configs/snap_filter.json`  
**方法**: `SnapFilterMethod`

**输入**:
- `align_snap_list`: 对齐后的人脸图像
- `face_pose`: 人脸姿态角度

**输出**: `snap_list` (过滤后的高质量人脸快照)

**过滤条件**:
- `frontal_yaw_thr`: 60度 (左右偏转阈值)
- `frontal_roll_thr`: 60度 (旋转阈值)
- `frontal_pitch_thr`: 60度 (上下俯仰阈值)

**目的**: 只保留正面、清晰的人脸图像用于特征提取

### 阶段9: 人脸特征提取（Face Feature Extraction）

**配置文件**: `race_configs/infer_feature.json`  
**模型**: `edgenext_base.bin`

**输入**: `snap_list` (过滤后的高质量人脸快照)  
**输出**: `face_feature` (人脸特征向量，512维)

**处理流程**:
```
高质量人脸快照
    ↓
预处理: yuv_preprocess
    ↓
模型推理 (edgenext_base)
    ↓
后处理: faceid_postprocess
    ↓
输出: 512维特征向量
```

**特征向量用途**: 
- 用于人脸识别和身份匹配
- 与数据库中已注册的人脸特征进行相似度计算

## 🎯 运动识别关键步骤

### 1. 人员检测与跟踪

```
每帧图像
    ↓
多任务检测 → 检测人体、头部、人脸
    ↓
多目标跟踪 → 为每个人分配track_id
    ↓
合并跟踪结果 → 关联同一人的头部、人脸、人体
    ↓
持续跟踪 → 在连续帧中保持身份一致性
```

### 2. 人脸识别流程

```
检测到人脸
    ↓
人脸裁剪 → 提取人脸区域
    ↓
关键点检测 → 检测106个关键点 → 转换为5个关键点
    ↓
人脸对齐 → 根据关键点对齐人脸
    ↓
姿态估计 → 评估人脸角度
    ↓
快照过滤 → 只保留正面清晰的人脸
    ↓
特征提取 → 生成512维特征向量
    ↓
特征匹配 → 与数据库中的特征进行相似度计算
    ↓
身份识别 → 匹配成功则识别出人员身份
```

### 3. 撞线检测与圈数统计

根据日志分析，撞线检测流程如下：

```
检测到人员通过终点线
    ↓
confirmTester (确认测试者)
    ├─ 检查条件1: 基本有效性
    ├─ 检查条件2: 速度验证 (bestSpeed vs currSpeed)
    └─ 检查条件3: 速度验证 (bestSpeed vs currSpeed)
    ↓
checkCrossScoreValid (检查撞线有效性)
    ├─ 合并所有检查条件
    └─ 返回 result=true/false
    ↓
addCircle (添加圈数)
    ├─ recordId: 记录ID
    ├─ testerId: 测试者ID
    ├─ name: 姓名
    ├─ crossTime: 撞线时间
    ├─ crossCount: 圈数
    └─ score: 当前圈用时
```

### 4. 数据流示例

**输入数据**:
```json
{
  "image": "原始图像 (3840x2160)",
  "timestamp": "2025-11-27 13:31:00"
}
```

**阶段1-3输出** (检测和跟踪):
```json
{
  "body_final_box": [
    {
      "x1": 100, "y1": 200, "x2": 300, "y2": 500,
      "track_id": 4838,
      "score": 0.95
    }
  ],
  "face_final_box": [
    {
      "x1": 150, "y1": 220, "x2": 200, "y2": 270,
      "track_id": 4838,
      "score": 0.88
    }
  ],
  "kps": [
    {
      "track_id": 4838,
      "points": [
        {"x": 175, "y": 245},  // 鼻子
        {"x": 200, "y": 300},  // 左手腕
        {"x": 100, "y": 300},  // 右手腕
        // ... 共17个关键点
      ]
    }
  ]
}
```

**阶段4-9输出** (人脸识别):
```json
{
  "face_feature": [
    {
      "track_id": 4838,
      "feature": [0.123, -0.456, 0.789, ...],  // 512维特征向量
      "snap": "对齐后的人脸图像",
      "lmk_5pts": [
        {"x": 175, "y": 245},  // 左眼
        {"x": 200, "y": 250},  // 右眼
        {"x": 187, "y": 260},  // 鼻子
        {"x": 180, "y": 270},  // 左嘴角
        {"x": 195, "y": 270}   // 右嘴角
      ]
    }
  ]
}
```

**识别结果** (与数据库匹配后):
```json
{
  "track_id": 4838,
  "testerId": 1998864602,
  "name": "邓",
  "similarity": 0.759479,
  "recordId": "ceebb0223a7a43869f635fb067627253"
}
```

**撞线结果**:
```json
{
  "recordId": "ceebb0223a7a43869f635fb067627253",
  "testerId": 1998864602,
  "name": "邓",
  "crossTime": 1760922610498,
  "crossCount": 2,
  "score": "02:35",
  "lastScore": "01:18"
}
```

## 📊 配置参数说明

### 长跑项目配置 (`item.json` - item166)

```json
{
  "desc": "长跑",
  "workflow_file_v1": "/userdata/deploy/body_solution/race_configs/face_body.json",
  "min_rec_time_v3": 1,              // 最小识别时间
  "min_rec_sim_threshold": 0.7,      // 最小识别相似度阈值
  "new_feature_rec_sim_threshold_v2": 0.8,  // 新特征识别相似度阈值
  "update_feature_sim_threshold_v1": 0.8,   // 更新特征相似度阈值
  "min_track_length": 2,             // 最小跟踪长度
  "auto_join": 1,                     // 自动加入
  "need_cross_line": 0,               // 是否需要撞线检测
  "init_area": [[0.05, 0.6, 0.95, 0.6]]  // 初始区域（终点线位置）
}
```

### 跟踪参数 (`iou2_method_param.json`)

```json
{
  "match_type": "Euclidean",          // 匹配类型：欧氏距离
  "tracker_type": "IOU_2.0",          // 跟踪器类型
  "use_kalman_filter": 1,              // 使用卡尔曼滤波
  "missing_time_thres": 2,            // 丢失时间阈值
  "vanish_frame_count": 4,            // 消失帧数
  "time_gap": 40,                      // 时间间隔
  "iou_thres": -0.2,                   // IOU阈值
  "euclidean_thres": 600,              // 欧氏距离阈值
  "use_location_gain": 1,             // 使用位置增益
  "max_trajectory_number": 3          // 最大轨迹数
}
```

## 🔍 关键日志信息

根据日志分析，识别过程中的关键日志包括：

1. **识别出在跑人员**:
   ```
   识别出在跑人员:1998864602 tracker id:4838 trackerTime:4 inAreaCount:0 sim:0.759479 similerCount:2
   ```

2. **确认测试者** (confirmTester):
   ```
   confirmTester ip=192.168.111.214, testerId=499343, name=赵威凯
   ```

3. **检查撞线有效性** (checkCrossScoreValid):
   ```
   checkCrossScoreValid 1, result=true
   checkCrossScoreValid 2, result=true, bestSpeed=122.5, currSpeed=193
   checkCrossScoreValid 3, result=true, bestSpeed=143.75, currSpeed=387
   checkCrossScoreValid result=true, crossCount=2, crossTime=1760922610498
   ```

4. **添加圈数** (addCircle):
   ```
   addCircle ip=192.168.111.214, status=SPORTING, recordId=..., testerId=499343, 
   name=赵威凯, startTime=1760922455389, crossTime=1760922610498, 
   crossCount=2, score=02:35, lastScore=01:18
   ```

5. **运动人员列表** (testerListToSportList):
   ```
   testerListToSportList recordId=...
   ```

6. **添加视频到运动项** (addVideoToSportItem):
   ```
   addVideoToSportItem insert, ip=...
   ```

## 🎬 完整时序流程

```
时间轴: T0 → T1 → T2 → ... → Tn

T0: 系统启动
    ├─ 加载模型 (multitask_body_head_face_hand_kps_960x544.hbm)
    ├─ 加载模型 (faceLandmark106pts.hbm)
    ├─ 加载模型 (pose_power.bin)
    └─ 加载模型 (edgenext_base.bin)

T1: 开始检测
    ├─ 接收图像帧
    ├─ 多任务检测 (人体、头部、人脸、手部、关键点)
    └─ 多目标跟踪 (分配track_id)

T2: 持续跟踪
    ├─ 合并跟踪结果
    ├─ 人脸裁剪
    └─ 关键点检测

T3: 人脸识别
    ├─ 人脸对齐
    ├─ 姿态估计
    ├─ 快照过滤
    └─ 特征提取

T4: 身份匹配
    ├─ 特征向量与数据库匹配
    ├─ 相似度计算
    └─ 识别出人员身份 (testerId, name)

T5: 撞线检测
    ├─ 检测人员通过终点线
    ├─ 速度验证 (条件1、2、3)
    ├─ checkCrossScoreValid
    └─ addCircle (记录圈数)

T6: 圈数统计
    ├─ 更新圈数 (crossCount)
    ├─ 计算用时 (score)
    └─ 记录时间戳 (crossTime)

... (持续循环 T1-T6)
```

## 🔧 技术要点

1. **多任务检测**: 一次推理同时检测人体、头部、人脸、手部和关键点，提高效率
2. **多目标跟踪**: 使用IOU和欧氏距离匹配，结合卡尔曼滤波，实现稳定的目标跟踪
3. **人脸识别**: 106关键点 → 5关键点 → 对齐 → 姿态过滤 → 特征提取，确保识别准确性
4. **撞线检测**: 多条件验证（基本有效性 + 速度验证），避免误判
5. **实时性**: 通过多线程处理 (`thread_count`) 和异步推理，保证实时性能

## 📝 总结

长跑识别系统的运动识别过程是一个**多阶段、多任务、实时处理**的复杂流程：

1. **检测阶段**: 多任务模型同时检测人体、头部、人脸等
2. **跟踪阶段**: 多目标跟踪保持身份一致性
3. **识别阶段**: 人脸特征提取和匹配识别身份
4. **统计阶段**: 撞线检测和圈数统计

整个过程在XStream框架下高效运行，实现了对长跑人员的准确识别和圈数统计。

