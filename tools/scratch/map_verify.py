#!/usr/bin/env python3
"""map_verify.py —— 地图数据格式的**统计验证**（佐证，主证是 rich4.exe 机器码）

用法：
    python3 tools/scratch/map_verify.py [../extracted/map 或 ../Rich4/map.mkf]

做三件事：
 1) 直接读 `Rich4/map.mkf`，按 exe 的 MKF 表结构取出 8 张地图结构数据
    （资源号 2*gm+1），并与 `extracted/map/*.bin` 逐字节比对（判断解包是否忠实）。
 2) 按 40 字节头 + 5 张表（步长 0x28/0x34/0x38/0x34/0x1c）解析，
    核对**每个表的实际条数 == count+1**（1 基索引的实测证据）。
 3) 统计名字长度、type 基数与表名匹配率、flags 低字节分布、decorIndex 分布等。

结论只作**佐证**；与机器码冲突时以机器码为准（见 docs/systems/map-format.md）。
"""
from __future__ import annotations

import os
import struct
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MKF = os.path.join(ROOT, "..", "Rich4", "map.mkf")
EXTRACT = os.path.join(ROOT, "..", "extracted", "map")

STRIDE = {"node": 0x28, "land": 0x34, "facility": 0x38, "commercial": 0x34, "landscape": 0x1C}
HEADER_FIELDS = [
    "num_map_nodes", "node_table_offset",
    "num_lands", "land_table_offset",
    "num_facilities", "facility_table_offset",
    "num_commercials", "commercial_table_offset",
    "num_landscapes", "landscape_table_offset",
]


def mkf_table(path: str):
    """重现 exe 的 MKF 读取：dword0 = 索引表文件偏移；表项 = 资源数据偏移（绝对）。"""
    blob = open(path, "rb").read()
    tbl_off = struct.unpack_from("<I", blob, 0)[0]
    n = (len(blob) - tbl_off) // 4
    tbl = list(struct.unpack_from("<%dI" % n, blob, tbl_off))
    return blob, tbl


def mkf_entry(blob, tbl, idx):
    off = tbl[idx]
    d0, d1, c, e = struct.unpack_from("<4I", blob, off)
    payload = blob[off + 16:off + 16 + d0]
    return dict(off=off, size=d0, stored=d1, meta=c, extra=e, payload=payload)


