# grp3 · AI 用卡判据 action 28–33（rich4.exe, ImageBase 0x400000）

## 共用事實（本組 6 個 handler 都用到，先逐字驗證）
- `0x40b221(player,n)`：memset(0x48b8b4,0,0x10) 後產生 n 格走位，起點 `player+0xc`（當前格）、避開 `player+0xe`；每步在 map2land[cell]+0x18..+0x1e 四個鄰格中，排除 0、排除上一格、排除 `[+0x24]` 對應的 0x40000000>>i 阻擋位；只有 1 個候選就用它，>=2 個才 `rand()`。**回傳值=1 表示「過程中用過隨機」**。
  - @0x40b231 `push 0x48b8b4` ｜ @0x40b254 `mov dx, word ptr [eax + 0x496b74]` ｜ @0x40b2ca `mov word ptr [esp + ebx*2], dx` ｜ @0x40b2f2 `call 0x456f2d` ｜ @0x40b302 `mov word ptr [esi + 0x48b8b4], ax` ｜ @0x40b309 `mov dword ptr [esp + 8], 1` ｜ @0x40b337 `mov eax, dword ptr [esp + 8]`
- `0x40b343(player,n)`：同結構，但起點是 `player+0xe`、避開 `player+0xc`（只被 action 32/33/34 使用）。
  - @0x40b376 `mov dx, word ptr [eax + 0x496b76]` ｜ @0x40b420 `mov word ptr [esi + 0x48b8b4], ax`
- `0x40a45c(radius)`：把 0x474938 的 440×440 物件格中非零值依序抄進 `g48b8c4[]`，**回傳抄了幾個（eax=ebx）**；radius==-1 掃全圖；radius 為正時只掃邊長 2*radius 的方框（0x40a472 起算 `441*(220-radius)`，即中心 (220,220)──「推断」該點對應玩家所在格；本組所有呼叫端都傳 -1）。
  - @0x40a460 `mov edi, dword ptr [esp + 0x14]` ｜ @0x40a464 `cmp edi, -1` ｜ @0x40a46b `mov edi, 0x1b8` ｜ @0x40a4bb `mov word ptr [ebx*2 + 0x48b8c4], cx` ｜ @0x40a4da `mov eax, ebx`
- `0x409ef9()`：重建 0x474938 物件格（只放視窗內 `[map2land+0x24] & 0xffff00 == 0` 的「素格」的 map2land 索引，@0x409f7c `test dword ptr [esi + 0x24], 0xffff00`）後，同樣抄進 g48b8c4[] 並回傳筆數。
- `0x419744(owner, namePtr)`：累加 res_land 中 owner 相同且 `strcmp(+4,namePtr)==0` 者的「等級 → `[entry+level*2+0x20]`」值（+0x20 是各等級價值陣列）。
  - @0x419793 `mov al, byte ptr [ebx + 0x1a]` ｜ @0x419796 `mov ax, word ptr [ebx + eax*2 + 0x20]`
- aiP 槽：aiP0=0x48be58, aiP1=0x48be5c, aiP2=0x48be60, aiP3=0x48be64；`0x41e6f2(i)` 讀回。
- 參數 0x8000|(1<<p) = 玩家 p：`0x40d293` 取最低 set bit 回傳玩家索引（`test dl,0xff` → `test dl,1` 迴圈）。卡 29/30 的效果函式 0x445710/0x4458df 都先 `call 0x40d293` 解出目標玩家再改該玩家；卡 28 的效果函式 0x445593 直接把 aiP0 當地產 id 用。
- f7 = 卡片表 0x47fdea 第 c 筆 +7 位元組（=0x47fdf1+8c），是**用卡的性格門檻**：`0x41e6a4` 讀入、`0x41e6bd` 減 `player+0x17(personality)`、`0x41e6c1 cmp edx,2`（差 >=2 直接不用；差==1 有 1/3 機率放棄）、`0x41e6ea call dword ptr [eax*4 + 0x475324]`。price = 同筆 +5。
- 物件表 0x496d08：`0x407d3a push 0x450` / `0x407d41 push 0x496d08` / `0x407d46 call 0x456f60` → memset 0x450 = 0x2e(46) 筆 × 0x18 位元組；+0 = 型別碼，型別初值表在 0x47ed3c（`0x407d5d mov byte ptr [eax*8 + 0x496d08], dl`，索引 3*i）。

