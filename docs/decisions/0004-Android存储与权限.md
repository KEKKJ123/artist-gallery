# 0004 Android 存储：默认 App 私有目录，零存储权限
- 日期：2026-10-26
- 状态：采纳；取代 0003 中"图库放共享存储、申请所有文件访问权限"的部分

## 背景
- 用户的图片可能含隐私信息，权限应尽量小。
- 曾考虑"旧设备申请所有文件权限、新设备申请部分媒体权限"，否决原因：
  - Android 14 的部分照片访问（READ_MEDIA_VISUAL_USER_SELECTED）只读、临时、不给路径，无法支撑"移动 + 重命名 + 按目录整理"。
  - Android 12 及以下没有"部分"选项，READ_EXTERNAL_STORAGE 就是整个共享存储。

## 决定
1. **默认图库位置**：App 专属外部存储 `Android/data/<包名>/files/<图库>/`。读写无需任何权限，Python 照常按路径操作，现有设计（相对路径、移动、重命名）不变。
2. **导入单张/多张图片**：系统 Photo Picker（`PickVisualMedia` / `PickMultipleVisualMedia`），选中的图复制进图库。
   - Android 13+ 为系统原生；Android 4.4–12 通过 Google Play 服务 backport。
   - 无 Play 服务（类原生 ROM）时回退到 SAF `ACTION_OPEN_DOCUMENT`。均无需权限。
3. **导入整个图库（如从 PC 拷来的文件夹）**：SAF `ACTION_OPEN_DOCUMENT_TREE` 授权一次 → 复制进私有目录 → 不保留持久授权。
4. **导出图库**：SAF 选目标位置，打包导出（目录或 zip）。
5. **高级选项（默认关闭）**：图库放共享文件夹，用于配合 Syncthing 等工具。仅在用户手动开启时申请：
   - Android ≤ 10：WRITE_EXTERNAL_STORAGE；
   - Android ≥ 11：MANAGE_EXTERNAL_STORAGE（所有文件访问），开启前明确告知用户代价。
6. Manifest 设置 `android:hasFragileUserData="true"`，卸载时（Android 10+）询问是否保留数据。

## 理由与代价
- 双向隐私：App 看不到用户其他图片；图库也不进系统相册、不被其他 App 扫描。
- 代价：
  - 卸载可能删除图库（由 hasFragileUserData + 导出功能 + PC 主库缓解）。
  - Syncthing 等难以访问私有目录，同步改为 App 内导入/导出，或 M5 的合并功能。
  - Android 11+ 文件管理器默认进不去 `Android/data`；USB MTP 可见性因 ROM 而异，待实测。

## 待验证（M4 开工前第一项）
- Briefcase/Toga 的 Android WebView 是否实现 `onShowFileChooser`（让网页 `<input type="file">` 唤起系统选择器）。若未实现，需写少量 Java/Kotlin，或经 Chaquopy 从 Python 调用 Android API 启动 Photo Picker / SAF。
- `Android/data` 下的 SQLite 与文件操作在目标 ROM 上的表现。