def decode(raw: bytes) -> str:
    raw = raw.split(b"\0")[0]
    for enc in ("big5", "cp950", "big5hkscs"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return "<非Big5:%s>" % raw.hex()


def name_len(raw: bytes) -> int:
    return len(raw.split(b"\0")[0])


def parse_map(data: bytes):
    h = struct.unpack_from("<10I", data, 0)
    out = dict(zip(HEADER_FIELDS, h))
    tables = {}
    for key, cnt_idx, off_idx in (
        ("node", 0, 1),
        ("land", 2, 3),
        ("facility", 4, 5),
        ("commercial", 6, 7),
        ("landscape", 8, 9),
    ):
        tables[key] = (data[h[off_idx]:], h[cnt_idx])
    return out, tables


def main(argv):
    src = argv[1] if len(argv) > 1 else EXTRACT
    blob, tbl = mkf_table(MKF)
    print("# 地图数据格式统计验证  (MAP.MKF=%s)" % os.path.relpath(MKF, ROOT))
    print("# 资源总数 = %d" % len(tbl))
    print()

    all_nodes = []
    all_type_hits = Counter()
    hdr_ok = True
    for gm in range(8):
        res = gm * 2 + 1
        ent = mkf_entry(blob, tbl, res)
        # 与既有解包文件比对（判断 extracted/map/*.bin 是否忠实）
        ext_path = os.path.join(EXTRACT, "%04d.bin" % res)
        faithful = None
        if os.path.exists(ext_path):
            ext = open(ext_path, "rb").read()
            faithful = ext == ent["payload"]
        data = ent["payload"]
        hdict, tables = parse_map(data)
        h = struct.unpack_from("<10I", data, 0)   # 10 个 uint32，按顺序

        print("## global_map_id=%d  资源 MAP.MKF[%d]  d0=%d d1=%d  extracted 忠实=%s"
              % (gm, res, ent["size"], ent["stored"], faithful))
        print("   头部: num_map_nodes=%d node_off=%#x num_lands=%d land_off=%#x "
              "num_fac=%d fac_off=%#x num_com=%d com_off=%#x num_lsc=%d lsc_off=%#x"
              % h)
        # 每张表实际条数 == count+1 ？
        spans = {}
        order = ["node", "land", "facility", "commercial", "landscape"]
        bases = {k: h[2 * i + 1] for i, k in enumerate(order)}
        for i, k in enumerate(order):
            start = bases[k]
            end = bases[order[i + 1]] if i + 1 < len(order) else len(data)
            span = (end - start) // STRIDE[k]
            cnt = h[2 * i]
            ok = "OK" if span == cnt + 1 else "**MISMATCH**"
            print("   %-11s count=%4d  实测条数=%4d  (=count+1 %s)  off=%#07x size=%#x"
                  % (k, cnt, span, ok, start, STRIDE[k]))
            if span != cnt + 1:
                hdr_ok = False
        calc = h[9] + (h[8] + 1) * 0x1C
        print("   map_data_size 公式 lso+(nls+1)*0x1c = %d ; 文件长度 = %d ; %s"
              % (calc, len(data), "OK" if calc == len(data) else "**MISMATCH**"))
        if calc != len(data):
            hdr_ok = False

        # 节点表逐项统计
        nb, nn = tables["node"]
        for i in range(1, nn + 1):
            p = i * STRIDE["node"]
            x, y = struct.unpack_from("<2h", nb, p)
            raw = nb[p + 4:p + 0x18]
            adj = struct.unpack_from("<4H", nb, p + 0x18)
            typ, dec = struct.unpack_from("<2H", nb, p + 0x20)
            flags = struct.unpack_from("<I", nb, p + 0x24)[0]
            all_nodes.append(dict(gm=gm, i=i, x=x, y=y, raw=raw, name=decode(raw),
                                  nlen=name_len(raw), adj=adj, type=typ, dec=dec, flags=flags))
        print()
    print("=" * 78)
    print("## 汇总")
    print("全部地图的表条数/长度校验: %s" % ("全部 OK" if hdr_ok else "**有 MISMATCH**"))
    print("节点总数 = %d" % len(all_nodes))

    # --- type 基数 vs 各表名字 ---
    print()
    print("## type 基数 → 表名匹配（节点 +0x20 == 基数 + i 时，节点名与第 i 项名字比对）")
    tot = Counter()
    for gm in range(8):
        res = gm * 2 + 1
        data = mkf_entry(blob, tbl, res)["payload"]
        h, tables = struct.unpack_from("<10I", data, 0), parse_map(data)[1]
        groups = {
            0x7D0: ("land", tables["land"]),
            0x0FA0: ("facility", tables["facility"]),
            0x1770: ("commercial", tables["commercial"]),
            0x1F40: ("landscape", tables["landscape"]),
        }
        for nd in [n for n in all_nodes if n["gm"] == gm]:
            for base, (tname, (tb, cnt)) in groups.items():
                idx = nd["type"] - base
                if not (1 <= idx <= cnt):
                    continue
                raw = tb[idx * STRIDE[tname] + 4: idx * STRIDE[tname] + 0x18]
                tbl_name = decode(raw)
                tot[(tname, "match" if tbl_name == nd["name"] else "differ")] += 1
    for (t, k), v in sorted(tot.items()):
        print("   %-11s %-7s %4d" % (t, k, v))

    # --- 名字长度分布 ---
    print()
    print("## 节点名长度（Big5 字节数，不含 NUL）分布")
    c = Counter(n["nlen"] for n in all_nodes)
    print("   " + "  ".join("%d:%d" % (k, c[k]) for k in sorted(c)))
    print("   空名节点 = %d / %d" % (c.get(0, 0), len(all_nodes)))
    print("   最大长度 = %d" % max(c))

    # --- flags 低字节 / decorIndex ---
    print()
    print("## 节点 flags（+0x24）低字节分布")
    c = Counter(n["flags"] & 0xFF for n in all_nodes)
    print("   " + "  ".join("%d:%d" % (k, c[k]) for k in sorted(c)))
    print("## flags 高位（bits8-31）分布")
    c = Counter(n["flags"] >> 8 for n in all_nodes)
    print("   " + "  ".join("%#x:%d" % (k, c[k]) for k in sorted(c)))
    nonadj = sum(1 for n in all_nodes if n["adj"] == (0, 0, 0, 0))
    print("## adjacent 四个 u16 全 0 的节点数 = %d / %d" % (nonadj, len(all_nodes)))
    mx = max(max(n["adj"]) for n in all_nodes)
    print("## adjacent 最大值 = %d（应 <= num_map_nodes=%d）" % (mx, max(
        mkf_entry(blob, tbl, gm * 2 + 1)["payload"][0] for gm in range(8))))
    print("## decorIndex（+0x22）：0 的节点数 = %d，非 0 范围 %d..%d"
          % (sum(1 for n in all_nodes if n["dec"] == 0),
             min(n["dec"] for n in all_nodes), max(n["dec"] for n in all_nodes)))
    print()
    print("## 各图节点/住宅/设施/企业/景观（与 remake 文档 §6 表对照）")
    for gm in range(8):
        hh = struct.unpack_from("<10I", mkf_entry(blob, tbl, gm * 2 + 1)["payload"], 0)
        print("   gm=%d  nodes=%3d lands=%3d facils=%2d comms=%2d landsc=%3d"
              % (gm, hh[0], hh[2], hh[4], hh[6], hh[8]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