## action 28 · 查封卡  handler 0x42062b  f7=1  price=35
判据：先 `0x40b221(current_player,6)` 取 6 格走位（g48b8b4），`0x40d2d3` 取最敵對玩家 hostile。逐格取 `map2land[cell]+0x20` 的地產 id：①住宅地（0x7d0 < id < 0xfa0，索引 id-0x7d0、步長 0x34 的 res_land）——先用 strcmp 與「上一個候選」的地名去重；再掃全部同名地段條目：只要有一筆 owner==current_player+1 → 放棄此格（@0x4207af）；owner==0 不計；其他玩家的等級 `[+0x1a]` 累加進 edi，**edi >= 7** 就 `aiP0 = 該 id`、回傳 1。②商業地（0xfa0 < id < 0x1770，步長 0x38 的 com_land）：hostile != -1 且 `com_land[id-0xfa0].+0x19 == hostile+1` 且 `+0x18 != 0` 且等級 `+0x1a >= 3` → `aiP0 = 該 id`、回傳 1。其餘 id 一律略過。
证据：
- @0x42063a `push 6` ｜ @0x420643 `call 0x40b221` ｜ @0x420652 `call 0x40d2d3`
- @0x420722 `mov ax, word ptr [edx + eax + 0x20]` ｜ @0x420730 `cmp eax, 0x7d0` ｜ @0x42073b `cmp eax, 0xfa0`
- @0x4207ad `cmp edx, eax` （je 0x420685：同名地段自己已持有→放棄）｜ @0x4207be `add edi, eax`
- @0x42066f `cmp edi, 7` ｜ @0x420672 `jl 0x420685` ｜ @0x420678 `mov dword ptr [0x48be58], eax`
- @0x4206a3 `cmp dword ptr [esp + 4], -1` ｜ @0x4206c7 `cmp ebx, edx` ｜ @0x4206cb `cmp byte ptr [eax + 0x18], 0` ｜ @0x4206d1 `cmp byte ptr [eax + 0x1a], 3` ｜ @0x4206db `mov dword ptr [0x48be58], eax`
未决：0x420669 讀的 `[esp]` 旗標在此路徑恆為 0（0x420776 只寫 0），疑似編譯器殘留條件；res_land/com_land 的 `+0x18` 欄位語意未定（此處只確定「非 0」）。效果函式 0x445593 以 aiP0 為地產 id（住宅：同名地段全部標 `[+0x17]=0x51`；商業：`[+0x1c]=0x51`）。

