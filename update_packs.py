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
  3. fluids    : 用 GT 汉化刷新 fluids.db 的 fluid_name 表（fluid_container 不动）
  4. 同步 sha256 到 AEMobileApp/src/iconpack.ts 的 BUILTIN_SHAS
  5. 生成更新包（version.json + icons/*.db + .gz）到 --out 目录

改路径就改下面的 CONFIG。
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys

CONFIG = {
    # 主工程（AEMobileApp / AEMobile / tools 都在这里面）
    'project': r'D:/Develop/Game/AEMobildAll',
    # GTNH 客户端实例（mods 目录用来抽源质图标）
    'mods': r'D:/Game/Minecraft/MMCproject/instances/GTNHRC2/.minecraft/mods',
    # 游戏里 /aemobile dumpicons 的产物目录
    'dumps': r'D:/Game/Minecraft/MMCproject/instances/GTNHRC2/.minecraft/dumps/aemobile/items',
    # GregTech 汉化文件（流体中文名）
    'lang': r'C:/Downloads/nightly-2026-10-28/GregTech_zh_CN.lang',
    # 在线更新仓库里的 ae/ 目录
    'out': r'D:/Develop/Game/update/dsmgtnhupdate/ae',
}

DB = {
    'items': 'items.db',
    'fluids': 'fluids.db',
    'essentia': 'essentia.db',
}


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
    assets = os.path.join(CONFIG['project'], 'AEMobileApp', 'assets')
    scripts = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts')
    target = os.path.join(assets, DB[kind])

    if kind == 'items':
        src = args.dumps or CONFIG['dumps']
        if not os.path.isdir(src):
            raise SystemExit('找不到图标导出目录：%s\n先在游戏里跑 /aemobile dumpicons' % src)
        run([sys.executable, os.path.join(scripts, 'build_item_icons.py'), src, '--rebuild'])
    elif kind == 'essentia':
        src = args.mods or CONFIG['mods']
        if not os.path.isdir(src):
            raise SystemExit('找不到 mods 目录：%s' % src)
        run([sys.executable, os.path.join(scripts, 'build_aspects.py'), src, target])
    elif kind == 'fluids':
        src = args.lang or CONFIG['lang']
        if not os.path.isfile(src):
            raise SystemExit('找不到汉化文件：%s' % src)
        run([sys.executable, os.path.join(scripts, 'build_fluid_names.py'), src, target])
    else:
        raise SystemExit('未知的库：%s' % kind)


def sync_shas(kinds):
    """把三个库的 sha256 写进 AEMobileApp/src/iconpack.ts 的 BUILTIN_SHAS"""
    assets = os.path.join(CONFIG['project'], 'AEMobileApp', 'assets')
    ts = os.path.join(CONFIG['project'], 'AEMobileApp', 'src', 'iconpack.ts')
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='items,fluids,essentia', help='只更新这几库，逗号分隔')
    ap.add_argument('--no-pack', action='store_true', help='不生成在线更新包')
    ap.add_argument('--no-sha', action='store_true', help='不自动改 iconpack.ts 里的 sha256')
    ap.add_argument('--note', default='', help='更新说明，写进 version.json')
    ap.add_argument('--out', default=None, help='更新仓库的 ae/ 目录')
    ap.add_argument('--dumps', default=None, help='图标导出目录')
    ap.add_argument('--mods', default=None, help='客户端 mods 目录')
    ap.add_argument('--lang', default=None, help='GregTech 汉化文件')
    args = ap.parse_args()

    kinds = [k.strip() for k in args.only.split(',') if k.strip()]
    for k in kinds:
        if k not in DB:
            raise SystemExit('未知的库：%s（可选 items / fluids / essentia）' % k)

    print('要更新的库：' + '、'.join(kinds))
    for kind in kinds:
        rebuild(kind, args)

    if not args.no_sha:
        sync_shas(kinds)

    if not args.no_pack:
        out = args.out or CONFIG['out']
        cmd = [sys.executable, os.path.join(CONFIG['project'], 'AEMobileApp', 'buildiconpack.py'),
               '--out', out]
        if args.note:
            cmd += ['--note', args.note]
        run(cmd)

    print('\n完成。')
    print('  下一步：把更新包 push 到 Gitea；如果要出 APK，跑')
    print('  cd %s/AEMobileApp/android && ./gradlew assembleRelease' % CONFIG['project'])


if __name__ == '__main__':
    main()
