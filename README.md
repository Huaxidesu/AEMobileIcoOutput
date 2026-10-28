# AEMobile 图标库

AEMobile 是 GTNH 的手机端物品终端。这个仓库放它的**图标数据工具**：物品图标、流体图标、神秘时代源质图标。

> **App 不内置图标库**，也没有预设服务器。图标是各模组的艺术作品，不随安装包分发 ——
> 由服主自己搭一份更新源，玩家导入配置包后从那儿下载。

| 库 | 内容 | 大小 |
|---|---|---|
| 物品 | 6 万多个物品的图标和中文名 | ~186MB |
| 流体 | 流体名字、流体和容器物品的对应关系 | ~216KB |
| 源质 | 神秘时代要素的图标和名字 | ~180KB |

三个库**分开更新**：哪个变了才下哪个，补一个源质图标不会重下 186MB。

---

## 一、玩家：怎么用

### 1. 拿到服主给的配置包（一个 `.zip`）

里面是服务器地址、线路列表、图标库更新源。

### 2. 第一次打开 App

会停在「首次使用」页：

- **方式一**：点「选择配置文件（.zip）」，选服主给的包 —— 服务器、线路、图标源一次到位
- **方式二**：手动填图标源地址（服主提供，形如 `https://xxx/ae/version.json`）

### 3. 点「下载图标库」

第一次约 186MB（保持前台），之后只下变化的部分。下载完自动进主界面。

以后想换服务器或更新图标：**设置 → 图标库 / 服务器**。

---

## 二、服主：怎么搭

### 2.1 准备三个库

在装了 AEMobile mod 的客户端里导出图标，然后一键重建：

```bash
# 游戏里（进世界后）：/aemobile dumpicons
cd AEMobileIcoOutput
python update_packs.py --note "GTNH 2.9.1 图标"
```

细节见 [AGENTS.md](AGENTS.md) §0。

### 2.2 发布更新源

把 `buildiconpack.py` 生成的目录（`version.json` + `icons/*.db` + `.db.gz`）放到任意能直链访问的地方
（Gitea / Nginx / 对象存储都行），记下 `version.json` 的完整 URL。

**别放 GitHub** —— 图标是模组作者的作品，别把 186MB 的库塞进公开仓库。

### 2.3 做一个配置包发给玩家

```bash
python make_bundle.py \
    --ip mc.example.com \
    --name "我的服务器" \
    --icon-source https://cdn.example.com/ae/version.json \
    --from-server-list servers.json \
    --out dist
```

得到 `dist/aemobile-config.zip`（几 KB）。玩家装上 APK、导入这个包、点一下下载就能用。

`servers.json` 是可选的线路列表：

```json
[
  { "host": "mc.example.com",  "port": "44444", "name": "主线路" },
  { "host": "mc2.example.com", "port": "44444", "name": "备用", "tag": "IPv6" }
]
```

### 2.4（可选）出一个内置图标包的 APK

想让玩家连下载都省掉：

```bash
python embed_pack.py          # 把三个库写进 AEMobileApp/assets + 生成 src/bundled.ts
cd ../AEMobileApp/android && JAVA_HOME=<jdk17> ./gradlew assembleRelease
python embed_pack.py --restore   # 出完包还原，别提交进仓库
```

这样装出来的 APK 首次启动就有图标。**这个 APK 只能自己分发**，别传公开仓库。

---

## 三、目录内容

```
AEMobileIcoOutput/
├── README.md          本文件：玩家用法 + 服主搭建
├── AGENTS.md          维护者 / AI 工作指引（更新流程、脚本、踩坑、提交规范）
├── update_packs.py    一键重建三个库 + 同步 sha256 + 生成更新包
├── make_bundle.py     生成给玩家的配置包 zip
├── embed_pack.py      把库编译进 APK（出内置包用）
└── scripts/           四个建库脚本（副本，主副本在 AEMobildAll/tools）
```

---

## 四、常见问题

**Q：物品页有图标空白？**
A：那个「物品名 + meta」没被导出过。维护者重新跑一次全量导出即可。

**Q：流体和源质在「可合成」里看不到？**
A：它们本来就不可合成。第一行点开「流体」「源质」，第二行切到「全部」。

**Q：搜索搜不到流体/源质？**
A：搜索按显示名匹配，直接搜中文（「氨」「火」）。也支持注册名（`fluid_drop`、`essentia`）。

**Q：下载失败？**
A：确认图标源地址能直接打开 `version.json`；也可以先用「导入配置包」把地址换掉。

---

## 许可

图标素材版权归各自模组作者所有（GregTech、Thaumcraft 及各 GTNH 模组）。本仓库只提供生成与分发工具。
