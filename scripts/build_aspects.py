# -*- coding: utf-8 -*-
"""从 Thaumcraft 4 及其附属的 jar 里抽出源质（aspect）图标和中文名，生成 assets/essentia.db。

用法：python tools/build_aspects.py <mods 目录> [输出 db 路径]
      python tools/build_aspects.py <jar1> <jar2> ... <输出 db 路径>   （最后一个参数是输出）

- 图标：`assets/<modid>/textures/aspects/<tag>.png`（TC4 自带 50 个，附属模组还有十来个）
- 中文名：各 jar 里 `assets/<modid>/lang/zh_CN.lang` 的 `tc.aspect.<tag>=火,火焰`（取逗号前第一个）
- 同一个 tag 多个来源时，后扫到的覆盖前面的（附属模组的自定义贴图优先）
"""
import base64
import io
import json
import os
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


def scan_jar(path, icons, names):
    try:
        z = zipfile.ZipFile(path)
    except Exception:
        return
    for name in z.namelist():
        if '/textures/aspects/' in name and name.endswith('.png'):
            # 贴图文件名有大小写两套（TC4 小写、GT 大写 ELECTRUM.png），统一按小写当键
            tag = name.rsplit('/', 1)[-1][:-4].lower()
            icons[tag] = base64.b64encode(z.read(name)).decode('ascii')
        elif name.endswith('/lang/zh_CN.lang'):
            for k, v in read_lang(z, name).items():
                if k.startswith('tc.aspect.'):
                    names[k[len('tc.aspect.'):].lower()] = v


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return
    out_path = sys.argv[-1]
    sources = sys.argv[1:-1]

    jars = []
    for s in sources:
        if os.path.isdir(s):
            jars += [os.path.join(s, f) for f in sorted(os.listdir(s)) if f.endswith('.jar')]
        else:
            jars.append(s)

    icons, names = {}, {}
    for j in jars:
        scan_jar(j, icons, names)

    if os.path.exists(out_path):
        os.remove(out_path)
    conn = sqlite3.connect(out_path)
    conn.execute('PRAGMA synchronous=OFF')
    conn.execute('create table aspect (tag text primary key, dname text, icon blob)')
    rows = []
    for tag in sorted(icons):
        cn = names.get(tag, tag).split(',')[0].strip() or tag
        rows.append((tag, cn, base64.b64decode(icons[tag])))
    conn.executemany('insert into aspect (tag,dname,icon) values (?,?,?)', rows)
    conn.commit()
    n = conn.execute('select count(*) from aspect').fetchone()[0]
    conn.close()
    print(f'{n} 个源质（扫了 {len(jars)} 个 jar）→ {out_path}  {os.path.getsize(out_path)//1024}KB')
    missing = [t for t in icons if t not in names]
    if missing:
        print('没有中文名的:', missing)


if __name__ == '__main__':
    main()
