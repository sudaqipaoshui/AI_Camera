-- =============================================================================
-- 99_cleanup_fixture.sql
-- 作用: 清数 —— 只清"测试造出来的"数据, 绝不碰人工录入的数据
--
-- 为什么能安全地批量删:
--   所有造数脚本写入时都必须把 is_fixture 置 1。清数只按 is_fixture = 1 过滤,
--   人工在 Navicat 里录入或设备真实上报的数据 is_fixture 保持 0, 不受影响。
--
-- 用法:
--   单表清理 —— 把下面某一行取消注释单独执行
--   全量清理 —— 直接整体执行(按依赖倒序)
-- 想更保险: 把 DELETE 换成 SELECT COUNT(*), 先看要删多少行再决定。
-- =============================================================================

USE `ai_camera_test`;

-- 执行前先看一眼将影响多少行(推荐先跑这段)
SELECT 'test_result' AS `表`, COUNT(*) AS `待清理行数` FROM `test_result` WHERE `is_fixture` = 1
UNION ALL
SELECT 'device',      COUNT(*) FROM `device`      WHERE `is_fixture` = 1
UNION ALL
SELECT 'project',     COUNT(*) FROM `project`     WHERE `is_fixture` = 1;

-- 按依赖倒序清理: 先结果, 再设备, 最后项目
-- DELETE FROM `test_result` WHERE `is_fixture` = 1;
-- DELETE FROM `device`      WHERE `is_fixture` = 1;
-- DELETE FROM `project`     WHERE `is_fixture` = 1;

-- 只清成绩记录、保留项目与设备字典(日常最常用)
DELETE FROM `test_result` WHERE `is_fixture` = 1;

SELECT '清理完成' AS `结果`, ROW_COUNT() AS `test_result 已删行数`;
