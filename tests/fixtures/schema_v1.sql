-- 测试夹具：v1 版 schema.sql 原样（来自 commit 5e1d3af），用于验证从真实 v1 图库迁移。不要修改。
-- 数据库结构 v1，对应 docs/design.md 第 3 节。
-- 只在新建图库时执行；之后的结构变更写进 db.py 的 MIGRATIONS。

CREATE TABLE platform (
  id         TEXT PRIMARY KEY,      -- 'pixiv' / 'x' / 自定义
  name       TEXT NOT NULL,
  post_url   TEXT,                  -- 模板，如 'https://www.pixiv.net/artworks/{post_id}'
  user_url   TEXT,                  -- 模板，如 'https://www.pixiv.net/users/{uid}'
  url_regex  TEXT,                  -- 从链接解析，命名组 post_id / handle
  file_regex TEXT                   -- 从文件名解析，命名组 post_id / page
);

CREATE TABLE artist (
  id   INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  note TEXT
);

CREATE TABLE account (
  id        INTEGER PRIMARY KEY,
  artist_id INTEGER NOT NULL REFERENCES artist(id) ON DELETE CASCADE,
  platform  TEXT NOT NULL REFERENCES platform(id),
  uid       TEXT,                   -- 平台内不变的数字 ID
  handle    TEXT,                   -- 可能变化的用户名
  UNIQUE (platform, uid)
);

CREATE TABLE work (
  id        INTEGER PRIMARY KEY,
  artist_id INTEGER REFERENCES artist(id) ON DELETE SET NULL,
  title     TEXT,
  posted_at TEXT,
  added_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE source (
  id       INTEGER PRIMARY KEY,
  work_id  INTEGER NOT NULL REFERENCES work(id) ON DELETE CASCADE,
  platform TEXT NOT NULL REFERENCES platform(id),
  post_id  TEXT NOT NULL,
  UNIQUE (platform, post_id)
);

CREATE TABLE image (
  id       INTEGER PRIMARY KEY,
  work_id  INTEGER REFERENCES work(id) ON DELETE SET NULL,   -- NULL = 收件箱
  rel_path TEXT NOT NULL UNIQUE,     -- 相对图库根目录，'/' 分隔
  sha256   TEXT NOT NULL UNIQUE,
  page     INTEGER,
  width    INTEGER,
  height   INTEGER,
  phash    TEXT,
  missing  INTEGER NOT NULL DEFAULT 0,  -- 1 = 重新扫描时找不到文件
  added_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_image_work ON image(work_id);

CREATE TABLE tag (
  id   INTEGER PRIMARY KEY,
  ns   TEXT NOT NULL DEFAULT '',
  name TEXT NOT NULL,
  UNIQUE (ns, name)
);

CREATE TABLE tag_alias (
  alias  TEXT PRIMARY KEY,
  tag_id INTEGER NOT NULL REFERENCES tag(id) ON DELETE CASCADE
);

CREATE TABLE work_tag (
  work_id INTEGER NOT NULL REFERENCES work(id) ON DELETE CASCADE,
  tag_id  INTEGER NOT NULL REFERENCES tag(id) ON DELETE CASCADE,
  PRIMARY KEY (work_id, tag_id)
);
CREATE INDEX idx_work_tag_tag ON work_tag(tag_id);

CREATE TABLE op_log (
  id       INTEGER PRIMARY KEY,
  batch_id TEXT NOT NULL,
  at       TEXT NOT NULL DEFAULT (datetime('now')),
  kind     TEXT NOT NULL,           -- 'move' / 'tag_add' / 'tag_del' / 'merge' ...
  payload  TEXT NOT NULL            -- JSON
);
CREATE INDEX idx_op_log_batch ON op_log(batch_id);

-- 内置平台
INSERT INTO platform (id, name, post_url, user_url, url_regex, file_regex) VALUES
  ('pixiv', 'Pixiv',
   'https://www.pixiv.net/artworks/{post_id}',
   'https://www.pixiv.net/users/{uid}',
   'pixiv\.net/(?:\w+/)?artworks/(?P<post_id>\d+)',
   '(?P<post_id>\d{6,10})_p(?P<page>\d+)'),
  ('x', 'X',
   'https://x.com/i/status/{post_id}',
   'https://x.com/i/user/{uid}',
   '(?:x|twitter)\.com/(?P<handle>\w+)/status/(?P<post_id>\d+)',
   'x_(?P<post_id>\d{15,20})_p(?P<page>\d+)');
