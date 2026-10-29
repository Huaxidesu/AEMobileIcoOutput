# -*- coding: utf-8 -*-
"""一键更新三个图标库（items / fluids / essentia），并生成在线更新包。

用法（在 AEMobileIcoOutput 目录下）：
    python update_packs.py                # 三个库全更新 + 生成更新包
    python update_packs.py --only essentia
    python update_packs.py --only items,essentia --no-pack
    python update_packs.py --note "补 3 个新方块图标"

做的事：
  1. items     : 用游戏里 /aemobile dumpicons 导出的图标重建 items.db（带索引）
  2. essentia  : 扫 mods 目录里所有 jar 的源质贴图 + 汉化，重建 essentia.db
                 （有 /aemobile dump aspects 的颜色表就把颜色烘进图标）
  3. fluids    : 用 GT 汉化刷新 fluids.db 的 fluid_name 表（fluid_container 不动），
                 再用图集快照 / mods 里的流体贴图 + 颜色重建 fluid_icon 表
  4. 同步 sha256 到 AEMobileApp/src/iconpack.ts 的 BUILTIN_SHAS
  5. 生成更新包（version.json + icons/*.db + .gz）到 --out 目录

路径怎么配（三档，后者覆盖前者）：
  1. 下面的 CONFIG 是默认值
  2. 同目录的 pack_config.json 覆盖它（换机器只改这个文件，不动代码）
  3. 命令行 --lang / --mods / --dumps ... 覆盖前两者

GT 汉化文件（流体中文名的来源）是**必须**的：没它 fluids 那步会报错停下。
它不需要手动下载 —— GTNH 客户端实例根目录就自带一份，脚本会自动去那儿找；
也可以用 --lang 指定，或写进 pack_config.json。
"""
import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

CONFIG = {
    # 主工程（AEMobileApp / AEMobile / tools 都在这里面）
    'project': r'D:/Develop/Game/AEMobildAll',
    # GTNH 客户端实例（mods 目录用来抽源质图标）
    'mods': r'D:/Game/Minecraft/MMCproject/instances/GTNHRC2/.minecraft/mods',
    # 游戏里 /aemobile dumpicons 的产物目录
    'dumps': r'D:/Game/Minecraft/MMCproject/instances/GTNHRC2/.minecraft/dumps/aemobile/items',
    # 游戏里 /aemobile dump fluids|aspects 的产物目录（颜色表 + 图集快照）
    'dumps_dir': r'D:/Game/Minecraft/MMCproject/instances/GTNHRC2/.minecraft/dumps/aemobile',
    'fluid_colors': r'D:/Game/Minecraft/MMCproject/instances/GTNHRC2/.minecraft/dumps/aemobile/fluid-colors.tsv',
    'aspect_colors': r'D:/Game/Minecraft/MMCproject/instances/GTNHRC2/.minecraft/dumps/aemobile/aspect-colors.tsv',
    # 源质贴图的真实路径（Aspect.getImage），附属要素靠它才能取到图
    'aspect_images': r'D:/Game/Minecraft/MMCproject/instances/GTNHRC2/.minecraft/dumps/aemobile/aspect-images.tsv',
    # GregTech 汉化文件（流体中文名）。留空 = 自动去客户端实例根目录找；
    # 换了机器又不想自动找，就在 pack_config.json 里写死，或命令行 --lang
    'lang': '',
    # 在线更新仓库里的 ae/ 目录
    'out': r'D:/Develop/Game/update/dsmgtnhupdate/ae',
}

DB = {
    'items': 'items.db',
    'fluids': 'fluids.db',
    'essentia': 'essentia.db',
}

# 本机路径放这儿，别写进代码（换机器/换实例只改这个文件）
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pack_config.json')

# GT 汉化文件在实例里的常见位置（GTNH 整合包自带）
LANG_NAMES = (
    'GregTech_zh_CN.lang',
    'GregTech.lang',
    os.path.join('config', 'GregTech', 'GregTech_zh_CN.lang'),
    os.path.join('config', 'GregTech_zh_CN.lang'),
)