## action 29 · 同盟卡  handler 0x4207cc  f7=0  price=40
判据：`aiP2 = 0x40a45c(-1)`（全圖物件清單長度），掃 g48b8c4[0..aiP2-1]：只取「高位 0x8000 且低 4 位非 0」的條目，以最低 set bit 解出玩家索引 p；排除 p==current_player、p==最敵對玩家（0x40d2d3）、`player[p].type(+0x15)==0`、`player[p].ally(+0x41)==current_player+1`（已同盟）→ 得到候選表（放 [esp..]，個數 edi；edi==0 直接回 0）。接著對所有 `p != self` 且 `type != 0` 的玩家統計其 res_land + com_land 持有筆數（`owner == p+1` 才計），取**嚴格最大**者 best（含敵對者/已同盟者在內一起比）。最後若 best 恰好出現在候選表中 → `aiP0 = 0x8000 | (1<<best)`、回傳 1，否則 0。
证据：
- @0x4207db `call 0x40a45c` ｜ @0x4207e3 `mov dword ptr [0x48be60], eax` ｜ @0x420804 `cmp eax, dword ptr [0x48be60]`
- @0x420810 `mov dx, word ptr [eax*2 + 0x48b8c4]` ｜ @0x42081e `test dh, 0x80` ｜ @0x420823 `test dl, 0xf`
- @0x42084e `cmp byte ptr [ebx + 0x496b7d], 0` ｜ @0x420857 `mov bl, byte ptr [ebx + 0x496ba9]` ｜ @0x420869 `inc ebp` ｜ @0x42086a `cmp ebx, ebp`
- @0x4208de `cmp ebp, dword ptr [esp + 8]` ｜ @0x420921 `cmp esi, edx` ｜ @0x420925 `mov esi, edx`
- @0x420940 `cmp eax, ebx` ｜ @0x42094d `shl eax, cl` ｜ @0x42094f `or ah, 0x80` ｜ @0x420952 `mov dword ptr [0x48be58], eax`
未决：g48b8c4 條目 0x8000 的確實來源（玩家圖示標記 0x8000|1<<p 由 0x4087ed 產生並由 0x409de7 OR 入 0x474938；但其他物件也用同一位元格式，本 handler 不區分）；同盟效果（0x445710）設定雙方 `+0x41(ally)=對方+1`、`+0x3d=7`（7 回合），此處只據 aiP0 解碼推得目標為單一玩家。

## action 30 · 烏龜卡  handler 0x420970  f7=0  price=70
判据：三階段。**階段1**（僅當 `0x40b221(current_player,3)` 回傳 0，即 3 格走位無隨機分支時才評估）逐格（g48b8b4[0..2]）取 map2land+0x20：住宅地（0x7d0<id<0xfa0）——owner==self+1 且 `[+0x18]==0` 且等級 `[+0x1a] < 5`，或 owner==0 者 → `edi += (有主 ? [+0x1e] : [+0x1c])`、計數++；若該格是**其他玩家**的住宅地且 `0x419744(owner,name) > 1000*price_index` → 立刻跳階段2。商業地（0xfa0<id<0x1770）——owner==self+1 且 `[+0x18] ∉ {0,3}` 且等級<5 → 計數++；其他玩家的商業地 `[+0x18] ∉ {0,4}` 且等級!=0 → 跳階段2。第三類（0x1770<id<0x1f40，表 `[0x498e7c]` 步長 0x34）——該筆 `[+0x18] != 0 且 != self+1` → 跳階段2。三格跑完且 `edi*1.5 < player.cash`（0x463d40 = 1.5）、計數 >= 2、`cash+bank > 0x2710(10000)`、`word[player+0x46] >= 0` → `aiP0 = 0x8000|(1<<current_player)`、回傳 1。**階段2/3**：`aiP2 = 0x40a45c(-1)`，以同一 0x8000/低4位規則解出候選玩家（只排除 self 與 type==0，不排除敵對/已同盟）；對每個候選 `0x40b221(候選,3)`（回傳非 0 即跳過該候選），走訪其 3 格：任一格若是住宅/商業/第三類地且 owner==0 或 owner==候選+1 → 放棄該候選；屬於 current_player 的格累加價值與計數，最後 `edi >= 10000*price_index` 且 計數 >= 2 → `aiP0 = 0x8000|(1<<候選)`、回傳 1。
证据：
- @0x42097d `push 3` ｜ @0x420986 `call 0x40b221` ｜ @0x42098e `test eax, eax` ｜ @0x420990 `jne 0x420a82`
- @0x420a11 `cmp byte ptr [esi + 0x1a], 5` ｜ @0x420a7a `cmp ebx, eax` （eax=1000*price_index，jle 續格）
- @0x420b8c `je 0x4209a4` ｜ @0x420b92 `jmp 0x420a82` ｜ @0x420b97 `cmp eax, 0x1770` ｜ @0x420ba2 `cmp eax, 0x1f40`
- @0x420bff `fmul qword ptr [0x463d40]` ｜ @0x420c0a `jae 0x420a82` ｜ @0x420c10 `cmp dword ptr [esp + 0x10], 2` ｜ @0x420c27 `cmp eax, 0x2710` ｜ @0x420c32 `cmp word ptr [edx + 0x496bae], 0`
- @0x420c4b `shl eax, cl` ｜ @0x420c4d `or ah, 0x80` ｜ @0x420c50 `mov dword ptr [0x48be58], eax`
- @0x420cb5 `push 3` ｜ @0x420cbe `call 0x40b221` ｜ @0x420e6f `cmp edi, eax`（eax=10000*price_index）｜ @0x420e73 `cmp dword ptr [esp + 0x10], 2` ｜ @0x420e87 `mov dword ptr [0x48be58], eax`
未决：`player+0x46` 欄位語意；住宅/商業 `+0x18` 的列舉值意義（此處只確定測哪些值）；階段1/3 的 `[esp+4]` 恆為 0（0x420998 寫 0），疑似殘留條件；效果函式 0x4458df 對目標 `0x40d293` 解碼後把 `player+0x39` 設 3（別人）或 2（自己），`+0x39` 每回合遞減（0x41cb4c-0x41cb67），推断是回合數狀態。

