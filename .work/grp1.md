# grp1 · action 9–14 用卡判据（rich4.exe v3.11 / ImageBase 0x400000）

本组共用事实（均为逐字读码所得）：
- 卡表基址 **0x47fdea**、每项 8 字节：+0=名称指针、+4=f4、+5=price、+7=f7。action 13 读的 `[eax + 0x47fdf1]` 即 +7、`[eax + 0x47fdef]` 即 +5；按此表读第 9–14 项得 price=160/180/60/15/25/20、f7=0/2/2/1/2/0，与题给完全一致（第 9 项起始 0x47fdea+9*8=0x47fe32，price 字节 0x47fe37=0xa0）。
- 地图 word 表 g48b8c4，长度 0x1b8=440（来自 `push -1` + `call 0x40a45c`）。值域约定：`0x7d0 < w < 0xfa0` = 住宅地块（索引 w-0x7d0，步长 0x34），`0xfa0 < w < 0x1770` = 商业地块（索引 w-0xfa0，步长 0x38），其余且 bit15 置位者另有一套「地图物件」编码（见 action 12）。
- res_land/com_land 记录 **+0x19 = 拥有者（1 基，0=无主）**；地名是记录内联字符串：strcmp(0x458370) 的实参由 `lea eax,[rec+4]` 直接给出（0x458370 内部解引用实参，故 +4 不是指针）「推断，与 BRIEF 的“+4=地名指针”不一致」。
- 0x40d2d3 = find_most_hostile_player(self)，返回 0 基下标或 -1。
- 以下引文一律是**二进制原文**（未替换注释名）。对照：0x49910c=current_player、0x4990e8=price_index、0x48be58=aiP0、0x48be5c=aiP1、player 基址 0x496b68（+0x15 type、+0x17 个性、+0xc 当前格、+0x1c cash、+0x20 bank；+0x11/+0x39/+0x46 见各条未决）。

### action 9 · 天使卡  handler 0x41f037  f7=0  price=160
判据：遍历全部 0x1b8 个地图格，只收 `0x7d0<w<0xfa0` 且 res[w-0x7d0][+0x19]==current_player+1 且 [+0x18]==0 且 [+0x1a]<5 的地块，按「同名地名（strcmp 记录+4）」聚成街道并计数（命中同名者只把计数 +1，不新增项）；再把计数 **≥3** 的街道下标收进候选数组，若候选数 n≠0 则 `rand()%n` 随机取一条，aiP0 = 该街道首次出现地块的 word 值，返回 1；否则返回 0。
证据：
- @0x41f08b `cmp eax, 0x7d0` ／ @0x41f096 `cmp eax, 0xfa0`
- @0x41f0b6 `mov esi, dword ptr [0x49910c]` ／ @0x41f0bc `inc esi` ／ @0x41f0bd `cmp eax, esi`（esi=current_player+1）
- @0x41f0db `cmp byte ptr [ebx + 0x1a], 5`
- @0x41f0ea `push eax` ／ @0x41f0eb `call 0x458370`（比对两条记录的 +4 地名）
- @0x41f0f7 `inc word ptr [esp + edi + 6]`（同名计数）
- @0x41f14e `cmp word ptr [esp + ecx*8 + 6], 3` ／ @0x41f154 `jb 0x41f165`（门槛=3）
- @0x41f172 `call 0x456f2d` ／ @0x41f187 `mov ax, word ptr [esp + eax*8 + 4]` ／ @0x41f191 `mov dword ptr [0x48be58], eax`
未决：+0x18、+0x1a 的确切语义（等级/抵押？）；aiP0 存的是原始 word（0x7d0 段地块 id），效果函数如何解释未查。

### action 10 · 惡魔卡  handler 0x41f1b3  f7=2  price=180
判据：先取敌对目标 H=`0x40d2d3(current_player)`。按街道名分组，对每组按拥有者累计 A[owner]=该街道 [+0x1a] 之和、B[owner]=地块数（只统计 `0x7d0<w<0xfa0`、[+0x18]==0、[+0x19]!=0 的地块）。若 H!=-1：取 A[H]≥**7** 且 B[H]≥**2** 且 A[current_player]≤**1** 的街道，aiP0=该街道首地块 word。若 H==-1：取 A[self]==**0** 且 Σ其他活跃玩家 B≥**3** 且 Σ其他活跃玩家 A≥**9** 的街道。找到即返回 1，否则 0。
证据：
- @0x41f1d8 `call 0x40d2d3` ／ @0x41f1e0 `mov dword ptr [esp + 0x204], eax`
- @0x41f265 `cmp byte ptr [ebx + 0x18], 0` ／ @0x41f26b `cmp byte ptr [ebx + 0x19], 0`（只统计 [+0x18]==0 且业主≠0 的地块）
- @0x41f28f `add byte ptr [esp + eax + 3], dl`（A[owner] += [+0x1a]）／ @0x41f29a `inc byte ptr [esp + ebp + 7]`（B[owner]++）
- @0x41f332 `cmp byte ptr [esp + eax + 8], 2` ／ @0x41f337 `jb 0x41f3e7`（B[敌]≥2）
- @0x41f33d `cmp byte ptr [esp + eax + 4], 7`（A[敌]≥7）／ @0x41f34f `cmp byte ptr [esp + eax + 4], 1`（A[自己]≤1）
- @0x41f3d4 `cmp ebp, 3`（ΣB≥3）／ @0x41f3d9 `cmp edx, 9`（ΣA≥9）
- @0x41f35e `mov dword ptr [0x48be58], eax`
未决：0x41f0c7/0x41f101 处 `[esp+0x114]` 恒为 0（疑似死变量），不影响判据；A/B 数组下标是 0 基玩家号（+4/+8 与 1 基 owner 对应）已核对。

