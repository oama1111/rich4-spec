# 第 4 组：AI 卡片/道具决策 handler（跳表 0x475324，action 34,35,36,37,38,39,41,42,43）
真值：`Rich4/rich4.exe`（ImageBase 0x400000）。所有 `@地址 \`指令\`` 均逐字取自 `.work/r4.py show`（未做任何改写）。
返回非 0 = AI 决定使用该卡/道具；目标参数写静态池 aiP0..aiP3 = 0x48be58/0x48be5c/0x48be60/0x48be64。

## 公用被调函数（先立好语义，下面 9 条判据引用）
- `0x40b343(玩家,n)` / `0x40b221(玩家,n)`：从玩家格（player+0xc / +0xe）出发，沿 map2land 项的 4 个邻接字（+0x18,+0x1a,+0x1c,+0x1e）随机游走 n 步，方向 mask = `map2land+0x24` 的 0x40000000>>dir 位；结果依次写 0x48b8b4[0..n-1]；返回 1 表示某一步候选 ≥2（用到了随机）。
  证据：@0x40b3cf `mov dx, word ptr [edi + edx*2 + 0x18]`；@0x40b3e4 `test ebp, ecx`；@0x40b410 `call 0x456f2d`；@0x40b420 `mov word ptr [esi + 0x48b8b4], ax`；@0x40b427 `mov dword ptr [esp + 8], 1`。
- `0x409ef9()`：memset 440×440 格表（0x5e880 = 440*440*2 字节），按屏幕位置把 map2land 序号写进格表，再把非 0 格值收进 g48b8c4，返回个数。
  证据：@0x409f43 `mov edx, dword ptr [0x474938]`；@0x409f4a `push 0x5e880`；@0x40a046 `mov word ptr [edx + eax*2], di`；@0x40a095 `mov word ptr [esi*2 + 0x48b8c4], dx`；@0x40a0aa `mov eax, esi`。
- `0x40a45c(n)`：先 `call 0x409de7` 重建同一张 440×440 表（0x409de7 把对象表 0x48a44c 的 word 逐格 `or` 叠加），再收非 0 格值进 g48b8c4，返回个数（n=-1 时收全图）。对象 word 由写入点可证：玩家标记 = `0x8000|(1<<玩家)`；住宅地 = `0x7d0+序号`；商业地 = `0xfa0+序号`；另有 `0x1770+` / `0x1f40+` 的其它对象。
  证据：@0x40a467 `jne 0x40a472`；@0x40a46b `mov edi, 0x1b8`；@0x40a4bb `mov word ptr [ebx*2 + 0x48b8c4], cx`；@0x4087ef `add ah, 0x80`；@0x408800 `mov word ptr [esi*4 + 0x48a850], dx`；@0x409248 `add edx, 0x7d0`；@0x409490 `add edx, 0xfa0`；@0x409636 `add eax, 0x1770`；@0x40977e `add eax, 0x1f40`；@0x409ede `or word ptr [edx], ax`。
- `0x40a0b1(x,y,r)`：同样重建格表，但只写「当前玩家所在格」= `0x8000|(1<<当前玩家)`（前置 `dword[player+0x32]`(0x496b9a)==0）与有主地产 = `0x7d0+i` / `0xfa0+i`；收集窗口 = 行/列 `[0xdc-r, 0xdc+r)`（r=-1 → 整图 `0..0x1b8`）→ g48b8c4，返回个数。
  证据：@0x40a117 `mov edx, dword ptr [eax + 0x496b9a]`；@0x40a1ca `add ch, 0x80`；@0x40a202 `mov word ptr [edx + eax*2], cx`；@0x40a2c8 `add ecx, 0x7d0`；@0x40a3ba `add ecx, 0xfa0`；@0x40a400 `sub edi, edx`；@0x40a3f4 `mov ebp, 0x1b8`；@0x40a447 `mov word ptr [esi*2 + 0x48b8c4], dx`。