## action 31 · 機器娃娃(道具)  handler 0x420efa  f7=0  price=15
判据：僅當 `0x40b221(current_player,4)` 回傳 0（4 格走位無隨機分支）才評估。沿 g48b8b4[0..3] 找第一格滿足 `(map2land[cell]+0x24 & 0x3f0000) >> 16 != 0` 者（t = 該 6-bit 值，代表佔用該格的物件編號），查物件表 0x496d08 第 t-1 筆（步長 0x18，索引算式 3*(t-1)*8）的 `+0` 型別碼 c，並取該格地產（住宅：owner=`[entry+0x19]`、value=`0x419744(owner,name)`；商業：owner=`[com_land+0x19]`、value 固定 0x989680）：c ∈ {5,6,7,8,0xb} → 使用；或 c==0x11 且該格地產 owner==current_player+1 → 使用；或 c==0x10 且 owner!=0、owner!=current_player+1 且 value > 3000*price_index → 使用。命中即回傳 1（esi 黏著），**本 handler 不寫任何 aiP\***。
证据：
- @0x420f00 `push 4` ｜ @0x420f09 `call 0x40b221` ｜ @0x420f11 `test eax, eax` ｜ @0x420f13 `jne 0x421078`
- @0x420fb6 `mov ebp, dword ptr [eax + 0x24]` ｜ @0x420fb9 `and ebp, 0x3f0000` ｜ @0x420fbf `shr ebp, 0x10` ｜ @0x420fc4 `je 0x420f88`
- @0x420f4d `mov edx, 0x989680` ｜ @0x420f52 `dec ebp` ｜ @0x420f5a `mov al, byte ptr [eax*8 + 0x496d08]`
- @0x420f66 `cmp eax, 5` ｜ @0x420f69 `je 0x420f83` ｜ @0x420f7a `cmp eax, 0xb` ｜ @0x420f7d `jne 0x421010`
- @0x421014 `cmp eax, 0x11` ｜ @0x421020 `cmp ebx, ebp` ｜ @0x421030 `cmp eax, 0x10` ｜ @0x421039 `test ebx, ebx`
- @0x42106b `cmp edx, eax`（eax=3000*price_index）｜ @0x42106d `jle 0x420f88` ｜ @0x421078 `mov eax, esi`
未决：型別碼 {5,6,7,8,0xb,0x10,0x11} 的具體物件名稱（型別初值表 0x47ed3c 為 1..0x12 分組：1..0x0f 各一筆、0x0f×2、0x10/0x11/0x12 各 10 筆）；商業地一律給固定值 0x989680 的用意。