### action 11 · 怪獸卡  handler 0x41f400  f7=2  price=60
判据：对每个拥有者分别维护「住宅最高等级(≥3 才收) + 对应最高价(+0x1c) + 地块 word」和「商业最高等级(≥3 才收) + 对应最高价(+0x22) + 地块 word」，只收 `0x7d0<w<0xfa0` / `0xfa0<w<0x1770`、[+0x19]!=0、[+0x19]!=self+1、[+0x1a]≥**3** 的地块。若敌对目标 H≠-1：优先取 H 的商业最高等级≥**3** 者，否则取住宅最高等级≥**3** 者，aiP0=该地块 word。H==-1 **或 H 名下没有 ≥3 的建筑**时走同一段全局扫描（0x41f5d4 起）：在全部活跃他人中取商业最高等级≥**3** 或住宅最高等级≥**4** 者（商业优先于住宅）。命中返回 1。
证据：
- @0x41f424 `call 0x40d2d3`
- @0x41f4a0 `cmp byte ptr [eax + 0x1a], 3`（住宅门槛 3）／ @0x41f549 `cmp byte ptr [eax + 0x1a], 3`（商业门槛 3）
- @0x41f4f3 `cmp esi, dword ptr [esp + ebx - 4]`（同级比价 +0x1c）
- @0x41f5ab `cmp word ptr [esp + edx + 0x20], 3`（敌商业等级≥3）／ @0x41f5c4 `cmp word ptr [esp + edx], 3`（敌住宅等级≥3；两处都不满足则跳到 0x41f5d4）
- @0x41f650 `cmp word ptr [esp + eax], 4`（全局扫描里住宅门槛升为 4）／ @0x41f60a `cmp word ptr [esp + eax + 0x20], 3`
- @0x41f5ba `mov dword ptr [0x48be58], eax`
未决：+0x1c（住宅 0x41f4c8）与 +0x22（商业 0x41f56d）哪个是地价、哪个是建筑价值，未定。

### action 12 · 拆除卡  handler 0x41f6a9  f7=1  price=15
判据：**先直接调用 action 11 的 handler 0x41f400，若它返回 1 就原样返回 1**（复用怪獸卡选出的目标与 aiP0）；否则自己扫描：住宅地块要求 self 的 [+0x17]≠0、地有主且非 self、[+0x18]≠0、且 `0x41970f(owner)`（该 owner 名下有 [+0x18]≠0 的住宅数）≥**4**；商业地块要求 (self[+0x11]&3)≠0、商业 [+0x18]==**3**、[+0x1a]==**1**、业主≠self；或对 bit15 置位的 word：idx=(w>>8)&0x3f≠**0**，取 24 字节步长表 0x496d08 的第 idx-1 项，其 +2 word 经 map2land 得地块 id a，若该项 [+0]==**0x10** 则要求 a 的业主≠self 且≠0（住宅）或商业有主非 self；若 [+0]==**0x11** 则要求业主==self+1。命中即 aiP0=该 word、返回 1。
证据：
- @0x41f6ad `call 0x41f400` ／ @0x41f6b2 `cmp eax, 1` ／ @0x41f6b5 `je 0x41f8fc`
- @0x41f70a `cmp byte ptr [edx + 0x496b7f], 0` ／ @0x41f781 `test byte ptr [edx + 0x496b79], 3`
- @0x41f73c `call 0x41970f` ／ @0x41f744 `cmp eax, 4` ／ @0x41f747 `jl 0x41f8f4`
- @0x41f78e `cmp byte ptr [eax + 0x18], 3` ／ @0x41f798 `cmp byte ptr [eax + 0x1a], 1`
- @0x41f7ba `test bh, 0x80` ／ @0x41f7c8 `and eax, 0x3f` ／ @0x41f7e2 `mov cx, word ptr [edx + 0x496d0a]`
- @0x41f810 `cmp byte ptr [edx + 0x496d08], 0x10` ／ @0x41f884 `cmp byte ptr [edx + 0x496d08], 0x11`
- @0x41f8e9 `mov dword ptr [0x48be58], ebx`
未决：0x496d08 是 24 字节步长、(+0)=类型、(+2)=地图格索引的表（别名/用途未定；文件里该区属 BSS，0x407d50 处按 0x47ed3c 逐项写类型字节，取值 1..0x12）；类型 0x10/0x11 与「自己/别人」的对应只能由「业主比对」推出「推断」。

