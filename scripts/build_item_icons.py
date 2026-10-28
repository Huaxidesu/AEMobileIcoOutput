# -*- coding: utf-8 -*-
"""把游戏里导出的图标（dumps/aemobile/items）合并进 App 的图标库 itempanel.db。

用法：
    python tools/build_item_icons.py <dumps 目录> [--db <itempanel.db>] [--dry]

<dumps 目录> 就是 `/aemobile dumpicons` 产出的目录（里面有 manifest.jsonl 和 <modid>/*.png）。
- 已有 (item_name, item_meta) 的：只覆盖 icon（和空着的 dname），不动别的行
- 没有的：新增一行
- `--dry` 只统计不写库

导出的图标是「一格里一个物品」的截图，尺寸由导出时的参数决定（默认 128）。
"""
import io
import json
import os
import re
import sqlite3
import sys


def _sanitize(part):
    """和 mod 端 GuiIconDumper.sanitize 保持一致（modid 里可能有 | 之类的字符）"""
    return re.sub(r'[^A-Za-z0-9._-]', '_', part)


def rebuild(dump_dir, db_path, rows, dry):
    """重建整库：老行原样拷，dump 里有的换图标/补名字，dump 里没有的新增。比原地 UPDATE 快一个数量级。"""
    icons = {}
    for r in rows:
        rel = r['file'].replace('/', os.sep)
        png = os.path.join(dump_dir, rel)
        if not os.path.isfile(png):
            parts = rel.split(os.sep)
            parts[0] = _sanitize(parts[0])
            png = os.path.join(dump_dir, *parts)
        if os.path.isfile(png):
            icons[(r['name'], int(r['meta']))] = (io.open(png, 'rb').read(), (r.get('dname') or '').strip())

    tmp_path = db_path + '.new'
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    old = sqlite3.connect(db_path)
    new = sqlite3.connect(tmp_path)
    new.execute('PRAGMA synchronous=OFF')
    new.execute('CREATE TABLE item_panel (id INT, item_name NUM, item_id NUM, item_meta NUM, '
                'has_nbt NUM, dname NUM, icon NUM)')
    # 没索引时每次查 (name, meta) 都要全表扫 180MB，18263 条物品能拖到几十秒
    new.execute('CREATE INDEX idx_item ON item_panel(item_name, item_meta)')
    new.execute('CREATE TABLE fluid_container (id integer primary key, fluid_name string, item string, '
                'meta string, container_display_name string, amount integer)')

    seen = set()
    added = updated = 0
    src = old.execute('select item_name, item_id, item_meta, has_nbt, dname, icon from item_panel')
    batch = []
    for name, item_id, meta, has_nbt, dname, icon in src:
        key = (name, meta)
        seen.add(key)
        hit = icons.get(key)
        if hit is not None:
            icon = hit[0]
            if not dname:
                dname = hit[1]
            updated += 1
        batch.append((name, item_id, meta, has_nbt, dname, icon))
        if len(batch) >= 2000:
            new.executemany('insert into item_panel (item_name,item_id,item_meta,has_nbt,dname,icon) '
                            'values (?,?,?,?,?,?)', batch)
            batch = []
    if batch:
        new.executemany('insert into item_panel (item_name,item_id,item_meta,has_nbt,dname,icon) '
                        'values (?,?,?,?,?,?)', batch)

    extra = [(n, m, i, d) for (n, m), (i, d) in icons.items() if (n, m) not in seen]
    if extra:
        new.executemany('insert into item_panel (item_name,item_id,item_meta,has_nbt,dname,icon) '
                        'values (?,?,?,?,?,?)',
                        [(n, 0, m, 0, d, i) for n, m, i, d in extra])
        added = len(extra)

    new.executemany('insert into fluid_container (id,fluid_name,item,meta,container_display_name,amount) '
                    'values (?,?,?,?,?,?)',
                    old.execute('select id,fluid_name,item,meta,container_display_name,amount from fluid_container'))
    new.commit()
    total = new.execute('select count(*) from item_panel').fetchone()[0]
    ok = new.execute('pragma integrity_check').fetchone()[0]
    new.close()
    old.close()
    if dry:
        os.remove(tmp_path)
        print(f'[dry] 覆盖 {updated} 行，新增 {added} 行，预计 {total} 行（未替换）')
        return
    if ok != 'ok':
        os.remove(tmp_path)
        raise SystemExit(f'新库 integrity_check 失败：{ok}')
    os.replace(tmp_path, db_path)
    print(f'重建完成：覆盖 {updated} 行，新增 {added} 行，库现在 {total} 行 / '
          f'{os.path.getsize(db_path) // 1024 // 1024}MB')


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    dump_dir = sys.argv[1]
    db_path = 'AEMobileApp/assets/itempanel.db'
    dry = '--dry' in sys.argv
    if '--db' in sys.argv:
        db_path = sys.argv[sys.argv.index('--db') + 1]

    manifest = os.path.join(dump_dir, 'manifest.jsonl')
    if not os.path.isfile(manifest):
        print(f'找不到 {manifest}')
        return

    rows = []
    for line in io.open(manifest, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    print(f'清单 {len(rows)} 条，目标库 {db_path}')

    # 几万张图标要么原地 UPDATE（在 110MB 库上非常慢），要么整体重建一个新库再换掉。
    # 这里走重建：按原表顺序流式拷贝，遇到 dump 里有图标的就换成新图，最后原子替换。
    if '--rebuild' in sys.argv:
        rebuild(dump_dir, db_path, rows, dry)
        return

    conn = sqlite3.connect(db_path)
    # 几万次 BLOB 写入，必须显式事务 + 关同步，否则每行一次 fsync 要跑十几分钟
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('BEGIN')
    cur = conn.cursor()
    existing = {(n, m): i for i, n, m in
                cur.execute('select id, item_name, item_meta from item_panel')}

    added = updated = missing_png = 0
    for r in rows:
        name, meta = r['name'], int(r['meta'])
        rel = r['file'].replace('/', os.sep)
        png = os.path.join(dump_dir, rel)
        if not os.path.isfile(png):
            # modid 带 | 之类的字符时，目录名被 sanitize 过，清单里存的是原始名
            parts = rel.split(os.sep)
            parts[0] = _sanitize(parts[0])
            png = os.path.join(dump_dir, *parts)
        if not os.path.isfile(png):
            missing_png += 1
            continue
        blob = io.open(png, 'rb').read()
        dname = (r.get('dname') or '').strip()
        key = (name, meta)
        if key in existing:
            if dry:
                updated += 1
                continue
            cur.execute('update item_panel set icon=? where id=?', (blob, existing[key]))
            if dname:
                cur.execute('update item_panel set dname=? where id=? and (dname is null or dname="")',
                            (dname, existing[key]))
            updated += 1
        else:
            if dry:
                added += 1
                continue
            cur.execute(
                'insert into item_panel (item_name, item_id, item_meta, has_nbt, dname, icon) '
                'values (?,?,?,?,?,?)', (name, 0, meta, 0, dname, blob))
            added += 1

    if not dry:
        conn.commit()
    else:
        conn.rollback()
    total = cur.execute('select count(*) from item_panel').fetchone()[0]
    conn.close()
    print(f'新增 {added} 行，覆盖 {updated} 行，缺 PNG {missing_png} 个'
          + ('（dry-run，未写库）' if dry else f'，库现在 {total} 行'))


if __name__ == '__main__':
    main()