## action 32 · 路障(道具)  handler 0x42107f  f7=1  price=30
判据：`aiP3(0x48be64) = 目標格（map2land 索引）`。**階段1**：`0x40b221(current_player,4)`，逐格要求 `[map2land+cell*0x28+0x24] & 0x3fff00 == 0`（空物件格），再依 map2land+0x20 分類：①住宅地（0x7d0<id<0xfa0）且 res_land 該筆 owner==0（無主），且同名地段中 owner==self+1 的筆數 >= 2 或該筆等級 `[+0x1a] != 0`，且 `[+0x1c]*price_index < player.cash`、`cash+bank > 0x2710`、`word[player+0x46] >= 0`、`byte[player+0x39] == 0` → aiP3=該格、回傳 1。②商業地（0xfa0<id<0x1770）且該筆 owner==0，同樣的錢/狀態條件，另要求 `[+0x22]*price_index < cash` → aiP3=該格。③其他格：`byte[map2land+cell*0x28+0x24] == 0x0f` 且 `word[player+0x30(points)] > 0xc8(200)` → aiP3=該格。**階段2**（階段1 未決定）：`0x40b343(current_player,6)`（從 player+0xe 起的 6 格）+ `0x409ef9()` 重填 g48b8c4（回傳物件數 N）；對 g48b8c4[0..N-1] 中「同時等於 6 格之一」的格，若是 owner==self+1 的住宅/商業地且 `0x419744(self,name) > 6000*price_index`，取該值最大者 → aiP3=該格、回傳 1。
证据：
- @0x42108c `push 4` ｜ @0x421095 `call 0x40b221` ｜ @0x42109f `jne 0x421299`
- @0x421148 `test dword ptr [eax + 0x24], 0x3fff00` ｜ @0x42114f `jne 0x421118` ｜ @0x42117d `cmp byte ptr [edx + 0x19], 0` ｜ @0x4211bb `cmp eax, edx`
- @0x4210bd `cmp ebx, 2` ｜ @0x4210c2 `cmp byte ptr [eax + 0x1a], 0` ｜ @0x4210db `cmp edx, 0x2710` ｜ @0x4210e3 `cmp word ptr [eax + 0x496bae], 0` ｜ @0x4210ed `cmp byte ptr [eax + 0x496ba1], 0` ｜ @0x4210f6 `cmp esi, dword ptr [eax + 0x496b84]`
- @0x4210fe `mov ax, word ptr [ebp*2 + 0x48b8b4]` ｜ @0x42110b `mov dword ptr [0x48be64], eax`（住宅決定）｜ @0x421241 `cmp edx, dword ptr [eax + 0x496b84]`（商業）｜ @0x42126f `cmp eax, 0xf` ｜ @0x42127f `cmp word ptr [eax + 0x496b98], 0xc8` ｜ @0x42128e `mov dword ptr [0x48be64], ebx`
- @0x4212a4 `push 6` ｜ @0x4212ad `call 0x40b343` ｜ @0x4212b5 `call 0x409ef9` ｜ @0x4212f0 `cmp eax, esi`
- @0x421352 `mov al, byte ptr [edx + 0x19]` ｜ @0x42135c `cmp eax, edx` ｜ @0x42136e `mov ebx, eax`（=0x419744 回傳）｜ @0x42138f `cmp ebx, eax`（6000*price_index）｜ @0x4213a6 `mov dword ptr [0x48be64], eax`
未决：`player+0x39`、`player+0x46` 語意（推断 0x39 是回合數狀態，見 0x41cb4c）；`+0x18` 欄位語意；`map2land+0x24` 低byte==0x0f 的格子種類。

