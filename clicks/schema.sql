-- 一张表装所有事件。type：view=打开页面时屏幕上有哪些条目，click=点开原文，expand=展开简讯看摘要。
-- 各类事件的字段不一样，统一塞进 data(JSON)，分析时用 json_extract 取。
CREATE TABLE IF NOT EXISTS events (
  id    INTEGER PRIMARY KEY AUTOINCREMENT,
  ts    TEXT NOT NULL,          -- 后台收到的时间(UTC)，不信前端的钟
  type  TEXT NOT NULL,
  link  TEXT,                   -- view 事件为空
  data  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_type_ts ON events(type, ts);
CREATE INDEX IF NOT EXISTS events_link ON events(link);