- `0x4216ab(玩家,id)`（独立小函数，被 37 调用）：2000<id<4000 取 res_land[id-0x7d0]，4000<id<6000 取 com_land[id-0xfa0]，`+0x19`(owner)==玩家+1 → 1，否则 0。
  证据：@0x4216af `cmp eax, 0x7d0`；@0x4216c5 `mov eax, dword ptr [0x498e84]`；@0x4216ce `mov cl, byte ptr [eax + 0x19]`；@0x4216d6 `cmp ecx, eax`。
- `0x40d2d3(p)`=hostility[p][i] 最大者；`0x40d31c(p)`=随机挑一个 type!=0 且 player+0x32==0 的他人，无则 -1；`0x40d2b4()`=type!=0 的玩家数。

---

### action 34 · 定時炸彈  handler 0x421574  f7=1  price=25
判据：无前置门槛。`0x40b343(current_player,6)` 生成 6 步随机游走格表 0x48b8b4[0..5]，`0x409ef9()` 生成全图地块表 g48b8c4（返回个数）；只有「出现在那 6 步游走里」的格号才有资格：若格号 == `word[0x48bae0]`（该格 map2land+0x20==0x1f42）且 `dword[0x496b30]!=0`，或 == `word[0x48bae2]`（==0x1f41）且 `dword[0x496b60]!=0`，立刻选中该格；否则压入候选表（`[esp+esi*2]`）。最后 `rand() % 候选数` 随机取一个写 aiP3=[0x48be64]，候选数为 0 → 返回 0。
证据：
- @0x42158f `call 0x40b343`
- @0x421597 `call 0x409ef9`
- @0x4215c6 `mov dx, word ptr [eax*2 + 0x48b8b4]`
- @0x4215ed `mov dx, word ptr [0x48bae0]`
- @0x4215f8 `cmp dword ptr [0x496b30], 0`
- @0x42160f `mov ax, word ptr [0x48bae2]`
- @0x421619 `cmp dword ptr [0x496b60], 0`
- @0x421639 `mov word ptr [esp + esi*2], ax`
- @0x421548 `idiv esi`
- @0x421553 `mov dword ptr [0x48be64], eax`
未决：0x48bae0/0x48bae2 由 0x408068/0x408048 写入，条件分别是 `cmp word ptr [... + 0x20], 0x1f42` / `0x1f41`，即地图上两栋特殊建筑（医院/监狱之类别名，属「推断」）；0x496b30/0x496b60 是按玩家索引的字节标志数组（@0x40d774 `mov byte ptr [ebx + 0x496b30], dh`），此处用一条 `cmp dword ptr [...]` 同时比较 4 个玩家的标志。

### action 35 · 機車  handler 0x421644  f7=0  price=80
判据：`(byte[player+0x11] & 3) == 0` 且 `rand() % 4 == 0` 才返回 1（否则 0）；即只在无载具状态下、1/4 概率使用。
证据：
- @0x421647 `imul edx, dword ptr [0x49910c], 0x68`
- @0x42164e `test byte ptr [edx + 0x496b79], 3`
- @0x421655 `jne 0x421671`
- @0x42165e `mov ecx, 4`
- @0x421666 `idiv ecx`
- @0x421668 `test edx, edx`
- @0x42166c `mov ebx, 1`
未决：player+0x11（0x496b79）字段名；由 36/42 的阈值（<2 / !=3）与 @0x4221d8 `mov byte ptr [eax + 0x496b7a], 3` 推断为「已有载具级别」，属「推断」。

