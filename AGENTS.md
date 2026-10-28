# AGENTS.md — 维护者 / AI 工作指引

这个仓库是 **AEMobile 三个图标库（物品 / 流体 / 源质）的维护包**：
放更新流程、建库脚本、给接手的人（或 AI）的上下文。

**先读完这一页再动手**，里面每条都是踩过的坑。玩家请看 [README.md](README.md)。

---

## 0. 快速更新流程（GTNH 换版本后）

### 0.1 前置

- `update_packs.py` 顶部的 `CONFIG` 改成自己机器上的路径（主工程、客户端 mods、汉化文件、更新仓库）。
- 只依赖 Python 3 标准库。

### 0.2 在游戏里导出图标（必须人来做）

进 GTNH 客户端 → **进世界** → 等 NEI 物品面板加载完，然后：

```
/aemobile dumpicons            全量导出（所有注册物品 × 所有 meta，几万个，几十秒）
/aemobile dumpicons 64         同上，图标 64px（体积减半）
/aemobile dumpicons list       只导出 config/aemobile-dump-items.txt 里列的（补漏，秒级）
```

产物：`<游戏目录>/dumps/aemobile/items/<modid>/<item>_<meta>.png` + `manifest.jsonl`。
导出时画面会花屏（正常），Esc 可中止。

### 0.3 一键重建 + 打包

```bash
cd D:/Develop/Game/AEMobildAll/AEMobileIcoOutput
python update_packs.py --note "GTNH 2.9.1 图标"
```

| 步骤 | 实际执行的命令 | 耗时 |
|---|---|---|
| 物品 | `scripts/build_item_icons.py <dumps> --rebuild` | ~30 秒 |
| 流体 | `scripts/build_fluid_names.py <GT 汉化> .../assets/fluids.db` | 1 秒 |
| 源质 | `scripts/build_aspects.py <客户端 mods> .../assets/essentia.db` | 3 秒 |
| 同步 | 三个库的 sha256 写回 `AEMobileApp/src/iconpack.ts` 的 `BUILTIN_SHAS` | 1 秒 |
| 打包 | `AEMobileApp/buildiconpack.py --out <更新仓库>/ae` | ~2 分钟（186MB 库要 gzip） |

只更新某几库：`--only essentia` / `--only fluids,essentia --no-pack`。

### 0.4 推送 + 出包

```bash
# 更新仓库（App 的在线更新从这里拉）
cd D:/Develop/Game/update/dsmgtnhupdate && git add ae && git commit -m "图标库 ..." && git push

# 需要随包分发时再出 APK
cd D:/Develop/Game/AEMobildAll/AEMobileApp/android
JAVA_HOME=D:/Library/DevelopmentKit/Java/Zulu/zulu17 ./gradlew assembleRelease
```

---

## 1. 先读这些（按顺序）

| 文件 | 为什么读 |
|---|---|
| `D:/Develop/Game/AEMobildAll/HANDOFF.md` | 全局交接：三个仓库、服务器地址、当前状态、待办 |
| `AEMobileApp/doc/AI协作.md` | 客户端架构、版本号规则、UI 约定、一堆历史坑 |
| `AEMobileApp/doc/程序结构.md` | 三个库的表结构、装配方式、在线更新流程 |
| `AEMobile/doc/开发进度.md` | 服务端（mod）改了什么、为什么改 |
| `AEMobile/doc/传输协议与安全.md` | TCP 帧格式；改帧/加字段前必读 |

---

## 2. 三个仓库在哪

```
D:/Develop/Game/AEMobildAll/
├── AEMobile/            mod（服务端 + 客户端共用，Java 1.7.10 / Gradle）
├── AEMobileApp/         手机端（Expo / React Native + TypeScript）
├── AEMobileIcoOutput/   本目录：图标库维护包（工具 + 文档）
└── tools/               建库脚本的**主副本**（本目录 scripts/ 是副本）
```

图标数据（`items.db` / `fluids.db` / `essentia.db`）在 `AEMobileApp/assets/`，
更新包生成到 `D:/Develop/Game/update/dsmgtnhupdate/ae`（Gitea 的 `dsmgtnhupdate` 仓库）。

---

## 3. 常见任务怎么做

### 3.1 更新图标库（GTNH 换版本）

见上面 **§0 快速更新流程**。一句话：人在游戏里 `/aemobile dumpicons` 导出 → `python update_packs.py` → push → 出 APK。
**AI 没法自己跑客户端渲染**，导出这一步必须找人做。

### 3.2 只补几个缺图标的物品

1. `AEMobileApp/mock/_items_dump.cjs` 拉一遍服务端库存 → `mock/_items.json`
2. 和 `assets/items.db` 求差集，写 `config/aemobile-dump-items.txt`
3. 让人在游戏里跑 `/aemobile dumpicons list`
4. `python update_packs.py --only items`

### 3.3 改 App 的物品页筛选 / 显示

- 类型筛选（物品/流体/源质）：`AEMobileApp/src/screens/ItemsScreen.tsx` 的 `kinds` state
- 单行解析（名字/图标/颜色）：`AEMobileApp/src/db.ts` 的 `resolveItem`
- 图标渲染（水滴/纯色块/蒙版上色）：`AEMobileApp/src/components.tsx` 的 `ItemIcon`

### 3.4 给玩家做「配置包」

```bash
python make_bundle.py --ip mc.example.com \
    --icon-source https://cdn.example.com/ae/version.json --out dist
```

产出 `dist/aemobile-config.zip`（几 KB）：玩家在 App 的「首次使用」页点「选择配置文件」导入，
服务器地址、线路列表、图标源一次到位，再点「下载图标库」。

### 3.5 给玩家做「内置图标包的 APK」

