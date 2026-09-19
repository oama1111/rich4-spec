# 共享简报（AI 用卡判据分析）
真值：/Users/chenke/Documents/kimi/Workspaces/大富翁4重制版/Rich4/rich4.exe (ImageBase 0x400000)
工作目录：/Users/chenke/Documents/kimi/Workspaces/大富翁4重制版/rich4-spec
工具：`python3 .work/dumphand.py x <handlerVA> ...` 输出带注释的线性反汇编（会打印该 handler 的完整函数体，边界由 0x475324 跳表地址排序推出）。
也可用 `python3 .work/r4.py show <va> <endva>` / `python3 .work/r4.py fn <va>`。

## 已知全局（注释里的名字）
- num_players=0x499114, current_player=0x49910c, price_index=0x4990e8
- hand[]=0x499120 (player*15+slot, 值=卡号/道具号, 0=空), deck_cnt[]=0x499198
- aiP0=0x48be58, aiP1=0x48be5c, aiP2=0x48be60, aiP3=0x48be64 （静态暂存池，决策函数写入目标参数，效果函数用 0x41e6f2(index) 读回）
- res_land=0x498e84 (住宅地数组, 步长0x34), com_land=0x498e88 (商业地数组, 步长0x38), map2land=0x498e80 (步长0x28, +0x20=地产id)
- 0x498e98 = 住宅地数量上界（循环上界）, 0x498e7c = 另一张表基址
- g48b8c4 = 全图地块 word 数组（0x40a45c(-1) 返回其长度 0x1b8=440）；word 高位 0x8000=已拥有, 低 4 位=拥有者的位掩码(1<<owner)
- player struct base 0x496b68 stride 0x68; +0x15=type(0=未参加), +0x16=b16, +0x17=個性, +0x1c=cash, +0x20=bank, +0x24=loan, +0x30=points, +0x4c..0x58=hostility[0..3], +0xc=当前地图格(uint16)
- 地产字段（res_land/com_land 项）：+0x18=等级?   +0x19=拥有者(1基, 0=无主), +0x1a=等级/建築等級, +0x1c/+0x1e(住宅) +0x22/+0x24(商业)=地价/建筑数, +4=地名指针
- 0x458370 = strcmp, 0x41970f = ? , 0x456f2d = libc_rand, 0x456f60 = memset, 0x441262 = count_cards(player), 0x4413ad = has_card(player,card,?)
- 0x40d2d3 = find_most_hostile_player(self) → 返回 hostility[self][i] 最大者的下标（严格大于才更新，平手取最小下标；跳过自己与 type==0；无候选返回 -1）
- 0x40a45c(x) = 返回地块表长度/索引相关计数（x=-1 → 0x1b8=440）
- 0x40df69 = update_hostility(a,b,delta)

## 要求
对每个 action N（卡 1..30 / 道具 31..43）给出：
1. handler VA（0x475324[N]）
2. **一行判据摘要**：它在返回非 0（=决定使用）之前测试的条件。必须写清阈值（立即数或表地址）。
3. 支撑证据：至少 2 条**逐字**汇编（含地址与助记符/操作数），例如
   `@0x41ea75 cmp edx, dword ptr [eax + 0x496b84]`（不要改写）。
4. 不确定处写「未决」，**禁止编造**。
5. 不要从 rich4-re/ 的文档抄结论；rich4-re/asm 只能当导航线索。

输出格式（Markdown），写入指定文件，并在最终消息里给出同样内容：
```
### action N · <中文卡名>  handler 0x…  f7=…  price=…
判据：…
证据：
- @0x… `instruction`
- @0x… `instruction`
未决：…
```
