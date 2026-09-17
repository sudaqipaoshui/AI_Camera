-- ============================================================
-- AICameraTestLab 结果表 (批次 / 用例明细 / 指标)
--
-- 与 02_schema.sql 的区别:
--   02 是"字典表"(project/device/test_result), 用来造数, 可以 DROP 重建;
--   04 是"结果表", 装的是真实跑测的历史, **一旦 DROP 趋势就没了**。
--
-- ⚠️ 因此本文件只允许 CREATE TABLE IF NOT EXISTS, 绝不允许 DROP。
--    要清理历史请用明确的删除语句(按 run_id 或时间范围), 不要重建表。
--
-- 幂等: 可重复执行, 已存在的表不会被改动。
-- 字符集: utf8mb4 / 时间用 DATETIME (不用 TIMESTAMP, 避开 2038 与时区隐式转换)
-- ============================================================

SET NAMES utf8mb4;

-- ------------------------------------------------------------
-- 批次: 一次运行的总体结果
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `test_run` (
  `id`            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `run_id`        VARCHAR(64)  NOT NULL COMMENT '批次号, 如 20260917_113000_api',
  `target`        VARCHAR(32)  NOT NULL COMMENT '目标名: api/security/e2e/replay/performance/...',
  `env`           VARCHAR(32)  NOT NULL DEFAULT 'test' COMMENT '环境名, 对应 config/<env>/',
  `device_key`    VARCHAR(64)  NULL COMMENT '设备标识(清单里的 key)',
  `device_ip`     VARCHAR(64)  NULL,
  `firmware`      VARCHAR(64)  NULL COMMENT '跑测时设备固件版本(趋势对比的关键维度)',
  `git_commit`    VARCHAR(64)  NULL,
  `git_dirty`     TINYINT      NOT NULL DEFAULT 0 COMMENT '1=工作区有未提交改动',
  `trigger_by`    VARCHAR(64)  NULL COMMENT '谁/什么触发的',
  `tag`           VARCHAR(128) NULL COMMENT '批次标签, 如固件版本或里程碑',
  `started_at`    DATETIME     NULL,
  `finished_at`   DATETIME     NULL,
  `duration_sec`  DECIMAL(10,2) NOT NULL DEFAULT 0,
  `total`         INT NOT NULL DEFAULT 0,
  `passed`        INT NOT NULL DEFAULT 0,
  `failed`        INT NOT NULL DEFAULT 0,
  `skipped`       INT NOT NULL DEFAULT 0,
  `error`         INT NOT NULL DEFAULT 0,
  `verdict`       VARCHAR(16)  NOT NULL DEFAULT 'UNKNOWN' COMMENT 'PASS/FAIL/ERROR/UNKNOWN',
  `exit_code`     INT NOT NULL DEFAULT 0,
  `log_path`      VARCHAR(255) NULL,
  `report_path`   VARCHAR(255) NULL,
  `note`          TEXT         NULL,
  `created_at`    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_run_id` (`run_id`),
  KEY `idx_target_time` (`target`, `started_at`),
  KEY `idx_tag` (`tag`),
  KEY `idx_verdict` (`verdict`),
  KEY `idx_firmware` (`firmware`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='测试批次';

-- ------------------------------------------------------------
-- 用例明细: 批次下的单条用例结果
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `case_result` (
  `id`            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `run_id`        VARCHAR(64)  NOT NULL,
  `nodeid`        VARCHAR(512) NOT NULL COMMENT 'pytest nodeid',
  `name`          VARCHAR(255) NULL,
  `module`        VARCHAR(128) NULL,
  `status`        VARCHAR(16)  NOT NULL COMMENT 'passed/failed/skipped/error',
  `duration_sec`  DECIMAL(10,3) NOT NULL DEFAULT 0,
  `message`       TEXT NULL COMMENT '失败/跳过原因(已截断)',
  `created_at`    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_run_node` (`run_id`, `nodeid`),
  KEY `idx_run` (`run_id`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用例级结果';

-- ------------------------------------------------------------
-- 指标: 算法/性能的量化结果
--   约定 name 取值:
--     accuracy  —— 准确率(%),  subject=area1..area8 或 all
--     spread    —— 极差,        subject=all
--     in_area   —— 人体在框率(%), subject=area1..area8 或 all
--     其他自定义 name 也可, 只要 report/gate 认得
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `metric` (
  `id`            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `run_id`        VARCHAR(64)  NOT NULL,
  `name`          VARCHAR(64)  NOT NULL,
  `subject`       VARCHAR(64)  NULL COMMENT '指标主体: area1..area8 / all',
  `value`         DECIMAL(14,4) NULL,
  `unit`          VARCHAR(16)  NULL,
  `extra`         JSON NULL,
  `created_at`    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_run` (`run_id`),
  KEY `idx_name_subject` (`name`, `subject`),
  KEY `idx_run_name` (`run_id`, `name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='量化指标';