```bash
python embed_pack.py            # 把 iconpack/ 三个库写进 assets + 生成 src/bundled.ts
cd ../AEMobileApp/android && JAVA_HOME=<jdk17> ./gradlew assembleRelease
python embed_pack.py --restore  # 出完包记得还原，别提交进仓库
```

### 3.6 改在线更新逻辑

`AEMobileApp/src/iconpack.ts`：`PACK_KINDS` / `packInfo()` / `pendingKinds()` / `installOne()`。
清单格式见 `程序结构.md` 的「三个库都能在线更新」一节。

---

## 4. 必须知道的坑（都踩过）

| 坑 | 现象 | 正确做法 |
|---|---|---|
| **`item_panel` 没索引** | App 物品页加载 30–60 秒 | 建库脚本必须带 `create index idx_item on item_panel(item_name, item_meta)` |
| **ATTACH 路径带 `file://`** | 辅助库挂不上，图标全空、名字退回英文 | `FileSystem.documentDirectory` 是 URI，要 strip 掉前缀 |
| **BLOB 两种形态** | 源质图标全空白 | 主库的 icon 列 expo-sqlite 给 base64 字符串；ATTACH 进来的库给 `Uint8Array`，要走 `btoa` |
| **改了库忘了改 sha** | 装新 APK 还提示「有更新」 | 改 `src/iconpack.ts` 的 `BUILTIN_SHAS`（`update_packs.py` 会自动改） |
| **gradle 残留旧库** | APK 多出 183MB | `android/app/build/generated/res/.../assets_itempanel.db` 要手动删 |
| **源质只扫 TC4 一个 jar** | 缺十几个要素的图标 | 扫整个 mods 目录；tag 统一小写（GT 的贴图是大写文件名） |
| **流体名字只有英文** | 显示 "Dense Supercritical Steam" | 用 `fluids.db` 的 `fluid_name`（GT 汉化 Material 名） |
| **FlatList key 重复** | 771 条流体只渲染一条 | 流体/源质的行 key 必须带 nbt（`itemKey(name, meta, nbt)`） |

---

## 5. 构建 / 部署

```bash
# mod（服务端 + 客户端同一个 jar）
cd D:/Develop/Game/AEMobildAll/AEMobile && JAVA_HOME=D:/Library/DevelopmentKit/Java/Zulu/zulu8 ./gradlew build -x test

# 手机端
cd D:/Develop/Game/AEMobildAll/AEMobileApp/android && JAVA_HOME=D:/Library/DevelopmentKit/Java/Zulu/zulu17 ./gradlew assembleRelease

# 本地测试服（D:/Game/Minecraft/Server/GTNH290RC2）
#   停服：taskkill //F //PID $(netstat -ano | grep :44444 | head -1 | awk '{print $5}')
#   换 jar 到 mods/aemobile-1.7.10-3.0.0.jar
#   起服：(sleep 100000 | ./startserver.bat > console.log 2>&1)   ← 必须留 stdin，否则立刻退出
#   起服约 4 分钟；日志 console.log，编码 GBK
```

模拟器（MuMu）：`adb connect 127.0.0.1:5555` **经常掉线**，每条 adb 命令前重连一次；
或改用 `emulator-5554`。

---

## 6. 约定

### 6.1 提交规范（踩过坑）

**提交信息里只写「改了什么、为什么」，不要出现本地工作方式、助手约定、工具名。**

- ❌ `chore: gitignore 忽略 .workbuddy 本地工作区` —— 把本地用的工具名写进了公开历史
- ❌ 正文写「不要 push，交给本人」「不要删 .workbuddy-ai/」这类给助手看的规则
- ✅ `chore: gitignore 忽略本地工作区`
- ✅ `gitignore：统一忽略规则写法`

`.gitignore` 的 AI 目录段落也按「各家工具都有」写（`.opencode/` 打头，跟着 `.workbuddy/`、`.codebuddy/`、
`.claude/`、`.cursor/` …），别只留一个，否则等于公布用的是哪个。

历史里已经清理过一次（2026-10-28）：App 仓库从 163MB 降到 9.4MB，`assets/*.db` 全历史抹除。
**以后别再把图标库提交进仓库**（见 6.2）。

### 6.2 图标库不进公开仓库

图标是各模组的艺术作品，只通过**自建更新源**分发：

- 仓库里只放脚本和文档（`AEMobileApp/.gitignore` 已忽略 `/assets/*.db`）。
- 本地留一份给测试用：`D:/Develop/Game/AEMobildAll/iconpack/{items,fluids,essentia}.db`。
- App 不内置任何库：首次启动进「首次使用」页，导入配置包或填图标源地址。

### 6.3 其它

- 改帧格式 / 协议字段前，先读 `传输协议与安全.md`，并且 **App 和 mod 要一起改**。
- 三个库是**分开分发**的，别再把它们合并回一个大 `itempanel.db`。
- `scripts/` 是 `AEMobildAll/tools/` 的副本，改脚本请改主副本再同步过来。

---

## 7. 自检清单（改完图标库后）

```bash
# 1. 三个库都在、能打开、行数对
python - <<'PY'
import sqlite3
for f,t in [('items','item_panel'),('fluids','fluid_container'),('essentia','aspect')]:
    p=f'AEMobileApp/assets/{f}.db'
    c=sqlite3.connect(p)
    print(f, c.execute(f'select count(*) from {t}').fetchone()[0], c.execute('pragma integrity_check').fetchone()[0])
PY

# 2. 索引在
python -c "import sqlite3;print(sqlite3.connect('AEMobileApp/assets/items.db').execute(\"select name from sqlite_master where type='index'\").fetchall())"

# 3. iconpack.ts 里的三个 sha 和文件对得上
#    （update_packs.py 已经同步过；手改过库就要重新跑一次 --no-pack）
```
