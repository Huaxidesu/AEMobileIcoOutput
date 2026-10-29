# AGENTS.md — 维护者 / AI 工作指引

这个仓库是 **AEMobile 三个图标库（物品 / 流体 / 源质）的维护包**：
放更新流程、建库脚本、给接手的人（或 AI）的上下文。

**先读完这一页再动手**，里面每条都是踩过的坑。玩家请看 [README.md](README.md)。

> **如果你是 AI 助手**：直接跳到 [§0.0 执行手册](#00-给-ai-助手的执行手册)，那里把「怎么引导用户导出 → 怎么验收产物 → 怎么建库 → 怎么装到手机上验证」写成了可照抄的步骤。

---

## 0.0 给 AI 助手的执行手册

用户说「帮我更新图标 / 补图标 / 图标不对」时，**照这五步走**，不要跳步、不要让用户猜命令。

### 第一步：先摸清现状（别急着让用户进游戏）

```bash
# 1) 装的是哪版 mod？和源码最新产物比过没有
ls -l "<实例>/.minecraft/mods/aemobile-"*.jar
ls -l AEMobile/build/libs/aemobile-*.dirty.jar      # 比 mtime，旧了就重编（见第 5 节）

# 2) 之前导出过什么？哪些已经过期？
ls -l "<实例>/.minecraft/dumps/aemobile/"

# 3) 本机路径对不对（会自动找 GT 汉化文件）
python update_packs.py --only essentia --no-pack --no-sha --save-config
```

判断规则：

- **jar 比 dump 产物新** → 导出是用旧 mod 跑的，必须让用户重跑（新命令/新产物不会凭空出现）
- 缺 `atlas.raw` → 流体图标只能走 jar 贴图，水/岩浆/熔融金属会是灰的（见第 4 节）
- 缺 `aspect-images.tsv` → 附属模组的要素会显示问号

### 第二步：把要跑的命令原样给用户（连前提一起说）

前提必须讲清楚，否则用户会白跑：

> 进 GTNH 客户端 → **进世界**（不是主菜单）→ 等 NEI 面板加载完 → 再敲命令

| 用户的需求 | 给用户的命令 | 备注 |
|---|---|---|
| 全套（换 GTNH 版本后） | `/aemobile dump all` | 只有 items 会花屏，可按 Esc 中止 |
| 只补物品图标 | `/aemobile dump items 64` | 64px 体积减半 |
| 只补流体 | `/aemobile dump fluids` | 秒级，顺便写 `atlas.raw`（图集快照） |
| 只补源质 | `/aemobile dump aspects` | 秒级，顺便写 `aspect-images.tsv` |
| 只补清单里的少数物品 | `/aemobile dumpicons list` | 清单在 `config/aemobile-dump-items.txt` |

老入口等价关系：`dumpicons` = `dump items`，`dumpcolors` = `dump fluids aspects`。

### 第三步：验收产物（跑脚本，别靠肉眼）

```bash
D="<实例>/.minecraft/dumps/aemobile"
wc -l "$D/items/manifest.jsonl"   # 几万行；明显偏少 = 导到一半被 Esc 了
wc -l "$D/fluid-colors.tsv"       # ~1550
head -1 "$D/fluid-atlas.tsv"      # # atlas 8192 8192
ls -l  "$D/atlas.raw"             # 大小必须 = W*H*4（8192 → 268435456）
wc -l "$D/aspect-colors.tsv"      # ~70
wc -l "$D/aspect-images.tsv"      # ~70；没有就是 mod 太旧
```

数字对不上就别建库，先让用户重导。

### 第四步：建库 + 打包

```bash
python update_packs.py --note "GTNH 2.9.1 图标"
```

盯住输出里这几行，异常值回第 4 节查：

- `有图 N 条（图集 X 条，jar 兜底 Y 条…）` —— 图集那条应该占大头
- `补上 N 个` —— 源质贴图按路径补到几个
- `fluid_icon N 条` / `个源质（烘了颜色 N 个）`

### 第五步：交付（先问用户要哪种）

**A. 在线更新**（推荐，库 186MB 不进 APK）：

```bash
python update_packs.py --note "..."          # 已包含出包，产物在 CONFIG['out']
```

然后让用户在 App：设置 → 图标库 → 填 `.../ae/version.json` → 检查更新。

**B. 内置进 APK**（用户想要开箱即用）：

```bash
cd AEMobileIcoOutput && python embed_pack.py
cd ../AEMobileApp/android && JAVA_HOME=<zulu17> ./gradlew assembleRelease
adb install -r app/build/outputs/apk/release/app-release.apk
```

### 第六步：验收（装完必须做）

```bash
adb shell su -c "ls -l /data/data/dev.youtiao.aemonitor/files/SQLite/"   # 大小要和本地一致
adb logcat -d | grep AEMobile                                            # 不能有 attach-fail / fluid-icon-fail
```

App 里切到「流体」「源质」筛选，确认图标不是色块/问号。

---

## 0.0.1 故障速查：用户这么说 → 你先查这个

| 用户的话 | 真正的原因（按概率排） | 怎么确认 |
|---|---|---|
| 「图标没变 / 还是色块」 | ① 辅助库没挂上（`getInfoAsync` 传了裸路径）② 装的是旧 APK | `adb logcat \| grep AEMobile`，看有没有 `attach-fail`；比对设备上 db 大小 |
| 「流体是灰白的」 | 没跑 `/aemobile dump fluids`（缺 `atlas.raw`）→ 退化成「jar 灰度图 × 颜色」，而 `Fluid.getColor()` 对 GT 基本返回 FFFFFF | 看 dumps 目录有没有 `atlas.raw` |
| 「要素显示问号」 | 缺 `aspect-images.tsv`，或 mod 太旧（不导这张表）；附属要素文件名和 tag 对不上 | 看 `essentia.db` 里有没有该 tag |
| 「导出命令没反应 / 只有用法提示」 | 客户端跑的是旧 jar（jar 在游戏启动时才加载） | 比 jar 和 dumps 的 mtime |
| 「游戏崩溃了」 | 先看 `crash-reports/` 栈顶：Opis 的 `HeadlessException` = 环境没桌面，与本模组无关；AllMusic 的 NPE 同理 | 读 crash-report，别直接改自己的代码 |
| 「列表拉不到数据」 | 监控器所在区块没加载（没人在那个维度） | 服务端日志 `监控器未就绪` |

---

## 0. 快速更新流程（GTNH 换版本后）

### 0.1 前置

- 只依赖 Python 3 标准库（例外：`build_fluid_icons.py` 要 `pip install pillow`，它得解码/缩放 PNG）。
- 路径按三档来，后者覆盖前者：`update_packs.py` 顶部的 `CONFIG`（默认值）→ 同目录 `pack_config.json`
  → 命令行参数。换机器只改 `pack_config.json`，别动代码：

  ```bash
  # 第一次在这台机器上跑，把当前路径记下来（含自动找到的汉化文件）
  python update_packs.py --only essentia --no-pack --no-sha --save-config
  ```

- **GTNH 汉化文件（`GregTech_zh_CN.lang`）是必需的**，流体的中文名全靠它。
  不用手动下载：GTNH 客户端实例根目录（`<实例>/.minecraft/`）就自带一份，脚本按
  `--lang` → `pack_config.json` 的 `lang` → 实例根目录 → `C:/Downloads/**` 的顺序自己找。
  找不到会直接停下并打印找过的位置。想手动指定就 `--lang "D:/.../GregTech_zh_CN.lang"`。
  `pack_config.json` 已进 `.gitignore`（本机路径不该入库）。

### 0.2 在游戏里导出图标（必须人来做）

进 GTNH 客户端 → **进世界** → 等 NEI 物品面板加载完，然后：

```
/aemobile dump all [尺寸]      三样一起：物品图标 + 流体颜色 + 源质颜色
/aemobile dump items [尺寸]    物品图标（所有注册物品 × 所有 meta，几万个，几十秒）
/aemobile dump fluids          流体颜色表（不需要 GL，秒级）
/aemobile dump aspects         源质颜色表（不需要 GL，秒级）
/aemobile dumpicons [list] [尺寸]  老入口 = dump items（list：只导 config/aemobile-dump-items.txt）
/aemobile dumpcolors           老入口 = dump fluids aspects
```

产物：`<游戏目录>/dumps/aemobile/` 下
`items/<modid>/<item>_<meta>.png` + `manifest.jsonl`、`fluid-colors.tsv`、`aspect-colors.tsv`。
只有 items 会花屏（要开 Framebuffer 渲染），颜色表是纯文件 IO。

### 0.3 一键重建 + 打包

```bash
cd D:/Develop/Game/AEMobildAll/AEMobileIcoOutput
python update_packs.py --note "GTNH 2.9.1 图标"
```

| 步骤 | 实际执行的命令 | 耗时 |
|---|---|---|
| 物品 | `scripts/build_item_icons.py <dumps> --rebuild` | ~30 秒 |
| 流体 | `scripts/build_fluid_names.py <GT 汉化> .../assets/fluids.db`<br>`scripts/build_fluid_icons.py <mods> --db .../assets/fluids.db --colors <dumps>/fluid-colors.tsv` | 1 秒 + 2 秒 |
| 源质 | `scripts/build_aspects.py <客户端 mods> [--colors <dumps>/aspect-colors.tsv] .../assets/essentia.db` | 3 秒 |
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

见上面 **§0.0 给 AI 助手的执行手册**（完整五步 + 验收 + 交付）和 §0 快速流程。
一句话：人在游戏里 `/aemobile dump all` → `python update_packs.py` → push 或出 APK。
**AI 没法自己跑客户端渲染**，导出这一步必须找人做；但「让用户跑什么命令、跑完怎么验收、
产物对不对、装完怎么确认」全部由 AI 负责，不要让用户自己判断。

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

装完要验（不然「图标没变」你都不知道是包没生效还是代码问题）：

```bash
adb install -r app/build/outputs/apk/release/app-release.apk
adb shell su -c "ls -l /data/data/dev.youtiao.aemonitor/files/SQLite/"   # 三个库大小要和本地一致
adb logcat -d | grep AEMobile                                            # 不能有 attach-fail
```

注意 `adb install -r` 保留旧数据，SecureStore 里的「当前生效库名」会沿用；
换库后如果界面没变，先 `adb shell pm clear` 或卸载重装再判断。

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
| **流体贴图大半是灰的** | 烘出来的流体图标一片灰白 | GT 一千多条流体共用 `fluid.autogenerated.png`（灰度）。**别指望 `Fluid.getColor()`**：实测水/岩浆/熔融金属全返回 `FFFFFF`，颜色是贴图阶段就定死的。`/aemobile dump fluids` 会顺手把 blocks 图集读成 `atlas.raw` + `fluid-atlas.tsv`，`build_fluid_icons.py --atlas-dir` 按坐标裁游戏里真正画出来的那张图（首选）；没有图集才退回「jar 贴图 × 颜色表」 |
| **源质烘了色还留着 tint** | 源质图标比游戏里暗一截（颜色乘了两遍） | `aspect` 表和 `fluid_icon` 表都有 `tint` 列：0 = 颜色已烘进 PNG，App 不能再 tint；1 = 灰度蒙版，用服务端 Color 现染。`src/db.ts` 的 `lookupAspect` / `lookupFluidIcon` 都按这列走 |
| **图标/名字在真机上不生效** | 换库没反应，图标全是占位 | 先 `adb logcat \| grep AEMobile`。2026-10-29 抓到过：`attachAux` 拿裸路径调 `FileSystem.getInfoAsync`（它只认 `file://`），永远 `exists:false` → 辅助库从没 ATTACH 过。判断「库换了没生效」时先看这个，别先怀疑库内容 |
| **`build_fluid_icons.py` 要 Pillow** | `ModuleNotFoundError: PIL` | 这是三个建库脚本里唯一非标准库依赖（要解码/缩放 PNG）：`pip install pillow` |
| **附属要素显示问号** | `terminus` / `custom1-5` / `caelum` / `tabernus` / `evolutio` 没图标 | 它们的**贴图文件名和 tag 对不上**：GT 用大写 `AEQUALITAS.png` 注册成 `custom1`；`terminus` 在 `avaritia/textures/misc/`、`evolutio` 在 `gtnhcommunitymod/textures/icons/`，都不在 `textures/aspects/` 下。必须用 `/aemobile dump aspects` 导出的 `aspect-images.tsv`（`Aspect.getImage()` 的真实路径），`build_aspects.py --images` 按路径取图 |
| **流体图标覆盖不全** | 像「超临界致密蒸汽」这种没图标 | `fluid_icon` 的名字来源要取 **`fluid_container ∪ fluid_name ∪ 图集坐标** 的并集；只按 `fluid_container`（有容器的）建表会漏掉几百个只有名字的流体 |
| **只按文件名扫源质贴图** | 附属模组要素缺失 | 索引要覆盖 **所有 png**（不只 `textures/aspects/`），但只记「在哪个 jar」按需读取，否则内存吃几百 MB |
| **`embed_pack.py` 会把新库盖回旧的** | 刚建完库、再 embed 出 APK，装上去还是老图标 | 两个脚本方向相反：`update_packs.py` 直接写 `AEMobileApp/assets/`，`embed_pack.py` 是「`iconpack/` → `assets/`」。先 embed 后建库就会用旧库覆盖（2026-10-29 实际踩到，189MB 新库被 185MB 旧库盖掉，`bundled.ts` 的 sha 还是旧的）。现在 `update_packs.py` 末尾会自动 `sync_iconpack_dir()`，顺序反了也不会错，但**别手工只跑一半** |
| **换了库设备上没变化** | APK 重装了，图标还是旧的 | 先比 sha：`adb shell sha256sum /data/data/<pkg>/files/SQLite/*.db` 与本地 `assets/*.db` 对照。App 侧只认「内置包 sha 标记」，标记对上就不复制；标记键带 `v2` 前缀（v1 有「按文件大小跳过」的 bug，`fluids.db` 新旧都是 2007040 字节会误判） |

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