def load_config():
    """CONFIG 打底，pack_config.json 覆盖"""
    cfg = dict(CONFIG)
    if not os.path.isfile(CONFIG_FILE):
        return cfg
    try:
        with open(CONFIG_FILE, encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        raise SystemExit('%s 读不了：%s' % (CONFIG_FILE, e))
    for k, v in data.items():
        if isinstance(v, str) and v.strip():
            cfg[k] = v.strip()
    return cfg


def find_lang(cfg, override=None):
    """找 GT 汉化文件：--lang > 配置 > 客户端实例目录 > Downloads 里最新的。

    返回 (路径, 来源说明)；找不到返回 (None, 找过的位置)。
    """
    tried = []
    if override:
        if not os.path.isfile(override):
            raise SystemExit('--lang 指的文件不存在：%s' % override)
        return override, '--lang'

    if cfg.get('lang'):
        tried.append(cfg['lang'])
        if os.path.isfile(cfg['lang']):
            return cfg['lang'], 'pack_config.json / CONFIG'

    # 客户端实例根目录（mods 的上一级是 .minecraft）
    mods = cfg.get('mods') or ''
    if mods:
        inst = os.path.dirname(os.path.abspath(mods.rstrip('/\\')))
        for name in LANG_NAMES:
            p = os.path.join(inst, name)
            tried.append(p)
            if os.path.isfile(p):
                return p, '客户端实例自带'

    # 以前手动下载过的话，Downloads 里通常有
    for p in sorted(glob.glob('C:/Downloads/**/GregTech_zh_CN.lang', recursive=True),
                    key=os.path.getmtime, reverse=True)[:3]:
        tried.append(p)
        if os.path.isfile(p):
            return p, 'Downloads（可能是旧版）'

    return None, tried


def require_lang(cfg, override=None):
    """fluids 那步没它就没法给流体起中文名，直接停"""
    path, source = find_lang(cfg, override)
    if path:
        print('GT 汉化：%s  ← %s' % (path, source))
        return path
    raise SystemExit(
        '找不到 GT 汉化文件（GregTech_zh_CN.lang），流体中文名没来源。\n'
        '它不需要单独下载 —— GTNH 客户端实例根目录就有一份，脚本会自动找。\n'
        '如果你的实例路径不是默认的，任选一种指定：\n'
        '  1) python update_packs.py --lang "D:/.../.minecraft/GregTech_zh_CN.lang"\n'
        '  2) 在 %s 里写 {"lang": "D:/.../GregTech_zh_CN.lang"}\n'
        '找过的位置：\n  %s' % (CONFIG_FILE, '\n  '.join(p for p in (source or []))))


def save_config(cfg):
    """把当前生效的路径写进 pack_config.json，下次不用再传参"""
    data = {k: cfg[k] for k in
            ('project', 'mods', 'dumps', 'dumps_dir', 'fluid_colors', 'aspect_colors',
             'aspect_images', 'out')
            if cfg.get(k)}
    # 汉化文件按「实际找到的那份」记下来，别存空值
    lang = cfg.get('lang')
    if not lang:
        lang = find_lang(cfg)[0]
    if lang:
        data['lang'] = lang
    with open(CONFIG_FILE, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print('已写入 %s' % CONFIG_FILE)


# 启动时合并一次（CONFIG 默认值 + pack_config.json）
CFG = load_config()


def run(cmd, cwd=None):
    print('\n$ ' + ' '.join(cmd))
    r = subprocess.run(cmd, cwd=cwd)
    if r.returncode != 0:
        raise SystemExit('命令失败：%s' % ' '.join(cmd))


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def rebuild(kind, args):
    """重建单个库"""
    assets = os.path.join(CFG['project'], 'AEMobileApp', 'assets')
    scripts = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts')
    target = os.path.join(assets, DB[kind])

    if kind == 'items':
        src = args.dumps or CFG['dumps']
        if not os.path.isdir(src):
            raise SystemExit('找不到图标导出目录：%s\n先在游戏里跑 /aemobile dumpicons' % src)
        # 必须显式给 --db：脚本的默认值是相对的，而这里 cwd 是 AEMobileIcoOutput
        run([sys.executable, os.path.join(scripts, 'build_item_icons.py'), src,
             '--db', target, '--rebuild'])
    elif kind == 'essentia':
        src = args.mods or CFG['mods']
        if not os.path.isdir(src):
            raise SystemExit('找不到 mods 目录：%s' % src)
        cmd = [sys.executable, os.path.join(scripts, 'build_aspects.py'), src, target]
        colors = args.aspect_colors or CFG['aspect_colors']
        if os.path.isfile(colors):
            cmd = [sys.executable, os.path.join(scripts, 'build_aspects.py'), src,
                   '--colors', colors, target]
        else:
            print('提示：没有 %s，源质图标存灰度蒙版，App 用服务端颜色现染' % colors)
            print('      想烘死颜色就先在游戏里跑 /aemobile dump aspects')
        images = args.aspect_images or CFG.get('aspect_images')
        if images and os.path.isfile(images):
            cmd = cmd[:-1] + ['--images', images, cmd[-1]]
        run(cmd)
    elif kind == 'fluids':
        # GT 汉化：流体中文名的唯一来源，没有就直接停（自动去实例目录找，见 require_lang）
        src = require_lang(CFG, args.lang)
        run([sys.executable, os.path.join(scripts, 'build_fluid_names.py'), src, target])
        # 流体图标：贴图从 mods 抽、颜色从游戏导（没有颜色表就存灰度图，App 端现染）
        mods = args.mods or CFG['mods']
        if not os.path.isdir(mods):
            raise SystemExit('找不到 mods 目录：%s' % mods)
        cmd = [sys.executable, os.path.join(scripts, 'build_fluid_icons.py'), mods, '--db', target]
        # 图集快照（dump fluids 顺手导出的 atlas.raw）优先，它才是游戏里真正画出来的图
        atlas_dir = args.atlas_dir or CFG['dumps_dir']
        if os.path.isfile(os.path.join(atlas_dir, 'atlas.raw')):
            cmd += ['--atlas-dir', atlas_dir]
        colors = args.fluid_colors or CFG['fluid_colors']
        if os.path.isfile(colors):
            cmd += ['--colors', colors]
        else:
            print('提示：没有 %s，流体图标存灰度图，App 用服务端颜色现染' % colors)
            print('      想烘死颜色就先在游戏里跑 /aemobile dump fluids')
        run(cmd)
    else:
        raise SystemExit('未知的库：%s' % kind)


def sync_shas(kinds):
    """把三个库的 sha256 写进 AEMobileApp/src/iconpack.ts 的 BUILTIN_SHAS"""
    assets = os.path.join(CFG['project'], 'AEMobileApp', 'assets')
    ts = os.path.join(CFG['project'], 'AEMobileApp', 'src', 'iconpack.ts')
    src = open(ts, encoding='utf-8').read()

    shas = {}
    for kind in ('items', 'fluids', 'essentia'):
        path = os.path.join(assets, DB[kind])
        if os.path.isfile(path):
            shas[kind] = sha256(path)

    changed = []
    for kind, digest in shas.items():
        # items 走常量 BUILTIN_ICON_SHA，另外两个直接写在表里
        if kind == 'items':
            src = re.sub(r"export const BUILTIN_ICON_SHA = '[0-9a-f]{64}';",
                         "export const BUILTIN_ICON_SHA = '%s';" % digest, src)
        src = re.sub(r"(\b%s:\s*)'[0-9a-f]{64}'" % kind, r"\g<1>'%s'" % digest, src)
        changed.append('%s %s' % (kind, digest[:12]))

    open(ts, 'w', encoding='utf-8', newline='\n').write(src)
    print('\n已同步 sha256 到 iconpack.ts：' + '，'.join(changed))


def sync_iconpack_dir():
    """把建好的三个库同步一份到 AEMobildAll/iconpack/。

    为什么需要：`embed_pack.py` 默认从 iconpack/ 复制到 AEMobileApp/assets/，
    而本脚本是直接写 assets/ 的。不同步的话，跑完本脚本再跑 embed_pack
    会把刚建好的库覆盖回旧的（2026-10-29 实际踩到：新库 189MB 被 185MB 的旧库盖掉，
    APK 里 bundled.ts 的 sha 还是旧的，App 启动时判定「内置包没变」直接跳过落地）。
    """
    assets = os.path.join(CFG['project'], 'AEMobileApp', 'assets')
    local = os.path.join(CFG['project'], 'iconpack')
    try:
        os.makedirs(local, exist_ok=True)
        for kind in ('items', 'fluids', 'essentia'):
            src = os.path.join(assets, DB[kind])
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(local, DB[kind]))
        print('已同步副本到 iconpack/')
    except Exception as e:
        print('同步 iconpack/ 失败（不影响本次建库）：%s' % e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='items,fluids,essentia', help='只更新这几库，逗号分隔')
    ap.add_argument('--no-pack', action='store_true', help='不生成在线更新包')
    ap.add_argument('--no-sha', action='store_true', help='不自动改 iconpack.ts 里的 sha256')
    ap.add_argument('--note', default='', help='更新说明，写进 version.json')
    ap.add_argument('--out', default=None, help='更新仓库的 ae/ 目录')
    ap.add_argument('--dumps', default=None, help='图标导出目录')
    ap.add_argument('--mods', default=None, help='客户端 mods 目录')
    ap.add_argument('--lang', default=None,
                    help='GregTech 汉化文件（不给就自动去客户端实例根目录找）')
    ap.add_argument('--atlas-dir', default=None, help='dump fluids 导出的图集目录（atlas.raw）')
    ap.add_argument('--fluid-colors', default=None, help='/aemobile dump fluids 导出的流体颜色表')
    ap.add_argument('--aspect-colors', default=None, help='/aemobile dump aspects 导出的源质颜色表')
    ap.add_argument('--aspect-images', default=None, help='/aemobile dump aspects 导出的源质贴图路径表')
    ap.add_argument('--save-config', action='store_true',
                    help='把这次生效的路径写进 pack_config.json，下次不用再传')
    args = ap.parse_args()

    # 命令行参数覆盖配置，覆盖完（可选）落盘
    for key, val in (('lang', args.lang), ('mods', args.mods), ('dumps', args.dumps),
                     ('dumps_dir', args.atlas_dir), ('out', args.out),
                     ('fluid_colors', args.fluid_colors), ('aspect_colors', args.aspect_colors),
                     ('aspect_images', args.aspect_images)):
        if val:
            CFG[key] = val
    if args.save_config:
        save_config(CFG)

    kinds = [k.strip() for k in args.only.split(',') if k.strip()]
    for k in kinds:
        if k not in DB:
            raise SystemExit('未知的库：%s（可选 items / fluids / essentia）' % k)

    print('要更新的库：' + '、'.join(kinds))
    for kind in kinds:
        rebuild(kind, args)

    if not args.no_sha:
        sync_shas(kinds)

    # 让 iconpack/ 跟着更新：embed_pack.py 是从那儿复制到 assets/ 的
    sync_iconpack_dir()

    if not args.no_pack:
        out = args.out or CFG['out']
        cmd = [sys.executable, os.path.join(CFG['project'], 'AEMobileApp', 'buildiconpack.py'),
               '--out', out]
        if args.note:
            cmd += ['--note', args.note]
        run(cmd)

    print('\n完成。')
    print('  下一步：把更新包 push 到 Gitea；如果要出 APK，跑')
    print('  cd %s/AEMobileApp/android && ./gradlew assembleRelease' % CFG['project'])


if __name__ == '__main__':
    main()
