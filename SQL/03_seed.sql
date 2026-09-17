-- =============================================================================
-- 03_seed.sql
-- 作用: 造基础测试数据(项目字典 + 两台主用设备)
-- 特征: 全部 is_fixture = 1, 随时可以用 99_cleanup_fixture.sql 清掉
--
-- 设备/项目取自项目现状:
--   .60 -> items.json 的 active 设备, 出厂态, rtsp 未注入
--   .30 -> camera.yaml 的 ssh_host, 曾作实验机, 已还原
--   项目 17 / 26 对应日志里反复出现的 item17(跳绳) 与 8 区域配置
-- =============================================================================

USE `ai_camera_test`;

-- -----------------------------------------------------------------------------
-- 项目字典
-- -----------------------------------------------------------------------------
INSERT INTO `project` (`item_id`, `item_name`, `score_unit`, `score_field`, `is_fixture`)
VALUES
  ( 1, '1分钟跳绳',  '个', 'count', 1),
  ( 4, '立定跳远',   '米', 'distance', 1),
  (17, '1分钟跳绳',  '个', 'count', 1),
  (26, '1分钟跳绳',  '个', 'count', 1)
ON DUPLICATE KEY UPDATE
  `item_name` = VALUES(`item_name`),
  `is_fixture` = 1;

-- -----------------------------------------------------------------------------
-- 设备台账
-- -----------------------------------------------------------------------------
INSERT INTO `device` (`device_name`, `device_serial`, `model`, `ip`, `bound_account`, `organizes_id`, `is_fixture`)
VALUES
  ('X5-A060', 'X5-DEV-192.168.2.60', 'X5', '192.168.2.60', 'huangpu', 450965, 1),
  ('X5-A030', 'X5-DEV-192.168.2.30', 'X5', '192.168.2.30', 'yangyan', NULL,   1)
ON DUPLICATE KEY UPDATE
  `ip`            = VALUES(`ip`),
  `bound_account` = VALUES(`bound_account`),
  `is_fixture`    = 1;

-- -----------------------------------------------------------------------------
-- 自检
-- -----------------------------------------------------------------------------
SELECT 'project' AS `表`, COUNT(*) AS `行数` FROM `project` WHERE `is_fixture` = 1
UNION ALL
SELECT 'device', COUNT(*) FROM `device` WHERE `is_fixture` = 1;