### action 13 · 搶奪卡  handler 0x41f901  f7=2  price=25
判据：遍历地图格，对 bit15 置位且低 4 位≠0 的 word，把每个「位对应的活跃、非 self 玩家」记 flags[p]=1、并保存 word=0x8000|(1<<p)。先看敌对目标 H=`0x40d2d3`：要求 H≠-1、flags[H]!=0，再从 H 手牌（count_cards 0x441262）里挑一份 `卡表f7≥1` 且 price 最大者，aiP0=0x8000|(1<<H)、aiP1=卡号。否则退回全局：从所有 flags 玩家的手牌里挑 `卡表f7==2` 且 price 最大者，aiP0=0x8000|(1<<该玩家)、aiP1=卡号；都没有则返回 0。
证据：
- @0x41f94f `test byte ptr [esp + 0x11], 0x80` ／ @0x41f956 `test byte ptr [esp + 0x10], 0xf`
- @0x41f974 `cmp ebx, dword ptr [0x49910c]` ／ @0x41f97f `cmp byte ptr [eax + 0x496b7d], 0`（跳过 self 与非活跃者）
- @0x41f98e `or dh, 0x80`（存 0x8000|(1<<p)）／ @0x41f9a3 `cmp byte ptr [esp + ebp + 8], 0`（flags[H]）
- @0x41f9b7 `call 0x441262`（H 的手牌数）／ @0x41f9e5 `cmp byte ptr [eax + 0x47fdf1], 1`
- @0x41f9ee `mov al, byte ptr [eax + 0x47fdef]`（比价取最大）
- @0x41fa7f `cmp byte ptr [eax + 0x47fdf1], 2`（全局回退只认 f7==2）
- @0x41fa14 `mov dword ptr [0x48be58], eax` ／ @0x41fa19 `mov dword ptr [0x48be5c], edx`
未决：f7 的语义（1/2 的分类名）未定；被抢者拥有的多格会互相覆盖，但存值只含 0x8000|1<<p，故不影响结果。

### action 14 · 停留卡  handler 0x41facc  f7=0  price=20
判据：先取 self 所在格的地块 id L=map2land[player[+0xc]]。若 player[+0x39]==0 且 L 是住宅：要求业主==self、[+0x18]==0、[+0x1a]<**5**、`[+0x1e]*price_index < cash`、`cash+bank > 0x2710`、`[player+0x46] ≥ 0`，且（同名街道另有自己的地块 或 [+0x1a]≥**2**）→ aiP0=0x8000|(1<<self)。若 L 是商业：要求业主==self、`[+0x24]*price_index < cash`、`cash > 0x2710`、[+0x18]∉{0,3}、[+0x1a]<**5**、[player+0x46]≥0 → aiP0=0x8000|(1<<self)。以上都没命中时：对有地权的各玩家取其当前格地块 id，若某他人当前所在商业地业主==self 且 [+0x18]≠0 且 [+0x1a]≥**2**，或当前所在 0x498e7c 表地块（0x1770<id<0x1f40）的 [+0x18]==self+1 → aiP0=0x8000|(1<<该玩家)。
证据：
- @0x41fade `mov dx, word ptr [ecx + 0x496b74]` ／ @0x41faf2 `movzx ebp, word ptr [ebp + eax*8 + 0x20]`
- @0x41faf7 `cmp byte ptr [ecx + 0x496ba1], 0`（≠0 时跳过前两段）
- @0x41fb34 `imul ebx, dword ptr [0x4990e8]` ／ @0x41fb76 `cmp ebx, eax`（价<现金）
- @0x41fb84 `cmp eax, 0x2710`（cash+bank>10000）／ @0x41fb8f `cmp word ptr [ecx + 0x496bae], 0`
- @0x41fb66 `cmp byte ptr [edi + 0x1a], 5`（住宅等级<5）／ @0x41fc8d `cmp bl, 3`（商业 [+0x18]≠3）／ @0x41fc7e `cmp ebp, 0x2710`
- @0x41fbe9 `mov eax, 1` ／ @0x41fbee `shl eax, cl` ／ @0x41fbf3 `mov dword ptr [0x48be58], eax`（0x8000|1<<self）
- @0x41fdd7 `cmp byte ptr [eax + 0x18], 0` ／ @0x41fddd `cmp byte ptr [eax + 0x1a], 2`（第三段：他人所在商业地门槛）
- @0x41fe16 `mov dl, byte ptr [eax + 0x18]`（0x498e7c 表地块与 self+1 比对）／ @0x41fe2e `or ah, 0x80` ／ @0x41fe31 `mov dword ptr [0x48be58], eax`
未决：player+0x39、+0x46、+0x11（action 12）字段语义未定；0x498e7c 表（0x1770<id<0x1f40、步长 0x34）里 +0x18 被当作业主比对，而 res/com 表业主在 +0x19，两张表布局差异未查证。
