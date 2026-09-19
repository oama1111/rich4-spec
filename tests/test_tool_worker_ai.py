#!/usr/bin/env python3
"""
通道 2 差分测试 · 道具 9 機器工人 的 AI 判定（`0x00421BA6`，272 字节）

复刻侧对应 `rich4-remake/packages/core/src/ai/tool-policy.ts` 的 `gongren`
（@source 0x00421ba6）。本函数**没有 `call` 调用者**（AI 出道具跳表 `0x47539c`
的 entry 39 成员），建图工具不收 ⇒ 用
`rich4-remake/tools/disasm.py va 0x00421ba6 110` 按需反汇编。

## 语义（全文 84 条指令 / 272 字节，`0x421ba6`..`0x421cb5`）

```
0x421ba6():
    best = 0                              ; [esp] 局部量
    edx = 0
    n = 0x40a45c(-1)                      ; 填「可見實體表」0x48b8c4，返回项数
    for (i = 0; i < n; i++):              ; 0x421bc2 循环头
        v = word [0x48b8c4 + i*2]         ; 0x421bca（and edx,0xffff）
        if (0x7d0 < v < 0xfa0):           ; 0x421bd8 jle / 0x421be0 jge —— **两端都开**
            land = [0x498e84] + (v-0x7d0)*0x34
            if (byte[land+0x19] != [0x49910c]+1) continue   ; ★ 只认「我的」= 当前玩家+1
            if (byte[land+0x18] != 0) continue              ; ★ 住宅（type==0）
            cand = word [land + 0x20 + level*2]             ; rentByLevel[level]
            if (best >= cand) continue                      ; ★ 严格 >（并列保留先出现者）
            if (level >= 5) continue                        ; ★ 住宅上限**写死 5**
            best = cand
        elif (0xfa0 < v < 0x1770):        ; 0x421c38 jle / 0x421c40 jge —— 企业 0x1770+ 不收
            fac = [0x498e88] + (v-0xfa0)*0x38
            if (byte[fac+0x19] != [0x49910c]+1) continue
            if (level >= byte[type + 0x474940]) continue     ; ★ 設施上限**按类别查表**
            cand = word [fac + 0x24 + level*2]               ; rateByLevel[level]
            if (best >= cand) continue                       ; ★ 严格 >
            best = cand
        else: continue
        dword [0x48be64] = v              ; 0x421c94 —— 出口是**實體格值**，不是节点 id
    return best != 0                      ; 0x421ca0 test ecx,ecx / setne-ish
```

★ 三条容易写错、本测试专门钉住的点：

1. **值域是开区间**：`v = 0x7d0`（地块 0）与 `v = 0xfa0`（設施 0）**永远选不上**
   （`jle`/`jge` 把两端都推走）；企业 `v >= 0x1770`、玩家标记 `0x80xx` 也全跳过。
2. **两个上限口径不同**：住宅 `cmp byte [land+0x1a], 5 / jae`（**写死 5** = 复刻
   `MAX_LAND_LEVEL`）；設施 `cmp bl, byte [type + 0x474940] / jae`（**按类别查表**
   `0x474940 = [1,5,5,1,5,0,...]` = 复刻 `FACILITY_MAX_LEVEL`）。
3. **取的是两张不同的表**：住宅 `[land + 0x20 + level*2]`（`rentByLevel`，
   复刻 `loaders/map.ts` 同址）；設施 `[fac + 0x24 + level*2]`（`rateByLevel`，
   同址；下标 0 就是 `housePrice` 的别名，照搬寻址）。

★ 出口 `[0x48be64]` 写的是**可见表的字面值**（即 `2000+i` / `4000+i` 实体格值），
**不是**节点 id —— 这是道具参数全局的统一编码（见 `map-format.md` §(3)、
`tool-policy.ts:30`）。本测试因此断言 `param == 实体格值`。
（复刻的 `gongren` 返回 `{kind:'build', nodeId}`，由 `ai/policy.ts:386`
再把节点还原成地块/設施 —— 表示层不同、选中的目标相同，见最终报告。）

## 打桩清单

| VA | 原用途 | 桩 | 为什么可以打桩 |
|---|---|---|---|
| `0x0040a45c` | 填「可見**實體**表」`0x48b8c4`（440×440 格網逐格取非零，行序 = 先 y 後 x；写入的是**格值字**：地块 `2000+i` / 設施 `4000+i` / 企業 `6000+i` / 玩家标记 `0x80xx`），返回项数 | `mov eax,[COUNT_SLOT]; ret`；表内容由 `setup()` 直接把格值序列铺进 `0x48b8c4` | 「畫面 vs 全掃 / 镜头钳位」的视野口径差异 = 已登记的 **D-005**，**不是本测试对象**；本测试要钉的恰恰是**表项编码（格值而非节点 id）如何被消费**，所以只替换「怎么算出视野」，不替换「表里装什么」。原填充器 `0x40a45c` 的地址算术（`0x474938` 格網、`0x1b8` 行宽）已由本次反汇编逐条读过 |
| `0x00456f2d` | CRT `rand()` | 数据槽 + 调用计数 | 本函数**全文不含任何 `call`**（序言后只有一次 `call 0x40a45c`），更不摇随机数；桩留着是为了把「一次都没摇」变成**可断言**的 |

`0x498e84`（地块表基址）/ `0x498e88`（設施表基址）/ `0x49910c`（当前玩家）/
`0x48b8c4`（可见表）由 `setup()` 直接铺 —— 它们是**被测函数的输入**，不是桩。

★ 注意：本函数**完全不读节点表**（`0x498e80`）—— 全文没有该基址的引用。
这也是它与同族 `0x421cb6`（傳送機，读节点表）的结构差别。

跑法：cd rich4-spec && .venv/bin/python tests/test_tool_worker_ai.py
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from emulate import SCRATCH_BASE, Emu  # noqa: E402

try:
    from unicorn import UC_HOOK_CODE
except ImportError:                      # pragma: no cover
    UC_HOOK_CODE = None

# ── 被测函数 ──
GONGREN = 0x421BA6              # 9 機器工人

# ── 打桩 ──
VISIBLE_ENTITIES = 0x40A45C     # 填「可見實體表」0x48b8c4，返回项数
PRNG = 0x456F2D                 # CRT rand()（本函数不用，留着计数）

# ── 全局 / 输入 ──
CUR = 0x49910C                  # 当前玩家（0 基）
LAND_TABLE_PTR = 0x498E84       # dword：地块表基址（元素 i 在 base + i*0x34）
FAC_TABLE_PTR = 0x498E88        # dword：設施表基址（元素 i 在 base + i*0x38）
VIS_LIST = 0x48B8C4             # 可见实体表（word 数组）
TOOL_PARAM = 0x48BE64           # AI 道具参数出口（本函数唯一的输出全局）

FAC_MAX_LEVEL_TABLE = 0x474940  # byte[type]：設施等级上限（= [1,5,5,1,5,0,…]）

LAND_STRIDE, FAC_STRIDE = 0x34, 0x38
L_OWNER = 0x19                  # byte
L_TYPE = 0x18                   # byte（住宅 == 0）
L_LEVEL = 0x1A                  # byte
L_RENT = 0x20                   # word[6]：rentByLevel（+0x20 + level*2）
F_OWNER = 0x19
F_TYPE = 0x18
F_LEVEL = 0x1A
F_RATE = 0x24                   # word[6]：rateByLevel（+0x24 + level*2）

LAND_MARK = 0x7D0               # 2000：地块格值基址
FAC_MARK = 0xFA0                # 4000：設施格值基址
COMM_MARK = 0x1770              # 6000：企業格值基址

MAX_LAND_LEVEL = 5              # 住宅上限（写死）
FAC_CAPS = [1, 5, 5, 1, 5]      # @source 0x474940 —— 待测试里再与 exe 字节互证

SENTINEL = 0x5A5A5A5A
RESULTS = []

# 暂存区（跨 call 保留 ⇒ setup() 里必须自己清表）
LANDS = SCRATCH_BASE + 0x3000
FACS = SCRATCH_BASE + 0x6000
VIS_COUNT_SLOT = SCRATCH_BASE + 0x900
RAND_SLOT = SCRATCH_BASE + 0x904
RAND_CALLS = SCRATCH_BASE + 0x908

LANDS_ZERO = 0x2000             # 覆盖 idx 0..~245
FACS_ZERO = 0x2000              # 覆盖 idx 0..~234


def case(desc, got, want):
    ok = got == want
    RESULTS.append(ok)
    print(f"  {'✅' if ok else '❌'} {desc:<74} 实际 {got!s:<14} 期望 {want!s}")
    return ok


def ref_land(i):
    """地块 i 的实体格值（原版编码：2000 + i）"""
    return LAND_MARK + i


def ref_fac(i):
    return FAC_MARK + i


def reference(me, visible, lands, facs):
    """独立于 unicorn 的参考模型（逐条照 0x421ba6 的汇编次序写）。

    ★ 检查**次序**也照抄：地块支先比值再查上限；設施支先查上限再取值。
      两者都是「两个条件都过才接受」，但次序会影响「越界读」是否发生，
      参考模型里用 `val` 的读取点把这一点也复现出来。
    """
    best = 0
    ref = None
    for v in visible:
        if LAND_MARK < v < FAC_MARK:
            l = lands.get(v - LAND_MARK)
            if l is None:
                continue
            if l["owner"] != me + 1:
                continue
            if l["type"] != 0:
                continue
            val = l["rents"][l["level"]] & 0xFFFF
            if best >= val:
                continue
            if l["level"] >= MAX_LAND_LEVEL:
                continue
            best, ref = val, v
        elif FAC_MARK < v < COMM_MARK:
            f = facs.get(v - FAC_MARK)
            if f is None:
                continue
            if f["owner"] != me + 1:
                continue
            cap = FAC_CAPS[f["type"]] if f["type"] < len(FAC_CAPS) else 0
            if f["level"] >= cap:
                continue
            val = f["rates"][f["level"]] & 0xFFFF
            if best >= val:
                continue
            best, ref = val, v
    return (1 if best != 0 else 0), ref


class World:
    def __init__(self):
        self.emu = Emu()
        # rand()：读数据槽 + 自增调用计数（本函数不摇 ⇒ 恒 0）
        self.emu.patch(PRNG, b"\xA1" + struct.pack("<I", RAND_SLOT)
                       + b"\xFF\x05" + struct.pack("<I", RAND_CALLS) + b"\xC3")
        # 可见实体表填充器：只把「项数」交给 eax；表由 setup() 直接铺
        self.emu.patch(VISIBLE_ENTITIES,
                       b"\xA1" + struct.pack("<I", VIS_COUNT_SLOT) + b"\xC3")
        self.clear()

    # ── 世界构造 ──
    def clear(self):
        self.me = 0
        self.visible = []          # 可见实体表的**格值**序列（顺序 = 遍历顺序）
        self.lands = {}            # idx → dict(owner,type,level,rents[6])
        self.facs = {}             # idx → dict(owner,type,level,rates[6])
        self.rand = 0
        return self

    def see(self, *values):
        self.visible = list(values)
        return self

    def land(self, idx, owner=0, type=0, level=0, rents=None):
        self.lands[idx] = {
            "owner": owner, "type": type, "level": level,
            "rents": list(rents) if rents is not None else [0] * 6,
        }
        return self

    def fac(self, idx, owner=0, type=0, level=0, rates=None):
        self.facs[idx] = {
            "owner": owner, "type": type, "level": level,
            "rates": list(rates) if rates is not None else [0] * 6,
        }
        return self

    # ── 注入 ──
    def _setup(self, emu):
        emu.write32(CUR, self.me)
        emu.write32(LAND_TABLE_PTR, LANDS)
        emu.write32(FAC_TABLE_PTR, FACS)
        emu.write32(TOOL_PARAM, SENTINEL)
        emu.write32(VIS_COUNT_SLOT, len(self.visible))
        emu.write32(RAND_SLOT, self.rand)
        emu.write32(RAND_CALLS, 0)
        # ★ 暂存区跨 call 保留 ⇒ 先整张表清零再写自己的项
        emu.write(LANDS, b"\x00" * LANDS_ZERO)
        emu.write(FACS, b"\x00" * FACS_ZERO)
        emu.write(VIS_LIST, b"\x00" * 0x200)
        if self.visible:
            emu.write(VIS_LIST, b"".join(
                struct.pack("<H", v & 0xFFFF) for v in self.visible))
        for idx, l in self.lands.items():
            b = LANDS + idx * LAND_STRIDE
            emu.write8(b + L_TYPE, l["type"])
            emu.write8(b + L_OWNER, l["owner"])
            emu.write8(b + L_LEVEL, l["level"])
            for lv in range(6):
                emu.write16(b + L_RENT + lv * 2, l["rents"][lv] & 0xFFFF)
        for idx, f in self.facs.items():
            b = FACS + idx * FAC_STRIDE
            emu.write8(b + F_TYPE, f["type"])
            emu.write8(b + F_OWNER, f["owner"])
            emu.write8(b + F_LEVEL, f["level"])
            for lv in range(6):
                emu.write16(b + F_RATE + lv * 2, f["rates"][lv] & 0xFFFF)

    def run(self, func=GONGREN):
        r = self.emu.call(func, [], setup=self._setup)
        self.ret = r["eax"]
        self.param = self.emu.readu32(TOOL_PARAM)
        self.rand_calls = self.emu.readu32(RAND_CALLS)
        return self

    def trace(self, func=GONGREN):
        """跑一次并记录命中过的 EIP —— 用于『确实走了目标分支』的旁证断言。"""
        hits = set()
        h = self.emu.mu.hook_add(UC_HOOK_CODE,
                                 lambda mu, addr, size, user: hits.add(addr))
        try:
            self.run(func)
        finally:
            self.emu.mu.hook_del(h)
        return hits

    def expect(self, desc, ret, param):
        case(desc + " · 返回", self.ret, ret)
        case(desc + " · [0x48be64]", self.param, param)


def main():
    print("差分测试 · 道具 9 機器工人 AI 判定 `0x00421ba6`（272 字节）\n")
    w = World()

    # ═════════ [A] 表项编码互证：0x474940 就是设施上限表 =========
    print("[A] 通道 1 互证：`0x474940` 的字节 == 本测试用的设施上限表")
    raw = w.emu.read(FAC_MAX_LEVEL_TABLE, 8)
    case("exe 的 0x474940 前 8 字节", list(raw), [1, 5, 5, 1, 5, 0, 0, 0])
    case("本测试用的 FAC_CAPS 与 exe 一致", FAC_CAPS, list(raw[:5]))

    # ═════════ [B] 空表 / 无候选 / 出口不被写 =========
    print("\n[B] 空可见表 ⇒ 不用；出口保持哨兵；一次随机数都不摇")
    w.clear().run()
    case("空表 · 返回 0", w.ret, 0)
    case("空表 · [0x48be64] 保持哨兵", w.param, SENTINEL)
    case("空表 · rand 未消费", w.rand_calls, 0)

    # ═════════ [C] 值域开区间（四个边界都钉） ═════════
    print("\n[C] 值域：0x7d0 < v < 0xfa0 地块 / 0xfa0 < v < 0x1770 設施（**两端都开**）")
    w.clear().land(0, owner=1, type=0, level=0, rents=[9999] * 6).see(LAND_MARK).run()
    w.expect("★ 格值 0x7d0（地块 0）租金 9999 ⇒ 仍不选（jle 把左端推走）", 0, SENTINEL)
    w.clear().land(1, owner=1, type=0, level=0, rents=[9999] * 6).see(LAND_MARK + 1).run()
    w.expect("★ 格值 0x7d1（地块 1）⇒ 选", 1, LAND_MARK + 1)

    w.clear().fac(0, owner=1, type=1, level=0, rates=[9999] * 6).see(FAC_MARK).run()
    w.expect("★ 格值 0xfa0（設施 0）⇒ 不选（jle 把右端推走）", 0, SENTINEL)
    w.clear().fac(1, owner=1, type=1, level=0, rates=[9999] * 6).see(FAC_MARK + 1).run()
    w.expect("★ 格值 0xfa1（設施 1）⇒ 选", 1, FAC_MARK + 1)

    w.clear().land(1, owner=1, type=0, level=0, rents=[9999] * 6)
    w.fac(1, owner=1, type=1, level=0, rates=[9999] * 6)
    w.see(0x800, 0x7D0, 0xFA0, COMM_MARK, COMM_MARK + 1, 0x8001, 0xFFFF, 0).run()
    w.expect("★ 0x800 / 0x7d0 / 0xfa0 / 0x1770 / 0x1771 / 0x80xx / 0xffff / 0 全不收", 0, SENTINEL)

    w.clear().fac(96, owner=1, type=1, level=0, rates=[777] * 6).see(0x1000).run()
    w.expect("★ 格值 0x1000 = 設施 96（设施步长 0x38 的大下标）⇒ 选", 1, 0x1000)

    # ═════════ [D] 归属过滤：只认「当前玩家 + 1」 ═════════
    print("\n[D] 归属：owner == [0x49910c] + 1（1 基），无主/别人/换玩家都翻结论")
    for me, owner, want, tag in [
        (0, 0, 0, "无主（owner=0）"),
        (0, 2, 0, "别人（owner=2, 我=0）"),
        (0, 1, 1, "我的（owner=1, 我=0）"),
        (2, 3, 1, "★ 换玩家：我=2、owner=3 ⇒ 我的"),
        (2, 1, 0, "★ 我=2、owner=1 ⇒ 不是我的"),
        (3, 4, 1, "我=3、owner=4 ⇒ 我的"),
    ]:
        w.clear().me = me
        w.land(1, owner=owner, type=0, level=1, rents=[0, 500, 0, 0, 0, 0])
        w.see(ref_land(1)).run()
        w.expect(f"{tag} me={me} owner={owner}", want,
                  ref_land(1) if want else SENTINEL)

    w.clear().me = 0
    w.land(1, owner=1, type=0, level=1, rents=[0, 500, 0, 0, 0, 0])
    w.see(ref_land(1)).run()
    case("同一张表，我=0 时选中", w.ret, 1)
    w.clear().me = 1
    w.land(1, owner=1, type=0, level=1, rents=[0, 500, 0, 0, 0, 0])
    w.see(ref_land(1)).run()
    case("★ 同一张表，切到 我=1 ⇒ 同一块地变「不是我的」", w.ret, 0)

    # ═════════ [E] 地块类型必须 == 0（住宅） ═════════
    print("\n[E] 地块：`byte[+0x18] == 0`（住宅）才收")
    for type_, want, tag in [(0, 1, "住宅 0"), (1, 0, "連鎖店 1"), (2, 0, "类型 2"),
                             (0xFF, 0, "类型 255")]:
        w.clear().land(1, owner=1, type=type_, level=2, rents=[0, 0, 800, 0, 0, 0])
        w.see(ref_land(1)).run()
        w.expect(f"地块类型 {tag}", want, ref_land(1) if want else SENTINEL)

    # ═════════ [F] 住宅等级上限**写死 5** ═════════
    print("\n[F] 住宅：`cmp byte[+0x1a], 5 / jae` ⇒ level >= 5 跳过（与設施查表不同）")
    for level, want, tag in [(0, 1, "level 0"), (1, 1, "level 1"), (3, 1, "level 3"),
                             (4, 1, "level 4"), (5, 0, "★ level 5（上限）")]:
        rents = [0] * 6
        rents[level] = 9999
        w.clear().land(1, owner=1, type=0, level=level, rents=rents)
        w.see(ref_land(1)).run()
        w.expect(f"住宅 {tag}、rents[{level}]=9999", want,
                  ref_land(1) if want else SENTINEL)

    w.clear()
    w.land(1, owner=1, type=0, level=4, rents=[0, 0, 0, 0, 500, 0])
    w.land(2, owner=1, type=0, level=5, rents=[0, 0, 0, 0, 0, 9999])
    w.see(ref_land(1), ref_land(2)).run()
    w.expect("★ 同场：level4 值 500 vs level5 值 9999 ⇒ 取 level4（5 级被上限挡掉）",
             1, ref_land(1))

    # ═════════ [G] 住宅取值 = rentByLevel[level]（+0x20 + level*2） ═════════
    print("\n[G] 住宅取值取的是 `rentByLevel`（+0x20），不是地价(+0x1c)/房价(+0x1e)")
    w.clear()
    # 等级不是单调：level 2 的租金 > level 4 的租金 ⇒ 应按**当前等级**的租金取
    w.land(1, owner=1, type=0, level=2, rents=[0, 0, 800, 0, 300, 0])
    w.land(2, owner=1, type=0, level=4, rents=[0, 0, 0, 0, 300, 0])
    w.see(ref_land(1), ref_land(2)).run()
    w.expect("★ 非单调租金表：按当前等级查表 ⇒ level2(800) 赢 level4(300)",
             1, ref_land(1))

    w.clear()
    w.land(1, owner=1, type=0, level=1, rents=[0, 0, 0, 0, 0, 0])
    w.see(ref_land(1)).run()
    w.expect("★ rents[level] == 0 ⇒ 选不上（严格 > 0；best 初值 0）", 0, SENTINEL)

    w.clear()
    w.land(1, owner=1, type=0, level=3, rents=[0, 0, 0, 0, 0, 0])
    w.see(ref_land(1), ref_land(1)).run()
    w.expect("重复项全是 0 ⇒ 仍不用", 0, SENTINEL)

    # 地价/房价字段极大但不参与 —— 直接往 +0x1c/+0x1e 写 0xffff
    w.clear()
    w.land(1, owner=1, type=0, level=1, rents=[0, 100, 0, 0, 0, 0])
    w.land(2, owner=1, type=0, level=1, rents=[0, 200, 0, 0, 0, 0])
    w.see(ref_land(1), ref_land(2))
    b1 = LANDS + 1 * LAND_STRIDE
    b2 = LANDS + 2 * LAND_STRIDE
    old_setup = w._setup

    def setup_extra(emu, _old=old_setup):
        _old(emu)
        emu.write16(b1 + 0x1C, 0xFFFF)   # 地块 1 的地价
        emu.write16(b1 + 0x1E, 0xFFFF)   # 地块 1 的房价
        emu.write16(b2 + 0x1C, 0)
        emu.write16(b2 + 0x1E, 0)

    r = w.emu.call(GONGREN, [], setup=setup_extra)
    w.ret, w.param = r["eax"], w.emu.readu32(TOOL_PARAM)
    w.expect("★ 地价/房价(+0x1c/+0x1e) 绝不参与 ⇒ 仍按 rentByLevel 选地块 2",
             1, ref_land(2))

    # ═════════ [H] 設施等级上限按类别查表 0x474940 ═════════
    print("\n[H] 設施：`cmp byte[+0x1a], byte[type+0x474940] / jae`（表 = [1,5,5,1,5]）")
    for type_, cap in enumerate(FAC_CAPS):
        for level in range(0, 6):
            want = 1 if level < cap else 0
            rates = [0] * 6
            rates[level] = 5000
            w.clear().fac(1, owner=1, type=type_, level=level, rates=rates)
            w.see(ref_fac(1)).run()
            w.expect(f"設施 type={type_}(上限{cap}) level={level}",
                     want, ref_fac(1) if want else SENTINEL)
    for type_, tag in [(5, "表外 type 5（上限 0）"), (6, "表外 type 6（上限 0）"),
                       (7, "表外 type 7（上限 0）")]:
        w.clear().fac(1, owner=1, type=type_, level=0, rates=[5000] * 6)
        w.see(ref_fac(1)).run()
        w.expect(f"★ {tag}：连 level 0 也选不上", 0, SENTINEL)

    # ★ type > 4 是**表外**：原版 `movzx edi, byte[+0x18]` → `byte[edi + 0x474940]`
    #   会读到 0x474940 之后的**紧邻 DGROUP 数据**（无边界检查，也不可能有：
    #   游戏里 type 只能是 0..4）。type 255 恰好读到 0xFF ⇒ 上限 255。
    case("exe 在 0x474940+255 处的字节（表外读到的上限）",
         w.emu.read8(FAC_MAX_LEVEL_TABLE + 0xFF), 0xFF)
    w.clear().fac(1, owner=1, type=0xFF, level=0, rates=[5000] * 6)
    w.see(ref_fac(1)).run()
    w.expect("★ 表外 type 255 读到上限 0xFF ⇒ level 0 **收**（如实记录越界读，非实机可达）",
             1, ref_fac(1))
    w.clear().fac(1, owner=1, type=16, level=0, rates=[5000] * 6)
    w.see(ref_fac(1)).run()
    w.expect("表外 type 16 读到上限 0 ⇒ 不收", 0, SENTINEL)

    # ═════════ [I] 設施取值 = rateByLevel[level]（+0x24 + level*2） ═════════
    print("\n[I] 設施取值取的是 `rateByLevel`（+0x24），不是地价(+0x22)/房价(+0x24 别名)")
    w.clear()
    w.fac(1, owner=1, type=1, level=1, rates=[0, 900, 0, 0, 0, 0])
    w.fac(2, owner=1, type=1, level=3, rates=[0, 0, 0, 400, 0, 0])
    w.see(ref_fac(1), ref_fac(2)).run()
    w.expect("★ 非单调费率表：按当前等级查表 ⇒ level1(900) 赢 level3(400)",
             1, ref_fac(1))

    w.clear().fac(1, owner=1, type=1, level=0, rates=[0] * 6).see(ref_fac(1)).run()
    w.expect("★ rateByLevel[level] == 0 ⇒ 选不上", 0, SENTINEL)

    w.clear()
    w.fac(1, owner=1, type=2, level=0, rates=[1500] * 6)
    w.fac(2, owner=1, type=2, level=0, rates=[1200] * 6)
    w.see(ref_fac(1), ref_fac(2)).run()
    w.expect("★ 設施下标 0 读到的就是 +0x24（housePrice 别名）⇒ 1500 者赢",
             1, ref_fac(1))

    # ═════════ [J] 跨种类共用同一个 best（ecx），严格 > ⇒ 并列取**可见表先出现**者 ═════════
    print("\n[J] 严格 `>`：并列取可见表里**先出现**者；地块/設施共用同一个 best")
    w.clear()
    w.land(1, owner=1, type=0, level=1, rents=[0, 700, 0, 0, 0, 0])
    w.land(2, owner=1, type=0, level=1, rents=[0, 700, 0, 0, 0, 0])
    w.see(ref_land(1), ref_land(2)).run()
    w.expect("★ 两块同值 700，表序 [1,2] ⇒ 取地块 1", 1, ref_land(1))
    w.clear()
    w.land(1, owner=1, type=0, level=1, rents=[0, 700, 0, 0, 0, 0])
    w.land(2, owner=1, type=0, level=1, rents=[0, 700, 0, 0, 0, 0])
    w.see(ref_land(2), ref_land(1)).run()
    w.expect("★ 同值、表序 [2,1] ⇒ 取地块 2（证明确实是顺序，不是下标）", 1, ref_land(2))

    w.clear()
    w.land(1, owner=1, type=0, level=1, rents=[0, 700, 0, 0, 0, 0])
    w.fac(1, owner=1, type=1, level=0, rates=[700] * 6)
    w.see(ref_land(1), ref_fac(1)).run()
    w.expect("★ 地/設施同值 700，表序 [地,設] ⇒ 取地块", 1, ref_land(1))
    w.clear()
    w.land(1, owner=1, type=0, level=1, rents=[0, 700, 0, 0, 0, 0])
    w.fac(1, owner=1, type=1, level=0, rates=[700] * 6)
    w.see(ref_fac(1), ref_land(1)).run()
    w.expect("★ 同值 700，表序 [設,地] ⇒ 取設施", 1, ref_fac(1))

    w.clear()
    w.land(1, owner=1, type=0, level=1, rents=[0, 700, 0, 0, 0, 0])
    w.land(2, owner=1, type=0, level=1, rents=[0, 700, 0, 0, 0, 0])
    w.land(3, owner=1, type=0, level=1, rents=[0, 700, 0, 0, 0, 0])
    w.see(ref_land(3), ref_land(1), ref_land(2)).run()
    w.expect("★ 三块并列，表序 [3,1,2] ⇒ 取地块 3", 1, ref_land(3))

    print("  ── 跨种类共用 best：值与种类无关，值大者赢 ──")
    for first, second, want_first, tag in [
        (("land", 500), ("fac", 400), True, "地500 在前、設400 在后"),
        (("land", 400), ("fac", 500), False, "地400 在前、設500 在后"),
        (("fac", 500), ("land", 400), True, "設500 在前、地400 在后"),
        (("fac", 400), ("land", 500), False, "設400 在前、地500 在后"),
    ]:
        w.clear()
        vals = {}
        for kind, val in (first, second):
            if kind == "land":
                w.land(1, owner=1, type=0, level=1, rents=[0, val, 0, 0, 0, 0])
                vals["land"] = ref_land(1)
            else:
                w.fac(1, owner=1, type=1, level=0, rates=[val] * 6)
                vals["fac"] = ref_fac(1)
        w.see(vals["land"], vals["fac"]).run()
        winner = vals[first[0]] if want_first else vals[second[0]]
        w.expect(f"★ {tag} ⇒ 值大者", 1, winner)

    # ═════════ [K] 步长 / 大下标（地块 0x34、設施 0x38） ═════════
    print("\n[K] 表步长：地块 0x34、設施 0x38（用大下标把步长误差暴露出来）")
    w.clear().land(7, owner=1, type=0, level=2, rents=[0, 0, 1234, 0, 0, 0])
    w.see(ref_land(7)).run()
    w.expect("地块 idx 7（0x7d7）", 1, ref_land(7))
    w.clear().fac(5, owner=1, type=1, level=1, rates=[0, 4321, 0, 0, 0, 0])
    w.see(ref_fac(5)).run()
    w.expect("設施 idx 5（0xfa5）", 1, ref_fac(5))
    w.clear().fac(10, owner=1, type=2, level=0, rates=[2468] * 6)
    w.see(ref_fac(10)).run()
    w.expect("設施 idx 10（0xfaa）", 1, ref_fac(10))

    # ═════════ [L] 返回值 / 出口语义 ═════════
    print("\n[L] 返回值恒 0/1（不是金额）；出口只在**接受**时被写")
    w.clear().land(1, owner=1, type=0, level=1, rents=[0, 2800, 0, 0, 0, 0])
    w.see(ref_land(1)).run()
    w.expect("★ 选中值 2800 ⇒ 返回恰为 1（不是 2800）、出口 = 格值", 1, ref_land(1))
    w.clear().fac(2, owner=1, type=4, level=1, rates=[0, 6000, 0, 0, 0, 0])
    w.see(ref_fac(2)).run()
    w.expect("★ 选中值 6000 ⇒ 返回恰为 1", 1, ref_fac(2))

    w.clear()
    w.land(1, owner=1, type=0, level=1, rents=[0, 900, 0, 0, 0, 0])
    w.land(2, owner=1, type=0, level=1, rents=[0, 100, 0, 0, 0, 0])
    w.see(ref_land(1), ref_land(2)).run()
    w.expect("★ 先好后差：出口停在先出现的更优者（不会被后来的差者覆盖）",
             1, ref_land(1))

    w.clear()
    w.land(1, owner=2, type=0, level=1, rents=[0, 900, 0, 0, 0, 0])
    w.land(2, owner=1, type=0, level=1, rents=[0, 100, 0, 0, 0, 0])
    w.see(ref_land(1), ref_land(2)).run()
    w.expect("★ 别人的地在前（900）不写出口 ⇒ 出口 = 我的地格值", 1, ref_land(2))

    # ═════════ [M] 分支旁证：确实走了目标分支（UC_HOOK_CODE） ═════════
    print("\n[M] 分支旁证（UC_HOOK_CODE）：目标分支**真的被执行**过")
    LAND_BODY = 0x421BE8      # 地块支体
    FAC_CHECK = 0x421C38      # 設施支判定入口
    FAC_BODY = 0x421C48       # 設施支体
    ACCEPT = 0x421C94         # 接受（写出口）
    RET1 = 0x421CA4           # mov [esp],1
    RET0 = 0x421CAB           # mov eax,[esp] 的回落点（ecx==0）

    hits = w.clear().land(1, owner=1, type=0, level=1,
                          rents=[0, 900, 0, 0, 0, 0]).see(ref_land(1)).trace()
    case("地块支体 0x421be8 命中", LAND_BODY in hits, True)
    case("設施支体 0x421c48 **未**命中", FAC_BODY in hits, False)
    case("接受支 0x421c94 命中", ACCEPT in hits, True)
    case("返回 1 的 0x421ca4 命中", RET1 in hits, True)

    hits = w.clear().fac(1, owner=1, type=1, level=1,
                         rates=[0, 900, 0, 0, 0, 0]).see(ref_fac(1)).trace()
    case("設施支判定 0x421c38 命中", FAC_CHECK in hits, True)
    case("設施支体 0x421c48 命中", FAC_BODY in hits, True)
    case("地块支体 0x421be8 **未**命中", LAND_BODY in hits, False)
    case("接受支 0x421c94 命中", ACCEPT in hits, True)

    hits = w.clear().land(1, owner=9, type=0, level=1,
                          rents=[0, 900, 0, 0, 0, 0]).see(ref_land(1)).trace()
    case("别人的地：走了地块支体", LAND_BODY in hits, True)
    case("★ 但接受支 0x421c94 **未**命中", ACCEPT in hits, False)
    case("★ 返回 0 的回落点 0x421cab 命中", RET0 in hits, True)

    hits = w.clear().see(COMM_MARK, 0x8001).trace()
    case("★ 非地非設的项：两条支体都未命中", (LAND_BODY in hits) or (FAC_BODY in hits), False)
    case("★ 空结果仍走到 0x421cab", RET0 in hits, True)

    # ═════════ [N] 随机交叉核对（独立参考模型） ═════════
    print("\n[N] 随机交叉核对（固定种子，独立参考模型逐例比对）")
    import random
    rnd = random.Random(0x421BA6)
    pool_lands = [ref_land(i) for i in range(0, 9)]
    pool_facs = [ref_fac(i) for i in range(0, 9)]
    pool_other = [0x800, LAND_MARK, FAC_MARK, COMM_MARK, COMM_MARK + 3,
                  0x8001, 0xFFFE, 0, 0x1234]
    pool = pool_lands + pool_facs + pool_other
    n_rand = 40
    for t in range(n_rand):
        w.clear()
        w.me = rnd.randrange(0, 4)
        for i in range(0, 9):
            w.land(i, owner=rnd.randrange(0, 5), type=rnd.randrange(0, 4),
                   level=rnd.randrange(0, 6),
                   rents=[rnd.choice([0, 0, 100, 500, 700, 2800, 9999]) for _ in range(6)])
            w.fac(i, owner=rnd.randrange(0, 5), type=rnd.randrange(0, 6),
                  level=rnd.randrange(0, 6),
                  rates=[rnd.choice([0, 0, 300, 400, 600, 1500, 9999]) for _ in range(6)])
        vis = [rnd.choice(pool) for _ in range(rnd.randrange(0, 7))]
        w.see(*vis)
        want_ret, want_ref = reference(w.me, vis, w.lands, w.facs)
        w.run()
        case(f"[{t:02d}] 随机配置 ret（me={w.me} 表={vis}）", w.ret, want_ret)
        case(f"[{t:02d}] 随机配置 出口（期望 {want_ref}）", w.param,
             want_ref if want_ref is not None else SENTINEL)
        case(f"[{t:02d}] rand 未消费", w.rand_calls, 0)

    n_ok = sum(RESULTS)
    print(f"\n{'=' * 82}\n结果：{n_ok}/{len(RESULTS)} 通过")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
