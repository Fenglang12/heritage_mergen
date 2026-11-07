-- 焕新作品表：image_data 从 TEXT 升级为 LONGTEXT（仅需执行一次）
USE heritage_db;

ALTER TABLE user_artworks
  MODIFY COLUMN image_data LONGTEXT NOT NULL,
  MODIFY COLUMN analysis LONGTEXT NULL;