### action 36 · 汽車  handler 0x421675  f7=0  price=150
判据：`(byte[player+0x11] & 3) < 2` 且 `rand() % 4 == 0` 才返回 1；即无载具或只有機車(1)时可升级为汽車。
证据：
- @0x421678 `imul edx, dword ptr [0x49910c], 0x68`
- @0x42167f `mov dl, byte ptr [edx + 0x496b79]`
- @0x421685 `and dl, 3`
- @0x421688 `cmp dl, 2`
- @0x42168b `jae 0x4216a7`
- @0x42169c `idiv ecx`
- @0x42169e `test edx, edx`
未决：0x4216ab–0x421716 是独立函数 `0x4216ab(玩家,地产id)`（被 action 37 调用），dumphand 的边界把它并进了 action 36，它不是 36 的判据。

### action 37 · 飛彈  handler 0x421717  f7=2  price=100
判据：① 目标 = `0x40d2d3(current_player)`（hostility 最大者），若为 -1 改用 `0x40d31c(current_player)`（随机他人），仍为 -1 → 返回 0。② 用 `0x40a45c(-1)` 的全图格值表找「玩家标记」`0x8000|(1<<k)`：要求 `(word&0x8000)!=0`、`(word&0xf)!=0` 且位序 k == 目标玩家，命中即 aiP3=[0x48be64]=该 word；找不到 → 返回 0。③ 用 `0x40a0b1(目标+0x8, 目标+0xa, 0x64)` 取目标周围列表：若出现 0x8000 位（表内只有「当前玩家所在格」带 `0x8000|(1<<current_player)`）→ 返回 0；若某项 `0x4216ab(current_player, id)==1`（附近有自己的地产）→ 返回 0。④ 全部通过 → 返回 1。
证据：
- @0x42172a `call 0x40d2d3`
- @0x421734 `cmp eax, -1`
- @0x421740 `call 0x40d31c`
- @0x421758 `call 0x40a45c`
- @0x421782 `test ch, 0x80`
- @0x421787 `test cl, 0xf`
- @0x4217a1 `cmp edx, ebx`
- @0x4217a5 `mov dword ptr [0x48be64], ecx`
- @0x4217d0 `call 0x40a0b1`
- @0x4217f4 `test ch, 0x80`
- @0x4217f7 `jne 0x42181c`
- @0x421801 `call 0x4216ab`
- @0x42180c `je 0x42181c`
- @0x421815 `mov dword ptr [esp], 1`
未决：aiP3 存的是玩家标记 word（0x8000|1<<目标）而非格子号，目标玩家的还原方式在效果函数里；②中 `(word&0xf)` 只有玩家标记会满足（地产 id 2000–6000 的 bit15=0）。

### action 38 · 遙控骰子  handler 0x421827  f7=0  price=30
判据：前置全部不满足才继续——`byte[player+0x3f]`(0x496ba7) ∉{7,8,0xf}、`byte[player+0x39]`(0x496ba1)==0、`cash(player+0x1c)+bank(player+0x20) >= 0x2710`、`word[player+0x46]`(0x496bae)>=0、`0x40b221(current_player,6)==0`。随后遍历 6 个游走格 0x48b8b4[0..5]：跳过 `map2land+0x24` 的 bits12-15 !=0 的格；bits16-21(实体号)!=0 时，若 `byte[0x496d08 + 0x18*(实体号-1)]` ∈ {5,6,7,8,0xa,0xb,0x10,0x11,0x12} 也跳过。住宅地(id∈(0x7d0,0xfa0))：无主(+0x19==0)需「同街名(+4 用 0x458370 比较相等)且 owner==current_player+1 的地块数 ≥2」且 `cash > word[+0x1c] × 2.5`；已有主且是自己的、+0x18==0、+0x1a<5、同街自有地块 ≥2、`cash > word[+0x1e] × 2.5` → 取 +0x1a 最大者。商业地(id∈(0xfa0,0x1770))：无主需 `word[+0x22] × 2.5 < cash`；自己的需 +0x18!=0 且 !=3、+0x1a<5、`cash > word[+0x24] × 2.5`。命中即 aiP3=[0x48be64]=步数(i+1)，返回 1。
证据：
- @0x42183f `mov al, byte ptr [edx + 0x496ba7]`
- @0x421845 `cmp eax, 7`
- @0x42184f `cmp eax, 0xf`
- @0x42185b `cmp byte ptr [edx + 0x496ba1], 0`
- @0x421870 `cmp eax, 0x2710`
- @0x421877 `cmp word ptr [edx + 0x496bae], 0`
- @0x421884 `call 0x40b221`
- @0x421a15 `and edx, 0xf000`
- @0x421a25 `and eax, 0x3f0000`
- @0x4219b7 `fmul qword ptr [0x463d48]`（0x463d48 = 2.5）
- @0x421997 `cmp edi, 1`
- @0x4219c9 `mov dword ptr [0x48be64], eax`
- @0x421c77 `cmp bl, byte ptr [edi + 0x474940]`
未决：0x463d48 已读为 double 2.5；0x40b221 返回值“某步用过随机”为「推断」（由 @0x40b427 `mov dword ptr [esp + 8], 1` 只在 ≥2 候选分支执行推得）；+0x1c/+0x1e 与 +0x22/+0x24 的「地价/建筑数」命名沿用简报。