## action 33 · 地雷(道具)  handler 0x4213c5  f7=1  price=25
判据：`0x40b343(current_player,6)`（從 player+0xe 起的 6 格 → g48b8b4）+ `0x409ef9()`（重填 g48b8c4，回傳 N）。對每個 g48b8c4[k]（k<N），先用 6 格逐一比對，只有「值等於某個走位格」才處理：①值 == `word[0x48bae0]` 且 `dword[0x496b30] != 0`，或值 == `word[0x48bae2]` 且 `dword[0x496b60] != 0` → 立即 `aiP3 = 該值`、回傳 1（不需其他條件）。②否則查 `map2land[值]+0x20`：住宅（0x7d0<id<0xfa0）或商業（0xfa0<id<0x1770）且該筆 `owner(+0x19) != 0` 且 `owner != current_player+1` → 把該格收進候選陣列（esi 為候選數）。全部掃完若候選數 != 0 → `rand()` 取 `random % esi` 選一個，`aiP3 = 該格`、回傳 1；否則回傳 0。
证据：
- @0x4213d7 `push 6` ｜ @0x4213e0 `call 0x40b343` ｜ @0x4213e8 `call 0x409ef9` ｜ @0x4213ed `mov dword ptr [esp + 0x204], eax`
- @0x421413 `mov cx, word ptr [ebx*2 + 0x48b8c4]` ｜ @0x42141b `mov dx, word ptr [eax*2 + 0x48b8b4]` ｜ @0x421429 `cmp ecx, edx`
- @0x421446 `mov dx, word ptr [0x48bae0]` ｜ @0x421451 `cmp dword ptr [0x496b30], 0` ｜ @0x421469 `mov dx, word ptr [0x48bae2]` ｜ @0x421474 `cmp dword ptr [0x496b60], 0`
- @0x4214ce `cmp byte ptr [eax + 0x19], 0` ｜ @0x4214d2 `je 0x421534` ｜ @0x4214df `cmp ecx, eax` ｜ @0x4214e1 `je 0x421534` ｜ @0x42152f `mov word ptr [esp + esi*2], dx`
- @0x42153e `call 0x456f2d` ｜ @0x421548 `idiv esi` ｜ @0x421553 `mov dword ptr [0x48be64], eax`
未决：0x48bae0/0x48bae2 這兩個特殊格的意義——由 `0x40803f cmp word ptr [edx + eax*8 + 0x20], 0x1f41` → `0x408048 mov word ptr [0x48bae2], bx`、`0x40805f cmp word ptr [edx + eax + 0x20], 0x1f42` → `0x408068 mov word ptr [0x48bae0], bx` 取得，即 map id 0x1f41/0x1f42 的格；0x496b30 / 0x496b60 是 4 玩家 byte 旗標陣列（0x43d674 / 0x43ed20 會對某玩家設 1），此處以 **dword** 比較等同「任一玩家有旗標」，語意未定。

## 與簡報不一致處（給 parent 的修正）
1. g48b8c4 **不是**「長度 440 的全圖 word 陣列」。它是 `0x40a45c(radius)` 每次填入的**可變長度清單**（把 0x474938 的 440×440 物件格中非零值抄進來），回傳值＝清單長度（@0x40a4da `mov eax, ebx`）。`0x40a45c(-1)` 回傳的是「全圖非零物件數」，不是 440。action 2/7/9/10/11/13/14/15/26/27/29/30/34/39 都用這個清單。
2. 條目高位 0x8000、低 4 位非 0 者是**玩家標記 0x8000|(1<<p)**（產生處 @0x4087ed `shl eax, cl` + @0x4087ef `add ah, 0x80` → 存入 0x48a850；@0x409de7 將其 OR 進 0x474938），不是「地權位掩碼」；地產 id（0x7d1…/0xfa1…）以明文存同一格。
3. f7 = 0x47fdea 第 c 筆的 +7 位元組（=0x47fdf1+8c），是 0x41e69e 的性格門檻，不是效果參數；price = 同筆 +5。
