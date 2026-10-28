# -*- coding: utf-8 -*-
"""把 GTNH 的 GregTech 汉化文件刷进 assets/fluids.db 的 fluid_name 表（流体中文名）。

用法：python tools/build_fluid_names.py <GregTech_zh_CN.lang> [fluids.db 路径]

- `fluid_name(fluid, dname)`：fluid 是去掉 molten./plasma./liquid. 前缀的材料名（小写）
- `fluid_container` 表（流体→容器物品）来自 NEI 的 fluidcontainer 导出，这个脚本不动它
"""
import io
import re
import sqlite3
import sys


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    src_path = sys.argv[1]
    db_path = sys.argv[2] if len(sys.argv) > 2 else 'AEMobileApp/assets/fluids.db'

    src = io.open(src_path, encoding='utf-8').read()
    names = {}
    for line in src.splitlines():
        line = line.strip()
        if not line.startswith('S:'):
            continue
        m = re.match(r'S:(?:"([^"]+)"|([^=]+))=(.*)$', line)
        if not m:
            continue
        key = (m.group(1) or m.group(2)).strip()
        val = m.group(3).strip()
        if key.endswith('.ChemicalFormula') or not key.startswith('Material.'):
            continue
        names[key[len('Material.'):].lower()] = val

    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA synchronous=OFF')
    conn.execute('create table if not exists fluid_name (fluid text primary key, dname text)')
    conn.execute('delete from fluid_name')
    conn.executemany('insert into fluid_name (fluid, dname) values (?,?)', sorted(names.items()))
    conn.commit()
    n = conn.execute('select count(*) from fluid_name').fetchone()[0]
    containers = conn.execute('select count(*) from fluid_container').fetchone()[0]
    conn.close()
    print(f'fluid_name {n} 条，fluid_container {containers} 条 → {db_path}')


if __name__ == '__main__':
    main()
