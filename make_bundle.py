# -*- coding: utf-8 -*-
"""生成「配置包」zip：玩家导入后一次拿到服务器地址 + 线路列表 + 图标源。

用法（在 AEMobileIcoOutput 目录下）：
    python make_bundle.py --ip mc.example.com --icon-source https://cdn.example.com/ae/version.json --out dist
    python make_bundle.py --from-server-list servers.json --out dist

产物：<out>/aemobile-config.zip
    config.json    默认服务器 + 图标源 + 服务器列表源
    servers.json   线路列表（可选）
    README.txt     给玩家的说明

图标库**不放进 zip**（186MB，而且是各模组的艺术作品）：
config 里的 iconSource 指向在线更新源，App 导入后自己「检查更新」下载。
"""
import argparse
import io
import json
import os
import zipfile

README = """AEMobile 配置包
================

用法：
1. 装好 AEMobile，第一次打开会停在「首次使用」页
2. 点「选择配置文件（.zip）」，选这个压缩包
3. 导入后点「下载图标库」（第一次约 186MB，之后只下变化的部分）

包里包含：服务器地址、线路列表、图标库更新源。
导入后这些都能在 App 的「设置」里改。
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ip', default='', help='默认服务器地址')
    ap.add_argument('--port', default='44444')
    ap.add_argument('--token', default='', help='预置 token（一般留空，玩家自己粘）')
    ap.add_argument('--name', default='', help='服务器显示名')
    ap.add_argument('--icon-source', default='', help='图标库 version.json 的直链')
    ap.add_argument('--server-list', default='', help='服务器列表 servers.json 的直链')
    ap.add_argument('--from-server-list', default='', help='把本地的 servers.json 一起打进包里')
    ap.add_argument('--out', default='dist', help='输出目录')
    ap.add_argument('--filename', default='aemobile-config.zip')
    args = ap.parse_args()

    config = {
        'name': args.name or args.ip,
        'ip': args.ip,
        'port': args.port,
        'token': args.token,
        'iconSource': args.icon_source,
        'serverList': args.server_list,
    }

    servers = None
    if args.from_server_list:
        with io.open(args.from_server_list, encoding='utf-8') as f:
            servers = json.load(f)
        if not isinstance(servers, list):
            raise SystemExit('servers.json 应该是一个数组')

    os.makedirs(args.out, exist_ok=True)
    out_path = os.path.join(args.out, args.filename)
    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('config.json', json.dumps(config, ensure_ascii=False, indent=2))
        if servers:
            z.writestr('servers.json', json.dumps(servers, ensure_ascii=False, indent=2))
        z.writestr('README.txt', README)

    print('已生成 %s（%.1f KB）' % (out_path, os.path.getsize(out_path) / 1024))
    print('  默认服务器: %s' % (args.ip or '(未填)'))
    print('  图标源:     %s' % (args.icon_source or '(未填)'))
    print('  线路数:     %d' % (len(servers) if servers else 0))


if __name__ == '__main__':
    main()
