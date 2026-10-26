# 协作流程

人和 AI 都按这一套走。核心只有一句：**`main` 只通过 Pull Request 合入，谁都不直接往 `main` 推。**

## 日常流程

```bash
# 1. 从最新的 main 开分支
git switch main
git pull --ff-only
git switch -c feat/inbox-api        # 分支名：类型/简短描述

# 2. 写代码，小步提交（commit 前缀见下）
pytest -q
git add -A
git commit -m "feat: 收件箱列表接口"

# 3. 推分支，到 GitHub 网页开 Pull Request
git push -u origin feat/inbox-api

# 4. CI 变绿 + 另一个人看过 → 网页上点 "Squash and merge"

# 5. 合并后本地清理
git switch main
git pull --ff-only
git branch -d feat/inbox-api
```

### 分支开了一段时间，main 已经往前走了
```bash
git fetch origin
git rebase origin/main          # 把自己的提交挪到最新 main 之后
pytest -q
git push --force-with-lease     # 只对自己的分支这样做；永远不要 force push main
```
有冲突时 git 会停下：改好冲突文件 → `git add <文件>` → `git rebase --continue`。拿不准就 `git rebase --abort` 回到原状，然后找对方商量。

## 约定

| 项目 | 约定 |
|---|---|
| 分支名 | `feat/…` 新功能、`fix/…` 修复、`docs/…`、`refactor/…`、`test/…`、`chore/…` |
| commit 前缀 | 同上：`feat:` `fix:` `docs:` `refactor:` `test:` `chore:` |
| 合并方式 | **Squash and merge**：一个 PR 在 main 上就是一个 commit，历史干净，回滚也只需回滚一个 |
| PR 大小 | 一个 PR 做一件事；超过 ~400 行改动考虑拆开 |
| 谁来合并 | 作者以外的人看过再合。AI 开的 PR 由红豆合并 |
| CI | PR 上的 CI（Windows + Linux 跑测试和 ruff）必须是绿的 |
| 本地 main | 只用 `git pull --ff-only` 更新，不在本地 main 上提交 |

## 容易撞车的地方

- **数据库迁移**（`core/db.py` 的 `MIGRATIONS`）：两个分支各加一条迁移，合并时版本号会冲突。动迁移前先在群里说一声，或者在 PR 标题里写明 `[迁移]`，后合并的那个负责把自己的迁移挪到末尾并重新跑测试。
- **CHANGELOG.md**：每个 PR 都在 `[Unreleased]` 下追加，冲突时两边都保留即可。
- **设计决策**：需要改 `docs/design.md` 或新增 ADR 的，先开 Issue 或在 PR 描述里说明理由，按 AGENTS.md 的规矩由红豆拍板。

## Git 署名

请把署名设成 GitHub 的 noreply 邮箱，避免真实邮箱进入提交历史（仓库以后可能公开）：
```bash
git config user.name  "<你的 GitHub 用户名>"
git config user.email "<数字ID>+<用户名>@users.noreply.github.com"
```
数字 ID 在 `https://api.github.com/users/<用户名>` 的 `id` 字段。