### action 39 · 機器工人  handler 0x421ba6  f7=0  price=30
判据：`0x40a45c(-1)` 取全图格值；对 2000<值<4000 的住宅地：owner(+0x19)==current_player+1、`byte[+0x18]==0`、`byte[+0x1a]<5`，比较 `word[+0x1a*2+0x20]` 取最大；对 4000<值<6000 的商业地：owner==current_player+1、`byte[+0x1a] < byte[0x474940 + byte[+0x18]]`（建筑类型上限表：0→1,1→5,2→5,3→1,4→5），比较 `word[+0x1a*2+0x24]` 取最大。命中即 aiP3=[0x48be64]=该地块 word（地产 id）；最终 ecx!=0 → 返回 1。
证据：
- @0x421bb4 `call 0x40a45c`
- @0x421bd8 `cmp edx, 0x7d0`
- @0x421be0 `cmp edx, 0xfa0`
- @0x421c04 `cmp ebx, edi`
- @0x421c0c `cmp byte ptr [eax + 0x18], 0`
- @0x421c1b `mov bx, word ptr [eax + ebx*2 + 0x20]`
- @0x421c2e `cmp byte ptr [eax + 0x1a], 5`
- @0x421c77 `cmp bl, byte ptr [edi + 0x474940]`
- @0x421c84 `mov ax, word ptr [eax + ebx*2 + 0x24]`
- @0x421c94 `mov dword ptr [0x48be64], edx`
- @0x421ca0 `test ecx, ecx`
未决：+0x20/+0x24 这两张按等级索引的 word 表的含义（造价/收益）未定；0x474940 处字节表已核为 `01 05 05 01 05`。

### action 41 · 傳送機  handler 0x421cb6  f7=1  price=95
判据：`0x409ef9()` 取可见地块表 g48b8c4；住宅地(id∈(0x7d0,0xfa0))要求 `byte[+0x19]==0`（无主）、`byte[+0x18]==0`、`byte[+0x1a]>=3` 且 `word[+0x1e] × price_index([0x4990e8]) < cash(player+0x1c)`，取 +0x1a 最大者；商业地(id∈(0xfa0,0x1770))要求 `+0x19==0`、`+0x18!=0`、`+0x1a>=3` 且 `word[+0x24] × price_index < cash`，取 +0x1a 最大者。命中写 aiP3=[0x48be64]=该 map2land 序号。最后还要 `cash+bank > 0x2710` 且 `word[player+0x46]>=0`，否则返回 0。
证据：
- @0x421cc1 `call 0x409ef9`
- @0x421d00 `cmp eax, 0x7d0`
- @0x421d1e `cmp byte ptr [eax + 0x19], 0`
- @0x421d28 `cmp byte ptr [eax + 0x18], 0`
- @0x421d32 `cmp byte ptr [eax + 0x1a], 3`
- @0x421d48 `mov ax, word ptr [eax + 0x1e]`
- @0x421d51 `imul eax, dword ptr [0x4990e8]`
- @0x421d58 `cmp eax, dword ptr [ebx + 0x496b84]`
- @0x421db5 `mov si, word ptr [eax + 0x24]`
- @0x421dfe `cmp eax, 0x2710`
- @0x421e05 `cmp word ptr [ebx + 0x496bae], 0`
未决：「无主地产 +0x1a>=3」的语义（0x1a 对无主地是否仍为等级）未定；此处 aiP3 存 map2land 序号（@0x421d66 `mov dword ptr [0x48be64], edi`），与 34/39 存地块 word 不同。

