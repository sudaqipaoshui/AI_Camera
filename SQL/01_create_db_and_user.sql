-- =============================================================================
-- 01_create_db_and_user.sql
-- 作用: 在本机 MySQL (127.0.0.1:3306) 上创建 AICameraTestLab 专用测试库与专用账号
-- 执行: root 身份执行一次。可重复执行(全部带 IF NOT EXISTS / DROP IF EXISTS)
--
-- 命名说明:
--   库名   ai_camera_test       —— 专供本项目自动化测试, 与业务库严格隔离
--   账号   aicam_test_rw       —— 读写账号(造数/清数需要), 仅授权 ai_camera_test.*
--
-- 安全说明:
--   口令不写在本文件里。执行时用 sed 把 __AICAM_PASSWORD__ 替换成 .env 中的真实值。
--   参见 SQL/README.md 的执行方式。
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. 数据库
-- -----------------------------------------------------------------------------
CREATE DATABASE IF NOT EXISTS `ai_camera_test`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;

-- -----------------------------------------------------------------------------
-- 2. 专用读写账号
--    仅授权 ai_camera_test.*, 不给全局权限, 避免误伤其他库
-- -----------------------------------------------------------------------------
DROP USER IF EXISTS 'aicam_test_rw'@'localhost';
DROP USER IF EXISTS 'aicam_test_rw'@'192.168.2.%';

CREATE USER 'aicam_test_rw'@'localhost'
  IDENTIFIED BY '__AICAM_PASSWORD__';
CREATE USER 'aicam_test_rw'@'192.168.2.%'
  IDENTIFIED BY '__AICAM_PASSWORD__';

GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, ALTER, INDEX,
      CREATE TEMPORARY TABLES, EXECUTE, SHOW VIEW
  ON `ai_camera_test`.* TO 'aicam_test_rw'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, ALTER, INDEX,
      CREATE TEMPORARY TABLES, EXECUTE, SHOW VIEW
  ON `ai_camera_test`.* TO 'aicam_test_rw'@'192.168.2.%';

FLUSH PRIVILEGES;

-- -----------------------------------------------------------------------------
-- 3. 自检
-- -----------------------------------------------------------------------------
SELECT SCHEMA_NAME AS `库`, DEFAULT_CHARACTER_SET_NAME AS `字符集`, DEFAULT_COLLATION_NAME AS `排序规则`
  FROM information_schema.SCHEMATA
 WHERE SCHEMA_NAME = 'ai_camera_test';

SELECT User AS `账号`, Host AS `来源`, plugin AS `认证插件`
  FROM mysql.user
 WHERE User = 'aicam_test_rw';
