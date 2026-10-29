# -*- coding: utf-8 -*-
"""从 Thaumcraft 4 及其附属的 jar 里抽出源质（aspect）图标和中文名，生成 assets/essentia.db。

用法：
    python tools/build_aspects.py <mods 目录> [--colors <aspect-colors.tsv>]
                                  [--images <aspect-images.tsv>] [输出 db 路径]
      python tools/build_aspects.py <jar1> <jar2> ... [--colors ...] <输出 db>   （最后一个参数是输出）

- 图标：`assets/<modid>/textures/aspects/<tag>.png`（TC4 自带 50 个，附属模组还有十来个）
- 贴图路径（`--images`，游戏里 `/aemobile dump aspects` 导出）：附属模组注册的要素
  （custom1-5 / caelum / tabernus / terminus / evolutio）**文件名和 tag 对不上**，
  只靠文件名匹配会落到问号图标，必须按 `Aspect.getImage()` 给的真实路径去找
- 中文名：各 jar 里 `assets/<modid>/lang/zh_CN.lang` 的 `tc.aspect.<tag>=火,火焰`（取逗号前第一个）
- 同一个 tag 多个来源时，后扫到的覆盖前面的（附属模组的自定义贴图优先）

颜色（`--colors`，游戏里 `/aemobile dumpaspects` 导出）：
- 源质贴图是**灰度蒙版**，游戏里靠 `Aspect.getColor()` 乘上去。给了颜色表就把颜色烘进 PNG
  （tint=0），App 直接显示；没给就原样入库（tint=1），App 用服务端 NBT 里的 Color 现染。
"""
import base64
import io
import json
import os
import re
import sqlite3
import sys
import zipfile


def read_lang(z, name):
    try:
        raw = z.read(name)
    except KeyError:
        return {}
    out = {}
    for line in raw.decode('utf-8', 'replace').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        out[k.strip()] = v.strip()
    return out


def scan_jar(path, icons, names, png_index):
    try:
        z = zipfile.ZipFile(path)
    except Exception:
        return
    for name in z.namelist():
        if name.endswith('.png'):
            # 只记「在哪」，不读字节：源质贴图有些不在 textures/aspects 下
            # （terminus 在 avaritia/textures/misc、evolutio 在 gtnhcommunitymod/textures/icons）
            png_index[name] = path
        if '/textures/aspects/' in name and name.endswith('.png'):
            # 贴图文件名有大小写两套（TC4 小写、GT 大写 ELECTRUM.png），统一按小写当键
            tag = name.rsplit('/', 1)[-1][:-4].lower()
            icons[tag] = base64.b64encode(z.read(name)).decode('ascii')
        elif name.endswith('/lang/zh_CN.lang'):
            for k, v in read_lang(z, name).items():
                if k.startswith('tc.aspect.'):
                    names[k[len('tc.aspect.'):].lower()] = v


def load_colors(path):
    """`<tag>\t<RRGGBB>`；也容忍 `#` 注释、空格分隔、以及 `aspect<TAB>tag<TAB>hex` 这种带类型列的行"""
    colors = {}
    if not path:
        return colors
    if not os.path.isfile(path):
        raise SystemExit('找不到颜色表：%s' % path)
    with io.open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.replace('\t', ' ').split()
            if len(parts) >= 3 and parts[0].lower() in ('aspect', 'fluid'):
                parts = parts[1:]
            if len(parts) < 2:
                continue
            try:
                colors[parts[0].lower()] = int(parts[1], 16) & 0xFFFFFF
            except ValueError:
                continue
    return colors


def bake(png_b64, color):
    """灰度蒙版 × 颜色（alpha 保留）。没颜色就原样返回。"""
    if color is None:
        return base64.b64decode(png_b64)
    from PIL import Image
    im = Image.open(io.BytesIO(base64.b64decode(png_b64))).convert('RGBA')
    r, g, b = (color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            pr, pg, pb, pa = px[x, y]
            if pa:
                px[x, y] = (pr * r // 255, pg * g // 255, pb * b // 255, pa)
    buf = io.BytesIO()
    im.save(buf, 'PNG', optimize=True)
    return buf.getvalue()


def load_images(path):
    """`<tag>\\t<domain:path>` —— Aspect.getImage() 给的真实贴图路径（附属模组的要素靠它）"""
    out = {}
    if not path:
        return out
    if not os.path.isfile(path):
        raise SystemExit('找不到贴图表：%s' % path)
    with io.open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.replace('\t', ' ').split()
            if len(parts) >= 2:
                out[parts[0].lower()] = parts[1]
    return out


def main():
    args = sys.argv[1:]
    colors_path = None
    images_path = None
    for flag in ('--colors', '--images'):
        if flag in args:
            i = args.index(flag)
            if i + 1 >= len(args):
                raise SystemExit('%s 后面要跟文件路径' % flag)
            if flag == '--colors':
                colors_path = args[i + 1]
            else:
                images_path = args[i + 1]
            del args[i:i + 2]
    if len(args) < 2:
        print(__doc__)
        return
    out_path = args[-1]
    sources = args[:-1]

    jars = []
    for s in sources:
        if os.path.isdir(s):
            jars += [os.path.join(s, f) for f in sorted(os.listdir(s)) if f.endswith('.jar')]
        else:
            jars.append(s)

    icons, names, png_index = {}, {}, {}
    for j in jars:
        scan_jar(j, icons, names, png_index)
    colors = load_colors(colors_path)
    images = load_images(images_path)

    # 按 Aspect.getImage() 的真实路径补图：附属模组的要素（custom1-5 / caelum / tabernus …）
    # 文件名和 tag 对不上，只靠文件名匹配只能落到问号图标
    fixed = 0
    for tag, rl in images.items():
        domain, _, rel = rl.partition(':')
        if not rel:
            continue
        for cand in ('assets/%s/%s' % (domain, rel), 'assets/%s/%s.png' % (domain, rel)):
            jar = png_index.get(cand)
            if jar:
                with zipfile.ZipFile(jar) as z:
                    icons[tag] = base64.b64encode(z.read(cand)).decode('ascii')
                fixed += 1
                break

    print('扫了 %d 个 jar，%d 个源质贴图，颜色表 %d 条，贴图路径 %d 条（补上 %d 个）'
          % (len(jars), len(icons), len(colors), len(images), fixed))

    if os.path.exists(out_path):
        os.remove(out_path)
    conn = sqlite3.connect(out_path)
    conn.execute('PRAGMA synchronous=OFF')
    conn.execute('create table aspect (tag text primary key, dname text, icon blob, tint integer)')
    rows = []
    baked = 0
    for tag in sorted(icons):
        cn = names.get(tag, tag).split(',')[0].strip() or tag
        color = colors.get(tag)
        if color is not None:
            baked += 1
        # tint=0：颜色已烘进 PNG；tint=1：灰度蒙版，App 用服务端 Color 现染
        rows.append((tag, cn, bake(icons[tag], color), 0 if color is not None else 1))
    conn.executemany('insert into aspect (tag,dname,icon,tint) values (?,?,?,?)', rows)
    conn.commit()
    n = conn.execute('select count(*) from aspect').fetchone()[0]
    conn.close()
    print('%d 个源质（烘了颜色 %d 个）→ %s  %dKB'
          % (n, baked, out_path, os.path.getsize(out_path) // 1024))
    missing = [t for t in icons if t not in names]
    if missing:
        print('没有中文名的:', missing)


if __name__ == '__main__':
    main()