### action 42 · 工程車  handler 0x421e20  f7=2  price=150
判据：`(byte[player+0x11] & 3) != 3` 且 `rand() % 15 <= byte[player+0x17]`（個性 0x496b7f）→ 返回 1；否则 0。
证据：
- @0x421e24 `imul edx, dword ptr [0x49910c], 0x68`
- @0x421e2b `mov al, byte ptr [edx + 0x496b79]`
- @0x421e31 `and al, 3`
- @0x421e33 `cmp al, 3`
- @0x421e35 `jne 0x421e3c`
- @0x421e3c `movzx esi, byte ptr [edx + 0x496b7f]`
- @0x421e4a `mov ecx, 0xf`
- @0x421e56 `jg 0x421e5d`
未决：`rand()%15 <= 個性` 的概率语义（個性值域）未定。

### action 43 · 核子飛彈  handler 0x421e62  f7=2  price=250
判据：先收集所有「有主(+0x19!=0)且不是自己(owner!=current_player+1)且 +0x1a!=0」的住宅地序号+0x7d0、商业地序号+0xfa0 成表（`[esp+0x41c]` 为个数），表空 → 返回 0。最多 10 次（`cmp ecx, 0xa`）：`rand() % 个数` 随机取一个地产，用 `0x40a0b1(该地产 x, y, -1)` 取全图格值表；表内若出现 0x8000 位（=0x40a0b1 写的当前玩家所在格标记）→ 放弃本次；否则统计整图：自己的地块数(`[esp+0x424]`)/别人的地块数(`[esp+0x428]`) 与 自己等级和(edi)/别人等级和(esi)，两个比值都要 `< 1/(活跃玩家数+2)`（活跃玩家数 = `0x40d2b4()`）才接受：aiP3=[0x48be64]=该地产 id，返回 1。
证据：
- @0x421eb0 `cmp ecx, edx`（+0x19 owner != current_player+1）
- @0x421ec1 `add ebx, 0x7d0`
- @0x421f2d `add ebx, 0xfa0`
- @0x421f59 `je 0x4221ae`
- @0x421f92 `push -1`
- @0x421f9d `call 0x40a0b1`
- @0x421fe2 `test bh, 0x80`
- @0x421fe7 `mov dword ptr [esp + 0x414], 1`
- @0x421ffe `call 0x4216ab`
- @0x422003 `mov dword ptr [esp + 0x434], eax`（此时 esp 比帧基低 8，实际就是槽位 `[esp+0x42c]`）
- @0x422026 `cmp dword ptr [esp + 0x42c], 1`
- @0x4220bb `fdivp st(1)`
- @0x4220e0 `fdivp st(1)`
- @0x4220ee `add eax, 2`
- @0x422101 `fdivrp st(1)`
- @0x422125 `jae 0x422151`
- @0x422138 `jae 0x422151`
- @0x422141 `mov dword ptr [0x48be64], eax`
未决：0x8000 命中即作废这一条在 r=-1（整图）时会因 0x40a0b1 只在 `player+0x32==0` 时才写自己标记而变得很苛刻（player+0x32!=0 才可能用核彈），其设计意图未定；「比值 < 1/(n+2) 表示自己落后」为「推断」。
