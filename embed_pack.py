# -*- coding: utf-8 -*-
"""把图标库「编译进」APK：服主想给玩家一个开箱即用的安装包时用。

用法（在 AEMobileIcoOutput 目录下）：
    python embed_pack.py                       # 用 AEMobildAll/iconpack 里的三个库
    python embed_pack.py --src <库目录>
    python embed_pack.py --restore             # 还原成「不内置」

做的事：
  1. 把 items.db / fluids.db / essentia.db 复制到 AEMobileApp/assets/
  2. 重写 AEMobileApp/src/bundled.ts，写入 require + 各自的 sha256
  3. 之后照常 `./gradlew assembleRelease`，装出来的 APK 首次启动就有图标，不用联网

⚠️ 内置的图标是各模组的艺术作品，**只在自己分发时用**，不要提交到公开仓库
   （AEMobileApp/.gitignore 已经忽略 /assets/*.db）。
"""
import argparse
import hashlib
import io
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # AEMobildAll
APP = os.path.join(ROOT, 'AEMobileApp')
ASSETS = os.path.join(APP, 'assets')
BUNDLED_TS = os.path.join(APP, 'src', 'bundled.ts')

KINDS = ['items', 'fluids', 'essentia']

STUB = """// 内置图标包（编译期嵌入）
//
// 默认是空的：图标是各模组的艺术作品，不随公开仓库分发，玩家通过「订阅图标源」在线下载。
// 服主想给玩家一份开箱即用的 APK 时，用 tools/embed_pack.py 生成本文件（会把 assets/*.db 和
// 它们的 sha256 写进来），再打包 APK —— 这样 App 首次启动就有图标，不用联网。
export type BundledPack = { asset: number; sha256: string };

export const BUNDLED_PACKS: Partial<Record<'items' | 'fluids' | 'essentia', BundledPack>> = {};
"""


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def restore():
    for kind in KINDS:
        p = os.path.join(ASSETS, '%s.db' % kind)
        if os.path.exists(p):
            os.remove(p)
    io.open(BUNDLED_TS, 'w', encoding='utf-8', newline='\n').write(STUB)
    print('已还原：assets 里不再有图标库，bundled.ts 置空')


def embed(src):
    lines = [
        '// 内置图标包（编译期嵌入）—— 由 tools/embed_pack.py 生成，别手改',
        'export type BundledPack = { asset: number; sha256: string };',
        '',
        'export const BUNDLED_PACKS: Partial<Record<\'items\' | \'fluids\' | \'essentia\', BundledPack>> = {',
    ]
    total = 0
    for kind in KINDS:
        path = os.path.join(src, '%s.db' % kind)
        if not os.path.isfile(path):
            print('  跳过 %s（没有 %s）' % (kind, path))
            continue
        shutil.copy2(path, os.path.join(ASSETS, '%s.db' % kind))
        digest = sha256(path)
        size = os.path.getsize(path)
        total += size
        lines.append("  %s: { asset: require('../assets/%s.db'), sha256: '%s' }," % (kind, kind, digest))
        print('  %-8s %6.1f MB  %s' % (kind, size / 1048576, digest[:12]))
    lines.append('};')
    lines.append('')
    io.open(BUNDLED_TS, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines))
    print('已写入 %s' % BUNDLED_TS)
    print('合计 %.1f MB —— 接下来跑 android/gradlew assembleRelease' % (total / 1048576))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=os.path.join(ROOT, 'iconpack'), help='三个库所在目录')
    ap.add_argument('--restore', action='store_true', help='还原成不内置')
    args = ap.parse_args()
    if args.restore:
        restore()
    else:
        if not os.path.isdir(args.src):
            raise SystemExit('找不到库目录：%s' % args.src)
        embed(args.src)


if __name__ == '__main__':
    main()
