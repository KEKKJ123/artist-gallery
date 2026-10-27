-- 新图库格式，基线 user_version=5；旧 v1～v4 不迁移（ADR 0009、0010）。
-- 初始化后保持版本化演进，不能用重新建库代替今后的升级。
CREATE TABLE platform (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  post_url TEXT,
  user_url TEXT,
  url_regex TEXT,
  file_regex TEXT,
  builtin INTEGER NOT NULL DEFAULT 0 CHECK (builtin IN (0, 1))
);
CREATE TABLE artist (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL CHECK (length(trim(name)) > 0),
  note TEXT
);
CREATE TABLE account (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  artist_id INTEGER NOT NULL REFERENCES artist(id) ON DELETE CASCADE,
  platform TEXT NOT NULL REFERENCES platform(id),
  uid TEXT,
  handle TEXT,
  CHECK (coalesce(length(trim(uid)), 0) > 0 OR coalesce(length(trim(handle)), 0) > 0),
  UNIQUE (platform, uid)
);
CREATE TABLE image (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  state TEXT NOT NULL DEFAULT 'inbox' CHECK (state IN ('inbox', 'archived')),
  artist_id INTEGER REFERENCES artist(id) ON DELETE SET NULL,
  added_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_image_state ON image(state, added_at, id);
CREATE TABLE image_file (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  image_id INTEGER NOT NULL REFERENCES image(id) ON DELETE RESTRICT,
  rel_path TEXT NOT NULL COLLATE NOCASE UNIQUE,
  sha256 TEXT NOT NULL UNIQUE CHECK (length(sha256) = 64 AND sha256 NOT GLOB '*[^0-9a-f]*'),
  orig_name TEXT NOT NULL,
  width INTEGER CHECK (width > 0),
  height INTEGER CHECK (height > 0),
  is_display INTEGER NOT NULL DEFAULT 1 CHECK (is_display IN (0, 1)),
  missing INTEGER NOT NULL DEFAULT 0 CHECK (missing IN (0, 1)),
  added_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (id, image_id)
);
CREATE INDEX idx_image_file_image ON image_file(image_id);
CREATE UNIQUE INDEX idx_image_display ON image_file(image_id) WHERE is_display = 1;
CREATE TABLE tag (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ns TEXT NOT NULL DEFAULT '',
  name TEXT NOT NULL CHECK (length(trim(name)) > 0),
  UNIQUE (ns, name)
);
CREATE TABLE image_tag (
  image_id INTEGER NOT NULL REFERENCES image(id) ON DELETE CASCADE,
  tag_id INTEGER NOT NULL REFERENCES tag(id) ON DELETE CASCADE,
  PRIMARY KEY (image_id, tag_id)
);
CREATE INDEX idx_image_tag_tag ON image_tag(tag_id);
CREATE TABLE post (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  platform TEXT NOT NULL REFERENCES platform(id),
  post_id TEXT NOT NULL CHECK (length(trim(post_id)) > 0),
  posted_at TEXT,
  UNIQUE (platform, post_id)
);
-- 来源只描述这张图片；page 为来源的可选附属属性，不是图片 ID 或归档门槛。
CREATE TABLE image_source (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  image_id INTEGER NOT NULL REFERENCES image(id) ON DELETE CASCADE,
  post_id INTEGER NOT NULL REFERENCES post(id) ON DELETE RESTRICT,
  page INTEGER CHECK (page >= 0),
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'rejected')),
  confirmed_at TEXT,
  CHECK ((status = 'confirmed' AND confirmed_at IS NOT NULL) OR
         (status != 'confirmed' AND confirmed_at IS NULL)),
  UNIQUE (image_id, post_id),
  UNIQUE (id, image_id)
);
CREATE INDEX idx_image_source_post ON image_source(post_id);
-- 同一来源可以有不同命名／规则提供的依据；冲突不覆盖人工结果。
CREATE TABLE source_evidence (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  image_id INTEGER NOT NULL REFERENCES image(id) ON DELETE CASCADE,
  file_id INTEGER,
  source_id INTEGER,
  platform TEXT NOT NULL REFERENCES platform(id),
  post_id TEXT,
  page INTEGER CHECK (page >= 0),
  input_kind TEXT NOT NULL CHECK (input_kind IN ('filename', 'link')),
  input_text TEXT NOT NULL,
  rule_key TEXT NOT NULL,
  confidence TEXT NOT NULL CHECK (confidence IN ('high', 'medium')),
  evidence_key TEXT NOT NULL UNIQUE,
  added_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (file_id, image_id) REFERENCES image_file(id, image_id),
  FOREIGN KEY (source_id, image_id) REFERENCES image_source(id, image_id)
);
CREATE INDEX idx_source_evidence_image ON source_evidence(image_id);
CREATE TABLE import_record (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_id TEXT NOT NULL,
  file_id INTEGER NOT NULL REFERENCES image_file(id) ON DELETE RESTRICT,
  orig_name TEXT NOT NULL,
  added_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_import_record_file ON import_record(file_id);
CREATE TABLE op_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  payload TEXT NOT NULL,
  at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_op_log_batch ON op_log(batch_id);
