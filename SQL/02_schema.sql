-- =============================================================================
-- 02_schema.sql
-- 作用: AICameraTestLab 测试库最小表结构
-- 目标: 让「造数 → 跑用例 → 查库校验 → 清数」这条链路先跑通;
--       表结构按最小可用设计, 后续拿到测试环境真实 schema 后再增补字段。
--
-- 设计原则:
--   1. 全部 utf8mb4, 时间统一 DATETIME (不用 TIMESTAMP, 避开 2038 与时区坑)
--   2. 每张表带 status 软删除位 + created_at/updated_at, 方便清数时按标记回滚
--   3. 造数专用字段一律加 is_fixture: 1 表示"测试造出来的", 清数时只清这一批,
--      绝不误删人工录入的数据
--   4. 不建外键约束: 造数/清数要能独立操作单表, 顺序自由; 一致性由测试代码保证
-- =============================================================================

USE `ai_camera_test`;

-- 前置: 按依赖倒序删, 保证脚本可重复执行
DROP TABLE IF EXISTS `test_result`;
DROP TABLE IF EXISTS `device`;
DROP TABLE IF EXISTS `project`;

-- -----------------------------------------------------------------------------
-- project —— 运动项目(跳绳/跳远/长跑/引体向上...)
-- 对应设备侧 item.json 的 itemId / itemName
-- -----------------------------------------------------------------------------
CREATE TABLE `project` (
  `id`            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '自增主键',
  `item_id`       INT             NOT NULL                COMMENT '设备侧项目号, 对应 item.json -> itemId',
  `item_name`     VARCHAR(64)     NOT NULL                COMMENT '项目名称, 如 1分钟跳绳',
  `score_unit`    VARCHAR(16)     NOT NULL DEFAULT '个'   COMMENT '成绩单位: 个/秒/米',
  `score_field`   VARCHAR(32)     NOT NULL DEFAULT 'count' COMMENT '成绩字段名, 对应 ReplayLab 的 score_field',
  `threshold_high` DECIMAL(10,3)  NULL                     COMMENT '高优阈值, 达到视为高分(可为空)',
  `threshold_low`  DECIMAL(10,3)  NULL                     COMMENT '低优阈值, 低于视为未达标(可为空)',
  `status`        TINYINT         NOT NULL DEFAULT 1      COMMENT '1=启用 0=停用',
  `is_fixture`    TINYINT         NOT NULL DEFAULT 0      COMMENT '1=测试造的数据, 清数依据',
  `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_item_id` (`item_id`),
  KEY `idx_is_fixture` (`is_fixture`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='运动项目';

-- -----------------------------------------------------------------------------
-- device —— 摄像头设备台账
-- 对应 config/*.yaml 的 ssh_host / licence / 绑定账号
-- -----------------------------------------------------------------------------
CREATE TABLE `device` (
  `id`            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '自增主键',
  `device_name`   VARCHAR(64)     NOT NULL                COMMENT '设备名, 如 X5-A001',
  `device_serial` VARCHAR(64)     NOT NULL                COMMENT '设备唯一序列号 deviceUnicode',
  `model`         VARCHAR(32)     NOT NULL DEFAULT 'X5'   COMMENT '型号: X3/X5',
  `ip`            VARCHAR(45)     NULL                    COMMENT '设备内网 IP, 如 192.168.2.60',
  `bound_account` VARCHAR(64)     NULL                    COMMENT '设备当前绑定的云平台账号, 如 huangpu',
  `organizes_id`  BIGINT UNSIGNED NULL                    COMMENT '所属组织 id, 如 450965',
  `licence`       VARCHAR(64)     NULL                    COMMENT '设备授权码',
  `firmware`      VARCHAR(64)     NULL                    COMMENT '固件版本',
  `status`        TINYINT         NOT NULL DEFAULT 1      COMMENT '1=在线启用 0=停用',
  `is_fixture`    TINYINT         NOT NULL DEFAULT 0      COMMENT '1=测试造的数据, 清数依据',
  `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_device_serial` (`device_serial`),
  KEY `idx_ip` (`ip`),
  KEY `idx_bound_account` (`bound_account`),
  KEY `idx_is_fixture` (`is_fixture`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='摄像头设备台账';

-- -----------------------------------------------------------------------------
-- test_result —— 成绩记录
-- 对应 ReplayLab / E2E 跑出来的成绩, 用于与设备侧结果交叉校验
-- -----------------------------------------------------------------------------
CREATE TABLE `test_result` (
  `id`          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '自增主键',
  `device_id`   BIGINT UNSIGNED NOT NULL                COMMENT '关联 device.id (逻辑外键)',
  `project_id`  BIGINT UNSIGNED NOT NULL                COMMENT '关联 project.id (逻辑外键)',
  `tester_no`   VARCHAR(64)     NOT NULL                COMMENT '被测人员编号/号码布号',
  `tester_name` VARCHAR(64)     NULL                    COMMENT '被测人员姓名',
  `round_no`    INT             NOT NULL DEFAULT 1      COMMENT '第几轮(同一人多轮取最优)',
  `score`       DECIMAL(10,3)   NULL                    COMMENT '实际成绩',
  `score_extra` VARCHAR(128)    NULL                    COMMENT '附加成绩信息(如 极差/inArea)',
  `raw_json`    JSON            NULL                    COMMENT '设备返回的原始结果, 排查用',
  `occurred_at` DATETIME        NOT NULL                COMMENT '成绩发生时间(设备时间)',
  `source`      VARCHAR(16)     NOT NULL DEFAULT 'manual' COMMENT '来源: replay/E2E/manual',
  `status`      TINYINT         NOT NULL DEFAULT 1      COMMENT '1=有效 0=作废',
  `is_fixture`  TINYINT         NOT NULL DEFAULT 0      COMMENT '1=测试造的数据, 清数依据',
  `created_at`  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_device_project_time` (`device_id`, `project_id`, `occurred_at`),
  KEY `idx_tester_no` (`tester_no`),
  KEY `idx_source` (`source`),
  KEY `idx_is_fixture` (`is_fixture`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='成绩记录';

-- -----------------------------------------------------------------------------
-- 自检: 列出本库所有表
-- -----------------------------------------------------------------------------
SELECT TABLE_NAME AS `表`, TABLE_COMMENT AS `说明`, TABLE_ROWS AS `估算行数`
  FROM information_schema.TABLES
 WHERE TABLE_SCHEMA = 'ai_camera_test'
 ORDER BY TABLE_NAME;
