# -*- coding: utf-8 -*-
"""把一个大 itempanel.db 拆成三个库，方便分开更新。

用法：python tools/split_dbs.py [--src <itempanel.db>] [--out <输出目录>] [--lang <GT 汉化>]

产出（默认写到 AEMobileApp/assets/）：
  items.db      item_panel（物品名/meta/显示名/图标）        —— 唯一的大文件，单独更新
  fluids.db     fluid_container（流体→容器物品）+ fluid_name（流体中文名）
  essentia.db   aspect（源质 tag/中文名/图标）

源质图标和流体中文名分别从 src/aspects.ts、src/fluidNames.ts 里读（那两份是之前生成的）。
"""
import io
import json
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, 'AEMobileApp')


def read_ts_aspects(path):
    """从 src/aspects.ts 里抠出 {tag: (中文名, base64 png)}"""
    src = io.open(path, encoding='utf-8').read()
    out = {}
    for m in re.finditer(r'^\s*"([^"]+)":\s*\{\s*n:\s*("(?:[^"\\]|\\.)*"),\s*i:\s*\'([^\']*)\'\s*\},', src, re.M):
        tag = m.group(1)
        name = json.loads(m.group(2))
        out[tag] = (name, m.group(3))
    return out


def read_ts_fluid_names(path):
    src = io.open(path, encoding='utf-8').read()
    out = {}
    for m in re.finditer(r'^\s*"([^"]+)":\s*"((?:[^"\\]|\\.)*)",', src, re.M):
        out[m.group(1)] = json.loads('"' + m.group(2) + '"')
    return out


def make_db(path, ddl, rows, table, cols):
    if os.path.exists(path):
        os.remove(path)
    conn = sqlite3.connect(path)
    conn.execute('PRAGMA synchronous=OFF')
    conn.execute(ddl)
    conn.executemany(f'insert into {table} ({cols}) values ({",".join("?" * len(rows[0]))})', rows)
    conn.commit()
    if table == 'item_panel':
        conn.execute('create index idx_item on item_panel(item_name, item_meta)')
        # 覆盖索引：App 只取 dname 时不用回表读整行
        conn.execute('create index idx_item_dname on item_panel(item_name, item_meta, dname)')
        conn.commit()
    n = conn.execute(f'select count(*) from {table}').fetchone()[0]
    ok = conn.execute('pragma integrity_check').fetchone()[0]
    conn.close()
    print(f'{os.path.basename(path):14s} {n:6d} 行  {os.path.getsize(path) // 1024:>7d}KB  integrity={ok}')


def main():
    src_db = os.path.join(APP, 'assets', 'itempanel.db')
    out_dir = os.path.join(APP, 'assets')
    for i, a in enumerate(sys.argv):
        if a == '--src':
            src_db = sys.argv[i + 1]
        elif a == '--out':
            out_dir = sys.argv[i + 1]
    os.makedirs(out_dir, exist_ok=True)

    print(f'源库 {src_db}（{os.path.getsize(src_db) // 1024 // 1024}MB）')

    # ---- items.db ----
    src = sqlite3.connect(src_db)
    rows = list(src.execute('select item_name, item_id, item_meta, has_nbt, dname, icon from item_panel'))
    make_db(os.path.join(out_dir, 'items.db'),
            'create table item_panel (id integer primary key autoincrement, item_name text, item_id integer, '
            'item_meta integer, has_nbt integer, dname text, icon blob)',
            [(n, i, m, h, d, ic) for n, i, m, h, d, ic in rows], 'item_panel',
            'item_name,item_id,item_meta,has_nbt,dname,icon')
    src.close()

    # ---- fluids.db ----
    src = sqlite3.connect(src_db)
    containers = list(src.execute(
        'select fluid_name, item, meta, container_display_name, amount from fluid_container'))
    src.close()
    names = read_ts_fluid_names(os.path.join(APP, 'src', 'fluidNames.ts'))
    fluid_rows = [(f, cn) for f, cn in sorted(names.items())]
    if os.path.exists(os.path.join(out_dir, 'fluids.db')):
        os.remove(os.path.join(out_dir, 'fluids.db'))
    conn = sqlite3.connect(os.path.join(out_dir, 'fluids.db'))
    conn.execute('PRAGMA synchronous=OFF')
    conn.execute('create table fluid_container (id integer primary key autoincrement, fluid_name text, '
                 'item text, meta text, container_display_name text, amount integer)')
    conn.execute('create table fluid_name (fluid text primary key, dname text)')
    conn.executemany('insert into fluid_container (fluid_name,item,meta,container_display_name,amount) '
                     'values (?,?,?,?,?)', containers)
    conn.executemany('insert into fluid_name (fluid,dname) values (?,?)', fluid_rows)
    conn.commit()
    print(f'{"fluids.db":14s} {len(containers):6d} 行容器 + {len(fluid_rows)} 个名字  '
          f'{os.path.getsize(os.path.join(out_dir, "fluids.db")) // 1024:>7d}KB  '
          f'integrity={conn.execute("pragma integrity_check").fetchone()[0]}')
    conn.close()

    # ---- essentia.db ----
    aspects = read_ts_aspects(os.path.join(APP, 'src', 'aspects.ts'))
    import base64
    aspect_rows = [(tag, cn, base64.b64decode(b64)) for tag, (cn, b64) in sorted(aspects.items())]
    make_db(os.path.join(out_dir, 'essentia.db'),
            'create table aspect (tag text primary key, dname text, icon blob)',
            aspect_rows, 'aspect', 'tag,dname,icon')


if __name__ == '__main__':
    main()
