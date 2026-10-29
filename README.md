# AEMobile 图标库

| 仓库                                                                      | 是什么                          |
| ----------------------------------------------------------------------- | ---------------------------- |
| [AEMobile](https://github.com/Huaxidesu/AEMobile)                       | 服务端 mod：AE 监控器、TCP 服务、图标导出命令 |
| [AEMobileApp](https://github.com/Huaxidesu/AEMobileApp)                 | 手机端 App：AE 监控、物品 / 流体 / 源质终端 |
| **[AEMobileIcoOutput](https://github.com/Huaxidesu/AEMobileIcoOutput)** | 图标库维护包（本仓库）：导出、建库、出包脚本       |

AEMobile 是 GTNH 的手机端物品终端。这个仓库放它的**图标数据工具**：从游戏里导出物品 / 流体 / 源质图标，建成本地库，再分发给玩家。

> **App 不内置图标库，也没有预设服务器。** 图标是各模组的艺术作品，不随安装包分发。
> 分发方式有三种，见 §0；**不搭更新服务器也能用**。

## AI 工具入口

> **用 Claude Code / Cursor / Codex 这类 agent 维护？**
> 把仓库里的 [AGENTS.md](AGENTS.md) 交给它，然后说：
> **「读 AGENTS.md，按 §0.0 帮我更新图标库」**。
>
> 它会带你走完：摸清现状 → 告诉你游戏里该敲哪条命令 → 验收导出产物 → 建库打包 →
> 最后把图标包装到手机上逐项核对。
>
> 你只需要做 AI 做不了的那一步：**进游戏敲命令**（客户端渲染只能人来跑）。

---

## 0. 先选分发方式

| 方式 | 玩家拿到什么 | 需要更新源 | 适合 |
| --- | --- | --- | --- |
| **A. 在线更新** | 配置包或手填地址 → App 自己下载图标 | 需要 | 长期开服、玩家多 |
| **B. 群里发** | 带图标库的 APK + 配置包 | 不需要 | 小服、临时分发 |
| **C. 只发 APK** | 带图标库的 APK，玩家自己填服务器地址 | 不需要 | 最省事 |

两条容易踩的规则：

- **配置包（`.zip`）只有几 KB，不含图标库。** 只发配置包、不搭更新源，玩家会卡在
  「首次使用」页下载图标那一步。
- **App 只有在「APK 内置了图标库」或「下载过图标库」之后才会进主界面。**
  所以 B / C 方案必须用 §4 的带库 APK。

---

## 1. 手动导出（游戏里，必须人来做）

### 1.1 前提

- 客户端装了 AEMobile mod（服务端和客户端是同一个 jar）。
- **进入世界**（不是主菜单），等 NEI 物品面板加载完，再敲命令。
- 新版本换过 GTNH 整合包时，先确认 `mods/` 里的 jar 是新的：jar 在游戏启动时才加载，
  旧 jar 不会认识新命令。

### 1.2 命令

```
/aemobile dump all [尺寸]          三样一起：物品图标 + 流体颜色 + 源质颜色
/aemobile dump items [尺寸]        只导物品图标（默认 128px）
/aemobile dump fluids              只导流体颜色表 + 图集快照
/aemobile dump aspects             只导源质颜色表 + 贴图路径表
/aemobile dumpicons [list] [尺寸]  老入口 = dump items（list：只导清单里的物品）
/aemobile dumpcolors               老入口 = dump fluids aspects
```

| 需求 | 用哪条 | 说明 |
| --- | --- | --- |
| 换 GTNH 版本后全套更新 | `/aemobile dump all` | 物品那一步会花屏，可按 Esc 中止 |
| 只补物品图标 | `/aemobile dump items 64` | 64px 体积减半，手机上会略糊 |
| 只补流体 | `/aemobile dump fluids` | 秒级，顺便写 `atlas.raw` |
| 只补源质 | `/aemobile dump aspects` | 秒级，顺便写 `aspect-images.tsv` |
| 补清单里的少数物品 | `/aemobile dumpicons list` | 清单在 `config/aemobile-dump-items.txt` |

只有物品会走 GL 渲染，所以会花屏；流体和源质是纯文件 IO，不会卡游戏。

### 1.3 产物

```
<客户端>/.minecraft/dumps/aemobile/
├── items/<modid>/<item>_<meta>.png     物品图标
├── items/manifest.jsonl                物品清单
├── fluid-colors.tsv                    流体颜色
├── fluid-atlas.tsv                     流体在图集里的坐标
├── atlas.raw                           blocks 图集快照（8192×8192 RGBA）
├── aspect-colors.tsv                   源质颜色
└── aspect-images.tsv                   源质贴图的真实路径
```

### 1.4 先验收，别急着建库

| 检查 | 期望 |
| --- | --- |
| `items/manifest.jsonl` 行数 | 几万行；明显偏少 = 导到一半被 Esc 了 |
| `fluid-colors.tsv` 行数 | 约 1550 |
| `fluid-atlas.tsv` 第一行 | `# atlas 8192 8192` |
| `atlas.raw` 大小 | `8192 × 8192 × 4 = 268435456` 字节 |
| `aspect-colors.tsv` 行数 | 约 70 |
| `aspect-images.tsv` 行数 | 约 70；没有就是 mod 太旧 |

数字对不上就先重导，不要带着半份产物建库。

---

## 2. 建库 + 打包

### 2.1 环境

- Python 3（只用标准库）。
- `build_fluid_icons.py` 额外需要 Pillow：`pip install pillow`。
- **GTNH 汉化文件 `GregTech_zh_CN.lang` 是必需的**，流体的中文名靠它。GTNH 客户端实例根目录就自带一份，
  不用单独下载；脚本会自动找，找不到会停下并打印找过的位置。

### 2.2 第一次在这台机器上跑

先把本机路径记下来（会写到 `pack_config.json`，该文件不入库）：

```bash
cd AEMobileIcoOutput
python update_packs.py --only essentia --no-pack --no-sha --save-config
```

这条命令会先把当前路径写入 `pack_config.json`，再试建一次源质库。
如果路径不对，建库阶段会报错，但配置已经写好了 —— 改完 `pack_config.json` 再跑即可。

如果实例路径不是默认的，也可以在这一步直接用参数指定，或之后手动改 `pack_config.json`：

```bash
python update_packs.py --only essentia --no-pack --no-sha --save-config \
    --dumps "<实例>/.minecraft/dumps/aemobile/items" \
    --mods  "<实例>/.minecraft/mods" \
    --atlas-dir "<实例>/.minecraft/dumps/aemobile" \
    --out   "<更新仓库>/ae"
```

### 2.3 一键重建

```bash
python update_packs.py --note "GTNH 2.9.1 图标"
```

它会按顺序做这些事：

| 步骤 | 实际动作 | 耗时 |
| --- | --- | --- |
| 物品 | `scripts/build_item_icons.py <dumps> --rebuild` | 约 30 秒 |
| 流体 | 建中文名 + 按图集坐标裁图标 | 约 3 秒 |
| 源质 | 按 `aspect-images.tsv` 取图 + 烘颜色 | 约 3 秒 |
| 同步 | 三个库的 sha256 写回 `AEMobileApp/src/iconpack.ts` | 1 秒 |
| 备份 | 把三个库同步一份到 `AEMobildAll/iconpack/` | 视磁盘 |
| 打包 | `AEMobileApp/buildiconpack.py --out <更新仓库>/ae` | 约 2 分钟（186MB 要 gzip） |

只更新其中一类：

```bash
python update_packs.py --only essentia
python update_packs.py --only fluids,essentia --no-pack
```

`--no-pack` 不生成更新包，`--no-sha` 不改 `iconpack.ts`；调试时用，正式出包不要加。

### 2.4 产物结构

```
<更新仓库>/ae/
├── version.json                清单（schema 2：items / fluids / essentia 各一段）
└── icons/
    ├── items.db                约 186MB，App 下载的就是它
    ├── items.db.gz             压缩版（备用）
    ├── fluids.db               约 2MB
    ├── fluids.db.gz
    ├── essentia.db             约 240KB
    └── essentia.db.gz
```

三个库分开更新：哪个变了才下哪个，补一个源质图标不会重下 186MB。
App 目前下载**未压缩的 `.db`**，`.gz` 是备用产物。

---

## 3. 分发 A：在线更新（搭更新源）

### 3.1 更新源可以搭，也可以不搭

- **不搭**：走 §4 出带图标库的 APK，玩家装上就有图标；配置包只负责服务器地址。
- **搭**：玩家第一次下载约 186MB，之后只下变化的部分，适合长期开服。

### 3.2 用 Gitea 建一个图标仓库（示例）

下面用 `https://git.example.com` 占位，换成你自己的 Gitea 地址即可。

1. 新建一个**公开**仓库，例如 `aemobile-icons`。
   - 必须公开：App 拉 `raw` 是匿名请求，私有仓库会返回登录页 HTML。
2. 把 §2.4 的产物放进仓库的 `ae/` 目录：

   ```bash
   cd <更新仓库>
   mkdir -p ae
   cp -r <update_packs.py 的输出目录>/* ae/
   ```

   也可以让 `update_packs.py --out` 直接输出到 `<更新仓库>/ae`，省掉复制。

3. 提交并推送。物品库是 186MB，第一次 push 前先放开缓冲区：

   ```bash
   git config http.postBuffer 524288000
   git add ae
   git commit -m "icons: GTNH 2.9.1"
   git push
   ```

   如果 Gitea 实例或反向代理限制了单文件大小，改用 Nginx / 对象存储托管这份 `ae/`。

4. 取 `version.json` 的直链：

   ```
   https://git.example.com/<用户名>/aemobile-icons/raw/branch/main/ae/version.json
   ```

   - 网页地址里的 `/src/branch/main/...` 也能填，App 会自动换成 `/raw/branch/`。
   - 填目录地址时，App 会自动补 `version.json`。
   - 默认分支不是 `main` 时，把 `main` 换成实际分支名。

5. 先用浏览器无痕窗口打开这个地址，确认返回的是 **JSON**（能看到 `"schema": 2` 和三个库的
   `sha256` / `size`），不是登录页或 404。

6. 在 App 里填：

   - 首次使用页：**方式二**，粘贴 `version.json` 地址 → 「下载图标库并进入」。
   - 已经进过主界面：**设置 → 图标库 → 更新源**，填地址 → 「检查更新」。

### 3.3 其它托管方式

- **Nginx**：把 `ae/` 放到站点目录，确保 `version.json` 能直接打开。
- **对象存储**（S3 / OSS / R2 等）：把 `ae/` 设为公共读，用公网直链。
- **临时局域网源**（不想搭服务器，先给几个人用）：

  ```bash
  cd <更新仓库>          # 这里要有 ae/version.json
  python -m http.server 8765
  ```

  手机和电脑连同一个 Wi-Fi，App 里填：

  ```
  http://<电脑的局域网 IP>:8765/ae/version.json
  ```

  电脑防火墙要放行 8765；App 允许 HTTP 明文，所以局域网临时用没问题。
  这个地址只在电脑开机、服务运行时有效，不适合长期分发给玩家。

---

## 4. 分发 B / C：构建带图标库的 APK

适合「不想搭更新源」或「想让玩家装上就有图标」。图标库会编进 APK，首次启动不用联网下载。

### 4.1 把库写进 App

```bash
cd AEMobileIcoOutput
python embed_pack.py
```

默认从 `AEMobildAll/iconpack/` 取三个库（`update_packs.py` 每次跑完都会同步到这里）；
库在别处时用 `--src <目录>`。

它会做两件事：

- 把 `items.db` / `fluids.db` / `essentia.db` 复制到 `AEMobileApp/assets/`；
- 重写 `AEMobileApp/src/bundled.ts`，写入三个库的 `require` 和 sha256。

### 4.2 打包

```bash
cd ../AEMobileApp/android
./gradlew assembleRelease
```

- `JAVA_HOME` 用系统默认的 JDK 17 即可，不需要在命令里写死路径。
  Windows PowerShell 可以先确认：`echo $env:JAVA_HOME`。
- 产物：`app/build/outputs/apk/release/app-release.apk`。

### 4.3 安装并验收

```bash
adb install -r app/build/outputs/apk/release/app-release.apk
adb shell sha256sum /data/data/dev.youtiao.aemonitor/files/SQLite/*.db
adb logcat -d | grep AEMobile
```

- 设备上三个库的 sha256 要和本地 `AEMobileApp/assets/*.db` 对得上。
- `logcat` 里不能有 `attach-fail` / `fluid-icon-fail`。
- 打开 App，切到「流体」「源质」筛选，确认不是色块或问号。

`adb install -r` 会保留旧数据；换库后如果界面没变化，先 `adb shell pm clear dev.youtiao.aemonitor`
或卸载重装再判断。

### 4.4 出完包还原

```bash
cd AEMobileIcoOutput
python embed_pack.py --restore
```

`--restore` 会删掉 `AEMobileApp/assets/*.db` 并把 `bundled.ts` 置空。
**不要把图标库提交进公开仓库**（`AEMobileApp/.gitignore` 已忽略 `/assets/*.db`）：

- 图标是各模组作者的作品，只在自己分发 APK 时内置；
- 这个 APK 也只能自己分发，不要传到公开仓库或应用商店。

---

## 5. 分发 A 的配置包：手动导入

配置包是用来**省掉玩家手填服务器地址**的，几 KB，不含图标库。

```bash
cd AEMobileIcoOutput
python make_bundle.py \
    --ip mc.example.com \
    --name "主服务器" \
    --icon-source https://git.example.com/<用户名>/aemobile-icons/raw/branch/main/ae/version.json \
    --from-server-list servers.json \
    --out dist
```

产物 `dist/aemobile-config.zip`，里面是：

```
config.json     默认服务器 + 图标源 + 服务器列表源
servers.json    线路列表（可选）
README.txt      给玩家的说明
```

`servers.json` 是可选的线路列表：

```json
[
  { "host": "mc.example.com",  "port": "44444", "name": "主线路" },
  { "host": "mc2.example.com", "port": "44444", "name": "备用", "tag": "IPv6" }
]
```

玩家侧的操作：

1. 第一次打开 App，停在「首次使用」页。
2. 点「选择配置文件（.zip）」，选服主给的包 —— 服务器地址、线路、图标源一次到位。
3. 点「下载图标库」（约 186MB，保持前台）。
4. 以后要换服务器或更新图标：**设置 → 图标库 / 服务器列表**。

**不想搭更新源时**，不要只发这个 zip：它没有图标，玩家导入后仍然下载不到图标。
正确的组合是「§4 的带库 APK + 这个配置包」；或者干脆只发带库 APK，让玩家自己填地址和密码。

如果玩家已经有图标库，只想换服务器，也可以只用 App 里的手动入口：
设置 → 服务器与账号，直接填地址、端口、密码。

---

## 6. 目录与脚本

```
AEMobileIcoOutput/
├── README.md          本文件：导出、建库、分发
├── AGENTS.md          维护者 / AI 工作指引（完整流程、踩坑、验收、提交规范）
├── update_packs.py    一键重建三个库 + 同步 sha256 + 生成更新包
├── make_bundle.py     生成给玩家的配置包 zip
├── embed_pack.py      把库写进 APK（出内置包用）
├── pack_config.json   本机路径（不入库，第一次 --save-config 生成）
└── scripts/           建库脚本（副本，主副本在 ../tools）
```

相关的本地目录：

```
AEMobildAll/iconpack/{items,fluids,essentia}.db     本地库副本，embed_pack.py 默认从这儿取
AEMobileApp/assets/*.db                             出 APK 时临时放库，不入库
AEMobileApp/src/bundled.ts                          内置包的 sha256 标记，由 embed_pack.py 生成
```

---

## 7. 常见问题

**Q：不搭更新服务器行不行？**
A：行。用 §4 出带图标库的 APK，玩家装上就有图标；服务器地址可以发配置包，也可以让玩家自己填。
但只发配置包不行 —— 包里没有图标。

**Q：玩家导入配置包后还是没图标？**
A：配置包只含服务器 / 线路 / 图标源，不含图标文件。要么让他点「下载图标库」，
要么给他带库 APK。确认图标源地址能直接打开 `version.json`。

**Q：App 提示下载失败，但浏览器能打开 `version.json`？**
A：依次检查：地址是不是 `raw` 直链（不是网页 `/src/` 页面）；仓库是不是公开；
返回的是不是 JSON（私有仓库会返回登录页 HTML）；手机能不能访问这个域名。

**Q：物品页有图标空白？**
A：那个「物品名 + meta」没被导出过。维护者重新跑一次全量导出即可
（`/aemobile dump all` 或补清单）。

**Q：流体是灰白的？**
A：没跑 `/aemobile dump fluids`，缺 `atlas.raw`，只能退回「jar 灰度图 × 颜色」。
重跑一次导出，确认 `atlas.raw` 大小是 `8192 × 8192 × 4`。

**Q：源质显示问号？**
A：缺 `aspect-images.tsv`，或 mod 太旧没导这张表；附属模组的要素文件名和 tag 对不上，
必须按这张表取图。详见 `AGENTS.md` §4。

**Q：流体和源质在「可合成」里看不到？**
A：它们本来就不可合成。第一行点开「流体」「源质」，第二行切到「全部」。

**Q：搜索搜不到流体 / 源质？**
A：搜索按显示名匹配，直接搜中文（「氨」「火」）。也支持注册名（`fluid_drop`、`essentia`）。

**Q：改了库，App 没提示更新？**
A：App 只比 `version.json` 里的 sha256。确认重新跑了 `update_packs.py`（不要加 `--no-pack`），
并且把新的 `version.json` + `icons/` 推上去了。

**Q：同样的数据，为什么重复打包也会让所有人更新一次？**
A：合并 / 重建后行顺序和页布局会变，内容相同、字节不同，sha256 就变了。
**同样的数据不要重复打包上传。**

---

## 许可

图标素材版权归各自模组作者所有（GregTech、Thaumcraft 及各 GTNH 模组）。
本仓库只提供生成与分发工具；图标库本身请通过自建更新源或自行分发的 APK 提供，不要提交到公开仓库。
