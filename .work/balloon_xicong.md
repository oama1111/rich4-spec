# 小遊戲二／三：`0x004154DC` 與 `0x004155FC` 逆向規格

> 唯一真值：`Rich4/rich4.exe`（ImageBase 0x400000，PE32）。所有結論皆附 VA 與真實指令文本。
> 標「推断」者為推論，標「未决」者為未查清。`rich4-re/` 與 `rich4-remake/` 文件僅作導航，不採信其位址。

---

## 兩游戏的身份判别

資源 id 是唯一可靠的判別依據（兩個入口都只呼叫 `_read_mkf(handle,0,0,id)`，id 完全不同）：

| | 入口 VA | dispatch 事件類型 | panel.mkf id（→ 全域） | data.mkf id | 規則特徵 |
|---|---|---|---|---|---|
| 七彩氣球 | `0x004154DC` | 7 | `0x4e`→`0x48bd3c`、`0x4f`→`0x48bcd0`、`0x5b`→`0x48bd34` | 無 | 氣球自下方 `y=0x1a4` 往上升，**滑鼠左鍵點擊**得分；氣球上的數字即分數；另有 `x2`/`÷2`/`?` 三種特殊氣球 |
| 財神爺（喜從天降） | `0x004155FC` | 8 | `0x4e`→`0x48bd3c`、`0x4f`→`0x48bcd0`、`0x5c`→`0x48bd38`、`0x5d`→`0x48bce4`、`0x5e`→`0x48bcf4`、`0x5f..0x63`→`0x48bd14[0..4]`、`0x64+角色編號`→`0x48bd30` | `0x20e`→`0x48bce8` | **不處理滑鼠訊息**；由 `GetCursorPos` 驅動角色左右移動接寶物，寶箱10／錢袋5／元寶3／金幣1，炸彈一擊結束 |

判別證據（非猜測）：

- @source 0x0041525a / 0x00415273 / 0x0041528d：小遊戲一（case 6，`0x00415215`）載入 `push 0x4e`、`push 0x4f`、`push 0x50`；`0x004152a7`..`0x0041532c` 續載 `0x51..0x55` 與 `0x56..0x5a`（迴圈 `lea eax,[ebx+0x56]`）。
- @source 0x00415518 `push 0x4e`、0x00415532 `push 0x4f`、0x0041554b `push 0x5b`（＝氣球組）。
- @source 0x00415638 `push 0x4e`、0x00415652 `push 0x4f`、0x0041566b `push 0x5c`、0x00415685 `imul eax,dword ptr [0x49910c],0x68`＋0x0041568c `mov al,byte ptr [eax+0x496b7b]`＋0x00415697 `add eax,0x64`（角色專屬圖）、0x004156b3 `push 0x5d`、0x004156cd `push 0x5e`、0x004156e9 `lea eax,[ebx+0x5f]`（迴圈 5 次＝`0x5f..0x63`）。
- 影像內容（同一資源解出後的圖檔，僅作交叉驗證）：資源 `0x5b` 的第 1..13 張為「1..9」「x2」「÷2」「?」與爆破圖；資源 `0x5d` 為財神爺；`0x5f..0x63` 為寶箱/錢袋/元寶/金幣/炸彈；`0x64` 起為 12 位角色立繪。這與程式碼索引方式完全吻合：
  - @source 0x00413139 `and al,0xf` → 影像索引 = 狀態低 4 位（即氣球上的數字：狀態 s 的影像為第 s 張）。
  - @source 0x00413478 `mov ecx,dword ptr [edi*4 + 0x48bd14]` → 掉落物依 `type` 從 `0x48bd14[type]` 取圖集。

---

### 七彩氣球（入口 VA 0x004154DC）

**触发条件与触发点** — 事件分派表 `0x004197e9`，**事件類型 = 7**（不是 8）。@source 0x004197e9 表項 7（slot `0x00419805`）＝ `0x0041b15e`；@source 0x0041b15e `imul ebx,dword ptr [0x49910c],0x68`、@source 0x0041b165 `call 0x4154dc`、@source 0x0041b16a `jmp 0x41b152`、@source 0x0041b152 `add word ptr [ebx + 0x496b98], ax`。
分派器閘門（`0x00419837`..`0x004198b2`，`ebx` = 事件類型）：
- @source 0x00419837 `mov edx,dword ptr [esp + 0x10c]`（函式參數＝玩家/事件索引）；@source 0x00419840 `shl eax,2`＋0x00419843 `add eax,edx`＋0x00419845 `shl eax,3`（索引 ×0x28）＋0x0041984e `add eax,edx`（`edx` = `[0x498e80]`）→ 結構基底。
- @source 0x00419850 `mov dx,word ptr [eax + 0x20]`（存到 `[esp+0xf0]`）、@source 0x0041985b `mov ebx,dword ptr [eax + 0x24]`、@source 0x0041985e `and ebx,0xff` → 切換變數 = `[0x498e80]` 結構 `+0x24` 的位元組（事件類型），`+0x20` 的字被保存。
- @source 0x0041986c `imul eax,dword ptr [0x49910c],0x68`、@source 0x00419873 `cmp byte ptr [eax + 0x496b9f], 0`、@source 0x0041987a `je 0x419884`、@source 0x0041987c `test ebx,ebx`、@source 0x0041987e `jne 0x41b3d0` → 當前玩家 `+0x37` 非 0 且事件類型非 0 時整個事件被跳過（直接走 `0x41b3d0` 收尾）。
- 類型範圍檢查：@source 0x00419884 `cmp ebx,2`、0x00419887 `jb 0x4198a9`、0x00419889 `cmp ebx,0x10`、0x0041988c `ja 0x4198a9`；範圍內先播音效 @source 0x00419892 `mov al,byte ptr [ebx + 0x475299]`、0x00419898 `shl eax,3`、0x0041989b `add eax,0x48234a`、0x004198a1 `call 0x4542ce`。
- @source 0x004198a9 `cmp ebx,0x10`、0x004198ac `ja 0x41b3d0`、0x004198b2 `jmp dword ptr [ebx*4 + 0x4197e9]`。

**前置闸门** — 兩個閘門，任一不成立即跳到共享「未遊玩」分支 `0x00415457`：
- @source 0x004154e6 `imul eax,dword ptr [0x49910c],0x68`、0x004154ed `cmp byte ptr [eax + 0x496b7d], 1`、0x004154f4 `jne 0x415457`。
  `0x496b7d` = 玩家陣列 `0x496b68`（stride 0x68）`+0x15`，`eax` = 當前玩家索引 `[0x49910c]`×0x68。語意為「該玩家本局仍在場」——證據 @source 0x0040d2b4 區塊（`imul edx,eax,0x68`＋0x0040d2c3 `cmp byte ptr [edx + 0x496b7d], 0`＋`inc ecx`）＝統計旗標非 0 的玩家數；同型的第二支（`0x0040d2d3`）以 @source 0x0040d2fb `imul edx,esi,0x68`、@source 0x0040d300 `shl ebx,2`、@source 0x0040d305 `mov ebx,dword ptr [edx + 0x496bb4]`（即 `player[arg]+0x4c+other*4` 這排關係權重）挑出最大值者。此處要求**恰好等於 1**。其他取值語意「未决」。
- @source 0x004154fa `cmp byte ptr [0x497159], 0`、0x00415501 `je 0x415457`。`0x497159` 由設定檔 `RICH4.CFG` 解析而來：@source 0x00411e93 `push 0x463764`（＝`"rb"`）、0x00411e98 `push 0x463767`（＝`"RICH4.CFG"`）、0x00411e9d `call 0x4573bf`、0x00411eb0 `push 0x497158`、0x00411eb5 `call 0x4576d0`（讀 0x10 位元組）、0x00411ec2 `push 0x497168`、0x00411ec7 `call 0x4576d0`（讀 0x38 位元組）；檔案不存在時 @source 0x00411edc `mov byte ptr [0x497158], ah`(ah=1)、0x00411ee2 `mov byte ptr [0x497159], ah`。即設定檔開關位元組（哪一項「未决」）。

**資源与音频** —
| 對象 | 指令 | 落點 |
|---|---|---|
| 音效組 | @source 0x00415507 `push 0x47509f`、0x0041550c `call 0x454176` | effect.mkf（`[0x48a058]`，@source 0x00454192 `mov edi,dword ptr [0x48a058]`）的 id `0x13,0x14,0x15`（表 `0x47509f`，8 位元組一筆 `{id,handle}`，`0x4750b7` 為 `-1` 終止） |
| 動畫 FLIC | @source 0x00415518 `push 0x4e`、0x0041551a `mov ebp,dword ptr [0x48a05c]`、0x00415521 `call 0x450441`、0x00415529 `mov dword ptr [0x48bd3c], eax` | panel.mkf id `0x4e`（解出檔開頭 `a6 12 08 00 | 12 af | 14 00 | 80 02 | e0 01 | 08 00 | 03 00` ＝ FLIC：size=0x812a6、magic=`0xaf12`、frames=20、寬 640、高 480、8bpp） |
| HUD 數字 | @source 0x00415532 `push 0x4f`、0x0041553a `call 0x450441`、0x00415542 `mov dword ptr [0x48bcd0], eax` | panel.mkf id `0x4f` |
| 氣球＋背景 | @source 0x0041554b `push 0x5b`、0x00415554 `call 0x450441`、0x0041555c `mov dword ptr [0x48bd34], eax` | panel.mkf id `0x5b` |
| 背景音樂 | @source 0x00415595 `push 0xb`、0x00415597 `call 0x4549cf` | 曲目 id `0x0b` |
| 音效播放點 | @source 0x00413077 `push 0x47509f`（氣球生成，id `0x13`）、@source 0x00414f0f `push 0x4750a7`（點空，id `0x14`）、@source 0x00414e0e `push 0x4750af`（點爆，id `0x15`） | 皆 `call 0x4542ce`（`(record,0)`，@source 0x004542d8 `mov ecx,dword ptr [eax]`、0x004542db `mov ebx,dword ptr [eax+4]`、0x004542df `call 0x4540d8`） |
| 收尾 | @source 0x004155b2 `push 0x47509f`、0x004155b7 `call 0x454240`（停止並釋放音效組） | `0x454240` 先判 `[ebx]==-1` 再 `call dword ptr [edx+0x48]` |

**玩法规则（逐步）** —
1. 入口初始化：@source 0x00415561 `push 0x80`、0x00415566 `push 0`、0x00415568 `push 0x48bc44`、0x0041556d `call 0x456f60`（`_memset(0x48bc44,0,0x80)`：**16 槽 × 8 位元組的物件陣列**，`0x48bc44`..`0x48bcc3`）。
2. @source 0x00415575 `xor ecx,ecx`＋0x00415577 `mov dword ptr [0x48bcec], ecx`（分數＝0）；@source 0x0041557d `xor bl,bl`＋0x0041557f `mov byte ptr [0x48bd58], bl`（狀態＝0）；@source 0x0041558d `xor ebx,ebx`＋0x0041558f `mov dword ptr [0x48bcc8], ecx`（速度倍率＝0，見步驟 9）；0x00415585 `xor bh,bh`＋0x00415587 `mov byte ptr [0x48bd59], bh`（凍結計數＝0）。
3. @source 0x0041559f `push ebx`（0）、0x004155a0 `push 0x414bbc`、0x004155a5 `call 0x4018e7` → 進入訊息迴圈。`0x4018e7`：@source 0x004018eb `mov edx,dword ptr [0x46cad8]`、0x004018f1 `inc edx`、0x004018f8 `mov eax,edx`、0x004018fa `mov edx,dword ptr [esp + 0x24]`、0x004018fe `mov dword ptr [eax*4 + 0x48a010], edx`（註冊 WndProc）、0x00401909 `push ecx`、0x0040190c `push 0x401`、0x00401918 `call dword ptr cs:[0x462310]`（PostMessage）、迴圈 @source 0x0040192c `call dword ptr cs:[0x46230c]`(PeekMessageA)、0x00401937 `cmp dword ptr [esp + 4], 0x402`、0x0040193f `je 0x401957`（收到 0x402 即返回）。定時器 id 即 `[0x46cad8]`。
4. WndProc `0x00414bbc`（@source 0x00414bbc `push ebx`／0x00414bbd `push esi`／0x00414bbe `push edi`／0x00414bbf `push ebp`；@source 0x00414bc0 `mov ebx,dword ptr [esp + 0x14]`＝hwnd、0x00414bc4 `mov eax,dword ptr [esp + 0x18]`＝msg、0x00414bc8 `mov edx,dword ptr [esp + 0x20]`＝lParam）。
   訊息映射（@source 0x00414bcc `cmp eax,0x201` 起的比較樹）：
   - `0x401` → @source 0x00414c1d：@source 0x00414c1d `mov dword ptr [0x48bd2c], 0x96`（可玩時間＝150 tick）、0x00414c27 `mov dword ptr [0x48bd84], 0x63`（開場倒數＝99）、0x00414c31 `call 0x4146ee`（畫背景＋HUD）、@source 0x00414c38 `push 0x64`（100 ms）、0x00414c3a `mov ebp,dword ptr [0x46cad8]`、0x00414c42 `call dword ptr cs:[0x462324]`（SetTimer）、0x00414c49 `mov dword ptr [0x48bd80], eax`、@source 0x00414c4e `push 0`×2＋0x00414c53 `call dword ptr cs:[0x4622f8]`（InvalidateRect(hwnd,0,0)）。
   - `0xf` WM_PAINT → @source 0x00414f6b：@source 0x00414f6d `call 0x40235d`(BeginPaint)、0x00414f8f `call dword ptr [edx + 0x1c]`（把後備表面 `[0x48a0e0]` Blt 到螢幕）、0x00414f94 `call 0x402250`(EndPaint)、@source 0x00414f9f `call dword ptr cs:[0x462340]`(ValidateRect)、@source 0x00414fa6 `cmp dword ptr [0x48bd84], 0x63`、0x00414fad `jne`、0x00414fb3 `mov dword ptr [0x48bd84], 5`（第一次繪製把 99 改成 5 → 開場倒數 5×100 ms＝0.5 s）。
   - `0x113` WM_TIMER → @source 0x00414c69：@source 0x00414c69 `cmp byte ptr [0x46cb01], 0`、0x00414c70 `je`（音效子系統關閉則不更新）、@source 0x00414c7a `cmp eax,dword ptr [0x46cad8]`、0x00414c80 `jne`（不是本定時器則返回）。
     倒數期：@source 0x00414c86 `mov ecx,dword ptr [0x48bd84]`、0x00414c93 `mov dword ptr [0x48bd84], edx`、0x00414c9b `jne 0x414a4a`（倒數中直接返回，不更新世界）；歸零時 @source 0x00414ca1..0x00414ca9 `push 0x405`＋`call dword ptr cs:[0x462310]` → PostMessage(hwnd,0x405,0,0)。
     正式遊玩：@source 0x00414cc9 `mov esi,dword ptr [0x48bd2c]`、0x00414cd3 `lea edi,[esi - 1]`、0x00414cd6 `mov dword ptr [0x48bd2c], edi`、0x00414cde `jne 0x414ce7`、0x00414ce0 `mov byte ptr [0x48bd58], 1`（時間到）；@source 0x00414ce7 `push 2`＋0x00414ce9 `call 0x413f07`（HUD）；@source 0x00414cf1 `call 0x412f6f`（世界更新＋繪製）；@source 0x00414cf6 `cmp byte ptr [0x48bd58], 2`、0x00414cfd `jne 0x414a4a`。
     收尾：@source 0x00414d03 `push 0`＋0x00414d05 `call 0x402460`、0x00414d0d `push 0`／0x00414d0f `push 1`／0x00414d11 `push 0x29`＋0x00414d13 `call 0x4021f8`、@source 0x00414d1b `mov eax,dword ptr [0x48bd80]`＋0x00414d22 `call dword ptr cs:[0x4622fc]`（KillTimer(hwnd,[0x48bd80])）、0x00414d29 `push 1`＋0x00414d2b `call 0x4024a9`、@source 0x00414d33 `call 0x414789`（把分數排成文字並貼出）、@source 0x00414d38 `push 0x7d0`＋0x00414d3d `call 0x45285e`（暫停 2000 ms 並抽訊息）、@source 0x00414d45 `push 0`＋0x00414d47 `call 0x401966`（PostMessage(main,0x402,0,0) 結束訊息迴圈）。
   - `0x201`／`0x203`（WM_LBUTTONDOWN／WM_LBUTTONDBLCLK）→ @source 0x00414d9f：@source 0x00414d9f `cmp byte ptr [0x48bd58], 2`、0x00414da6 `je`（已結束不處理）、@source 0x00414dac `cmp dword ptr [0x48bd84], 0`、0x00414db3 `jne`（倒數中不處理）；@source 0x00414db9 `xor edi,edi`、0x00414dbb `mov di,dx`（游標 x）、0x00414dbe `mov eax,edx`、0x00414dc0 `shr eax,0x10`、0x00414dc3 `and eax,0xffff`、0x00414dc8 `movzx ebp,ax`（游標 y）。
   - `0x405` → @source 0x00414d51：@source 0x00414d53..0x00414d5f `push 1`、`push 0`、`push 0`、`push dword ptr [0x48bd3c]`、0x00414d60 `call 0x45144f` → 播放 `0x4e` 的 640×480 FLIC；之後 @source 0x00414d68..0x00414d82 再 Blt 一次，@source 0x00414d85 `push 5`／0x00414d87 `push 3`／0x00414d89 `push 9`＋0x00414d8b `call 0x4021f8`、@source 0x00414d93 `push 1`＋0x00414d95 `call 0x402460`。
   - 其他（含 `0x100`/`0x101`/`0x200`）→ @source 0x00414fc2 `push edx`、0x00414fc3 `mov edx,dword ptr [esp + 0x20]`、0x00414fc7 `push edx`、0x00414fc8 `jmp 0x414b94`；@source 0x00414b94 `push eax`、0x00414b95 `push ebx`、0x00414b96 `call dword ptr cs:[0x4622d8]`（DefWindowProcA）。**鍵盤完全交給 DefWindowProc，本遊戲只吃滑鼠左鍵。**
5. 世界更新 `0x00412f6f`（由 WM_TIMER 每 100 ms 呼叫一次；函式範圍 `0x00412f6f`..`0x00413230`）：
   - 先鎖後備表面並鋪背景：@source 0x00412fa5 `mov eax,dword ptr [0x48a08c]`、0x00412fc0 `mov eax,dword ptr [0x48bd34]`、0x00412fc5 `add eax,0xc`、0x00412fce `call 0x4562cc`（以 panel `0x5b` 的第 0 張圖填滿）。
   - 16 槽迴圈 @source 0x00413183 `inc ebp`、0x00413184 `cmp ebp,0x10`。
   - 空格生成（僅在 `[0x48bd58]==0`，@source 0x0041319c `cmp byte ptr [0x48bd58], 0`、0x004131a3 `jne`）：
     @source 0x004131a5 `call 0x456f2d`（rand）、0x004131ac `mov ecx,0x3e8`（1000）、0x004131b4 `idiv ecx`、@source 0x004131b6 `cmp edx,0x14`、0x004131b9 `jge 0x412fe1`；`edx<20` 時 @source 0x004131bf `sar edx,2`＋0x004131c2 `mov dword ptr [esp + 0x40], edx`（狀態 = rand()%1000>>2，取值 0..4）。
     `edx>=20` 時 @source 0x00412fe1 `cmp edx,0x1c`、0x00412fe4 `jge 0x412ff8`；`20..27` → @source 0x00412fe6 `mov eax,0x1b`、0x00412feb `sub eax,edx`、0x00412fed `sar eax,1`、0x00412fef `add eax,5`（狀態 5..8）；`28..29` → @source 0x00412ff8 `cmp edx,0x1e`、0x00412ffb `jge 0x413183`（放棄生成），否則 @source 0x00413001 `call 0x456f2d`、0x00413008 `mov ecx,0xa`、0x00413010 `idiv ecx`、0x00413014 `mov al,byte ptr [edx + 0x475039]`（**特殊氣球表**）；`>=30` 放棄。
     @source 0x0041301c `cmp dword ptr [esp + 0x40], -1`、0x00413021 `je`（放棄）。
     找空跑道：@source 0x00413027 `mov ebx,0x28`（x 起點 40）、0x0041305b `add ebx,0x50`（每 80 一跑道）、0x0041305e `cmp ebx,0x280`（到 640 為止 → 8 條：40/120/200/280/360/440/520/600），對每條跑道 @source 0x0041304b `cmp word ptr [eax + 0x48bc46], 0x12c`（該跑道下方 y>300 已有物件則跳過）；@source 0x00413057 `mov dword ptr [esp + esi*4], ebx` 收集可用跑道。
     @source 0x0041306e `test esi,esi`、0x0041306c `je`（無跑道放棄）；@source 0x00413074 `push 0`＋0x00413076 `push 0x47509f`＋0x0041307b `call 0x4542ce`（生成音效）；@source 0x00413083 `call 0x456f2d`、0x0041308d `idiv esi`、0x0041308f `mov dx,word ptr [esp + edx*4]`（隨機挑一條跑道）；@source 0x00413093 `mov word ptr [ebp*8 + 0x48bc44], dx`（x）、0x0041309b `mov word ptr [ebp*8 + 0x48bc46], 0x1a4`（y=420 由下往上生）、0x004130a9 `mov word ptr [ebp*8 + 0x48bc48], dx`（狀態）。
   - 既有物件（@source 0x00412fdc `jmp 0x413189` → 0x0041318e `cmp word ptr [eax + 0x48bc44], 0`、0x00413196 `jne 0x4130b6`）：
     上升：@source 0x004130b6 `test byte ptr [eax + 0x48bc48], 0xf0`（高位元組非 0 = 爆破中，見下）；@source 0x004130de `cmp byte ptr [0x48bd59], 0`、0x004130e5 `jne 0x41311b`（凍結中不動）；@source 0x004130e7 `movsx eax,word ptr [eax + 0x48bc48]`＋0x004130ee `mov al,byte ptr [eax + 0x475004]`（**每狀態上升速度表**）；倍率 @source 0x004130f9 `mov edx,dword ptr [0x48bcc8]`、0x004130ff `cmp edx,-1`、0x00413102 `jl`／0x00413104 `jle 0x41310d`（`-1` → @source 0x0041310d `add eax,eax` 速度 ×2）／0x00413106 `cmp edx,1`、0x00413109 `je 0x413111`（`+1` → @source 0x00413111 `sar eax,1` 速度 ÷2）；@source 0x00413113 `sub word ptr [ebp*8 + 0x48bc46], ax`（y 減速 → 上升）。
     繪製：@source 0x00413130 `mov ax,word ptr [ebx + 0x48bc48]`、0x00413137 `xor ah,ah`、0x00413139 `and al,0xf`、0x0041313c `lea edx,[eax + 1]`、0x00413148 `shl edx,2`（(frame+1)×12）、0x0041314b `mov eax,dword ptr [0x48bd34]`、0x00413150 `add eax,0xc`、0x0041315b `call 0x4562a5`；@source 0x00413163 `test eax,eax`、0x00413165 `je`、0x00413167 `xor esi,esi`、0x00413169 `mov word ptr [ebx + 0x48bc44], si`（畫出界 → 移除）。
     爆破動畫：@source 0x004130bf `sub word ptr [eax + 0x48bc48], 0x10`、0x004130c7 `test byte ptr [eax + 0x48bc48], 0xf0`、0x004130ce `jne 0x41311b`、0x004130d0 `xor edx,edx`、0x004130d2 `mov word ptr [eax + 0x48bc44], dx`（高位元組歸零 → 移除）。
   - 全部跑完後 @source 0x00413212 `cmp dword ptr [esp + 0x3c], 0`、0x00413217 `jne 0x413229`、0x00413219 `cmp byte ptr [0x48bd58], 1`、0x00413220 `jne`、0x00413222 `mov byte ptr [0x48bd58], 2`（時間到且畫面上已無物件 → 進結算）。
6. 點擊判定（WndProc，`0x00414dcd`..`0x00414f20`）：
   - 迴圈 @source 0x00414f1c `inc ebx`、0x00414f1d `cmp ebx,0x10`、0x00414f26 `mov eax,ebx`、0x00414f28 `shl eax,3`。
   - 跳過：@source 0x00414f2b `cmp word ptr [eax + 0x48bc44], 0`、0x00414f33 `je`（空槽）；@source 0x00414f35 `test byte ptr [eax + 0x48bc48], 0xf0`、0x00414f3c `jne`（爆破中不可點）。
   - 命中框：@source 0x00414f3e `cmp word ptr [eax + 0x48bc48], 6`、0x00414f46 `jge 0x414dd2`。
     `state>=6`（第 7..12 號圖）：@source 0x00414dd2 `movsx edx,word ptr [eax + 0x48bc44]`、0x00414dd9 `lea ecx,[edx - 0x12]`、0x00414ddc `add edx,0x12`、0x00414ddf `movsx eax,word ptr [eax + 0x48bc46]`、0x00414de6 `lea esi,[eax - 0x1a]`、0x00414de9 `add eax,0x1a`（±18 × ±26）。
     `state<6`：@source 0x00414f4c..0x00414f63 `lea ecx,[edx - 0x16]`／`add edx,0x16`／`lea esi,[eax - 0x1e]`／`add eax,0x1e`（±22 × ±30，大型氣球框較大）。
     比對：@source 0x00414dec `cmp edi,ecx`、0x00414df4 `cmp edi,edx`、0x00414dfc `cmp ebp,esi`、0x00414e04 `cmp ebp,eax`。
   - 命中：@source 0x00414e0e `push 0x4750af`＋0x00414e13 `call 0x4542ce`；取狀態 @source 0x00414e1b `mov dx,word ptr [ebx*8 + 0x48bc48]`，分派：`==9` → @source 0x00414e40 `mov eax,dword ptr [0x48bcec]`、0x00414e45 `add eax,eax`、0x00414e47 `mov dword ptr [0x48bcec], eax`（分數 ×2）；`==10` → @source 0x00414e51 `sar dword ptr [0x48bcec], 1`（分數 ÷2）；`==11` → @source 0x00414e5c `xor dh,dh`、0x00414e5e `mov byte ptr [0x48bd59], dh`、0x00414e64 `xor ecx,ecx`、0x00414e66 `mov dword ptr [0x48bcc8], ecx`、0x00414e6c `call 0x456f2d`、0x00414e73 `mov ecx,6`、0x00414e7b `idiv ecx`、0x00414e80 `ja 0x414ef7`、0x00414e86 `jmp dword ptr [edx*4 + 0x414ba4]`（6 路隨機）；其他 → @source 0x00414ece `movsx eax,word ptr [ebx*8 + 0x48bc48]`、0x00414ed6 `inc eax`、0x00414ed7 `mov edx,dword ptr [0x48bcec]`、0x00414edd `add edx,eax`、0x00414edf `mov dword ptr [0x48bcec], edx`（加 `state+1`），上限 @source 0x00414ee5 `cmp edx,0x3e8`、0x00414eeb `jl`、0x00414eed `mov dword ptr [0x48bcec], 0x3e7`。
   - 命中後續：@source 0x00414ef7 `push 1`＋0x00414ef9 `call 0x413f07`；@source 0x00414f01 `mov word ptr [ebx*8 + 0x48bc48], 0x3c`（狀態改為爆破：高位元組 3、低位元組 0xc＝第 13 張爆破圖）。
   - 未命中：@source 0x00414f0d `push 0`＋0x00414f0f `push 0x4750a7`＋0x00414f14 `call 0x4542ce`。
7. 特殊氣球「?」的 6 路跳表 `0x00414ba4`（@source 0x00414e86 `jmp dword ptr [edx*4 + 0x414ba4]`，`edx=rand()%6`）：
   | 索引 | 目標 | 效果 | 立即數位址 |
   |---|---|---|---|
   | 0 | `0x00414e8d` | `mov dword ptr [0x48bd2c], 1` → 剩餘時間直接砍到 1 tick（立刻結束） | @source 0x00414e8d |
   | 1 | `0x00414e99` | `mov byte ptr [0x48bd59], 0x14` → 全場氣球凍結 20 frame | @source 0x00414e99 |
   | 2 | `0x00414ea2` | `mov dword ptr [0x48bcc8], 0xffffffff` → 上升速度 ×2 | @source 0x00414ea2 |
   | 3 | `0x00414eae` | `mov dword ptr [0x48bcc8], 1` → 上升速度 ÷2 | @source 0x00414eae |
   | 4 | `0x00414eba` | `xor eax,eax`＋`jmp 0x414e47` → 分數歸 0 | @source 0x00414eba |
   | 5 | `0x00414ebe` | `mov esi,dword ptr [0x48bcec]`、`add esi,esi`、`mov dword ptr [0x48bcec], esi` → 分數 ×2 | @source 0x00414ebe |

**胜负判定** — 沒有「對手」；只有「時間到」與「加分」。
- 時間到：@source 0x00414cde `jne 0x414ce7`＋0x00414ce0 `mov byte ptr [0x48bd58], 1`；等畫面上氣球清空（@source 0x00413217 `jne 0x413229`、0x00413219 `cmp byte ptr [0x48bd58], 1`、0x00413222 `mov byte ptr [0x48bd58], 2`）後，WndProc 在 @source 0x00414cf6 `cmp byte ptr [0x48bd58], 2` 成立時走收尾。
- 返回值：@source 0x004155ec `mov eax,dword ptr [0x48bcec]`（函式尾）→ EAX = 本局點券（0..0x3e7）。呼叫端 @source 0x0041b152 `add word ptr [ebx + 0x496b98], ax`（`ebx`＝`[0x49910c]`×0x68，見 @source 0x0041b146 `imul ebx,dword ptr [0x49910c],0x68`）把它加到玩家點券上。
- `0x496b98 == 0x496b68 + 0x30`：`0x496b68 + 0x30 = 0x496b98`（算術恆等）。該欄位確為玩家結構的 16 位元分數字：@source 0x0042d15a `imul ecx,dword ptr [esp + 0x14], 0x68`、@source 0x0042d17c `mov ax,word ptr [ecx + 0x496b98]`、@source 0x0042d187 `fild dword ptr [esp + 8]`（被當數值參與繪圖）；@source 0x0041b152 為加項。另 @source 0x0041b21e 亦在寫此欄位（同族小遊戲/事件結算）。
- 「中途炸彈」無此機制；本遊戲不會提前失敗。

**奖罚数值** （單位：點券；總分上限 0x3e7＝999）
| 項目 | 數值 | 立即數地址 |
|---|---|---|
| 一般氣球得分 | `state + 1`（＝畫在氣球上的數字 1..9） | @source 0x00414ed6 `inc eax`、0x00414edd `add edx,eax` |
| 分數上限 | 999 | @source 0x00414eed `mov dword ptr [0x48bcec], 0x3e7`（比較用 0x3e8 @source 0x00414ee5） |
| `x2` 氣球（state 9） | 分數 ×2 | @source 0x00414e45 `add eax,eax` |
| `÷2` 氣球（state 10） | 分數 ÷2 | @source 0x00414e51 `sar dword ptr [0x48bcec], 1` |
| 「?」隨機事件 | 6 選 1（見上表） | @source 0x00414e73 `mov ecx,6` |
| 上升速度表 | 狀態 0..14 → 15/15/15/15/18/18/18/24/24/24/24/18/24/18/15 | 表 `0x475004`，@source 0x004130ee `mov al,byte ptr [eax + 0x475004]` |
| 特殊氣球類型表 | `{9,9,10,10,10,10,10,11,11,11}`（rand()%10 索引） | 表 `0x475039`，@source 0x00413014 `mov al,byte ptr [edx + 0x475039]` |
| 出現機率 | 空槽每 frame：2% 生成狀態 0..4；0.8% 生成狀態 5..8；0.2% 生成特殊；其餘不生成 | @source 0x004131b6 `cmp edx,0x14`、@source 0x00412fe1 `cmp edx,0x1c`、@source 0x00412ff8 `cmp edx,0x1e` |
| 跑道 | x = 0x28 + 0x50·k（k=0..7），起點 y = 0x1a4 | @source 0x00413027 `mov ebx,0x28`、0x0041305b `add ebx,0x50`、0x0041309b `mov word ptr [ebp*8 + 0x48bc46], 0x1a4` |
| 計時 | 150 tick × 100 ms ＝ 15 s；開場倒數 5 tick ＝ 0.5 s | @source 0x00414c1d `mov dword ptr [0x48bd2c], 0x96`、0x00414c38 `push 0x64`、0x00414fb3 `mov dword ptr [0x48bd84], 5` |
| 結算暫停 | 2000 ms | @source 0x00414d38 `push 0x7d0` |
| **未遊玩 fallback** | `rand()%20 + 50`（50..69） | @source 0x0041545e `mov ebx,0x14`、0x00415466 `idiv ebx`、0x00415468 `add edx,0x32`、0x0041546b `mov dword ptr [0x48bcec], edx` |

fallback（共享區塊 `0x00415457`..`0x004154d7`，三個小遊戲共同使用）完整拆解：
- @source 0x00415457 `call 0x456f2d`（`_libc_rand`：@source 0x00456f2d `call 0x456f23`、0x00456f37 `imul edx,dword ptr [eax], 0x41c64e6d`、0x00456f3d `add edx,0x3039`、0x00456f43 `mov dword ptr [eax], edx`、0x00456f47 `shr eax,0x10`）。
- @source 0x0041545c `mov edx,eax`、0x0041545e `mov ebx,0x14`（20）、0x00415463 `sar edx,0x1f`、0x00415466 `idiv ebx`、0x00415468 `add edx,0x32`（+50）、0x0041546b `mov dword ptr [0x48bcec], edx` → 分數＝rand()%20+50。
- @source 0x00415471 `push edx`、0x00415472 `push 0x463797`（＝`"得點券%d點"`，BIG5）、0x00415477 `lea eax,[esp + 8]`、0x0041547c `call 0x457110`（sprintf）。
- @source 0x00415484 `push 0x7d0`（2000）、0x00415489 `lea eax,[esp + 4]`、0x0041548e `call 0x440cac` → 參數為 `(文字緩衝, 0x7d0)`；`0x440cac` 內 @source 0x00440cef `test esi, 0x80000000`、0x00440cf7 `and esi, 0x7fffffff`、@source 0x00440d06 `push 1`／0x00440d08 `push 3`／0x00440d0a `push 0x101010`／0x00440d0f `push 0xf0f0f0`／0x00440d14 `push 0x10`＋0x00440d16 `call 0x44f9d8`（設定文字色/底色/字型）→「顯示訊息框」；`0x7d0`「推断」為顯示時長（ms），同值在 @source 0x00414d38／0x004152?? 由 `0x45285e`（@source 0x004528ae `cmp ebx,edi`／0x004528b0 `jb 0x452875`，用 `timeGetTime` 計時的訊息泵延遲）當作 2000 ms 使用。
- 之後 @source 0x00415496 `imul eax,dword ptr [0x49910c], 0x68`、0x0041549f `mov dl,byte ptr [eax + 0x496b7b]`（當前玩家角色編號）、0x004154a5..0x004154ac（×12）、0x004154b1 `shl ebx,3`（×96）、0x004154b4 `add ebx,eax`（角色編號 ×108）、@source 0x004154b6 `call 0x456f2d`、0x004154bb `and eax,1`、@source 0x004154be `mov esi,dword ptr [ebx + eax*4 + 0x48084a]`（每個角色 27 條台詞的字串指標表，例：`0x466bd8`＝`"#1050別忌妒我！"`）、@source 0x004154cf `call 0x44ef41`（`(playerIndex,0,字串)`：@source 0x0044ef74 `imul eax,dword ptr [esp + 0x24], 0x68`、0x0044ef5d `mov dword ptr [0x4762c8], ebx` 去重後顯示該角色台詞）。
- @source 0x004154d7 `jmp 0x4155ec` → @source 0x004155ec `mov eax,dword ptr [0x48bcec]` 返回 50..69。

**随机数使用点**（`call 0x456f2d` = `_libc_rand`，LCG `seed*0x41C64E6D+0x3039` 取 >>16）
| VA | 取模/遮罩 | 選什麼 |
|---|---|---|
| @source 0x00414e6c | `mov ecx,6`＋`idiv ecx` | 「?」氣球的 6 路隨機事件（跳表 `0x414ba4`） |
| @source 0x00415457（共享 fallback） | `mov ebx,0x14` | 未遊玩時 `rand()%20+50` 的分數 |
| @source 0x004154b6（共享 fallback） | `and eax,1` | 二選一角色台詞 |
| @source 0x004131a5（更新 `0x412f6f`） | `mov ecx,0x3e8`＋`sar edx,2` | 生成判定與狀態 0..4 |
| @source 0x00413083（更新 `0x412f6f`） | `idiv esi`（esi=可用跑道數） | 挑一條跑道 |
| @source 0x00413001（更新 `0x412f6f`） | `mov ecx,0xa` | 由 `0x475039` 表挑特殊氣球類型（9/10/11） |

（`0x004131a5`／`0x00413083`／`0x00413001` 全部落在更新函式 `0x00412f6f` 內；A 的入口函式 `0x004154dc` 本身沒有 `call 0x456f2d`，其 WndProc `0x00414bbc` 內只有 `0x00414e6c` 一處。）

**动画与输入接线点** —
- IAT（以 `rich4dis.py` 讀 `.idata` 的 hint/name 確認）：
  | slot | 函式 | 本遊戲用在哪 |
  |---|---|---|
  | `cs:[0x462324]` | `SetTimer` | @source 0x00414c42（間隔 `0x64`＝100 ms 由 @source 0x00414c38 `push 0x64`） |
  | `cs:[0x4622fc]` | `KillTimer` | @source 0x00414d22 |
  | `cs:[0x4622f8]` | `InvalidateRect` | @source 0x00414c53 |
  | `cs:[0x462340]` | `ValidateRect` | @source 0x00414f9f |
  | `cs:[0x462310]` | `PostMessageA` | @source 0x00414ca9（`push 0x405`）、`0x401966`（`push 0x402`） |
  | `cs:[0x4622d8]` | `DefWindowProcA` | @source 0x00414b96（所有未處理訊息） |
  | `cs:[0x46230c]` | `PeekMessageA` | @source 0x0040192c |
  | `cs:[0x4622e0]` | `DispatchMessageA` | @source 0x0040194e |
  | `cs:[0x462334]` | `TranslateMessage` | @source 0x00401944 |
  | `cs:[0x46246c]` | `timeGetTime` | @source 0x0045286c（2000 ms 延遲） |
  | `cs:[0x4622ec]` | `GetCursorPos` | @source 0x004151af（僅 B 使用） |
  | `cs:[0x46231c]` | `SetCursorPos` | @source 0x0041361c（僅 B 使用） |
- 其他關鍵 callee：`_Wait_0402_Message` `0x4018e7`（@source 0x004155a5）；`_read_mkf` `0x450441`（@source 0x00415521 等）；`_rich4_init_sound_effect_info` `0x454176`（@source 0x0041550c）；`0x454240` 停音效（@source 0x004155b7）；`0x4549cf` 播 BGM（@source 0x00415597）；`0x454bcc` 音樂更新（@source 0x004155ad）；`_libc_free` `0x456e11`（@source 0x004155c6 / 0x004155d5 / 0x004155e4）；`_memset` `0x456f60`（@source 0x0041556d）；`0x456f2d` `_libc_rand`；`0x4542ce`／`0x4542e9` 音效播放／停止；`0x4562a5`／`0x4562cc` 貼圖；`0x4563f5` 貼圖（=@source 0x004563fe `push dword ptr [ebp + 0xc]` … @source 0x0045640e `call 0x455b3a`，參數 `(surface, 640, 480, 圖集, x, y)`）；`0x45144f` FLIC 播放（@source 0x0045146c `call 0x450ced`）；`0x4146ee` 畫背景＋HUD；`0x413f07` HUD（@source 0x00413f35 `call 0x457110` 以 `0x463788`＝`"%03d"` 格式化 `[0x48bd2c]`）；`0x414789` 結算文字（@source 0x00414796 `push 0x46377c`，@source 0x004147a0 `call 0x457110` 格式化 `[0x48bcec]`）；`0x4147b5`..`0x4147c6` 置中計算（`mov esi,0x161`）；`0x40235d`/`0x402250` BeginPaint/EndPaint；`0x413f07`；`0x4021f8`、`0x402460`、`0x4024a9`、`0x401966`。

**汇编摘录**
```asm
004154dc  push     ebx
004154e6  imul     eax, dword ptr [0x49910c], 0x68
004154ed  cmp      byte ptr [eax + 0x496b7d], 1
004154f4  jne      0x415457
004154fa  cmp      byte ptr [0x497159], 0
00415501  je       0x415457
00415507  push     0x47509f
0041550c  call     0x454176
00415518  push     0x4e
00415521  call     0x450441
00415529  mov      dword ptr [0x48bd3c], eax
00415532  push     0x4f
0041553a  call     0x450441
00415542  mov      dword ptr [0x48bcd0], eax
0041554b  push     0x5b
00415554  call     0x450441
0041555c  mov      dword ptr [0x48bd34], eax
00415561  push     0x80
00415568  push     0x48bc44
0041556d  call     0x456f60
00415595  push     0xb
00415597  call     0x4549cf
004155a0  push     0x414bbc
004155a5  call     0x4018e7
004155ec  mov      eax, dword ptr [0x48bcec]
004155fb  ret
```
```asm
0041b15e  imul     ebx, dword ptr [0x49910c], 0x68
0041b165  call     0x4154dc
0041b152  add      word ptr [ebx + 0x496b98], ax
0041985b  mov      ebx, dword ptr [eax + 0x24]
0041985e  and      ebx, 0xff
00419873  cmp      byte ptr [eax + 0x496b9f], 0
00419889  cmp      ebx, 0x10
004198b2  jmp      dword ptr [ebx*4 + 0x4197e9]
```
```asm
00414c1d  mov      dword ptr [0x48bd2c], 0x96
00414c27  mov      dword ptr [0x48bd84], 0x63
00414c38  push     0x64
00414c42  call     dword ptr cs:[0x462324]
00414fad  jne      0x414a4a
00414fb3  mov      dword ptr [0x48bd84], 5
00414cc9  mov      esi, dword ptr [0x48bd2c]
00414ce0  mov      byte ptr [0x48bd58], 1
00414ce9  call     0x413f07
00414cf1  call     0x412f6f
00414f3e  cmp      word ptr [eax + 0x48bc48], 6
00414e0e  push     0x4750af
00414e13  call     0x4542ce
00414e1b  mov      dx, word ptr [ebx*8 + 0x48bc48]
00414e45  add      eax, eax
00414e51  sar      dword ptr [0x48bcec], 1
00414e6c  call     0x456f2d
00414e73  mov      ecx, 6
00414e86  jmp      dword ptr [edx*4 + 0x414ba4]
00414ece  movsx    eax, word ptr [ebx*8 + 0x48bc48]
00414ed6  inc      eax
00414edd  add      edx, eax
00414ee5  cmp      edx, 0x3e8
00414eed  mov      dword ptr [0x48bcec], 0x3e7
00414f01  mov      word ptr [ebx*8 + 0x48bc48], 0x3c
004131a5  call     0x456f2d
004131a6  mov      ecx, 0x3e8
004131b6  cmp      edx, 0x14
00413014  mov      al, byte ptr [edx + 0x475039]
00413027  mov      ebx, 0x28
0041309b  mov      word ptr [ebp*8 + 0x48bc46], 0x1a4
004130ee  mov      al, byte ptr [eax + 0x475004]
00413113  sub      word ptr [ebp*8 + 0x48bc46], ax
```
```asm
00415457  call     0x456f2d
0041545e  mov      ebx, 0x14
00415466  idiv     ebx
00415468  add      edx, 0x32
0041546b  mov      dword ptr [0x48bcec], edx
00415472  push     0x463797
0041548e  call     0x440cac
004154be  mov      esi, dword ptr [ebx + eax*4 + 0x48084a]
004154cf  call     0x44ef41
```

**未决**
- `0x48bc4a`（物件記錄第 4 個 word 的第 1 位元組）在 A 的所有程式路徑中未被讀寫 → 未使用。
- panel.mkf `0x4e` 這支 FLIC 究竟是「開場動畫」還是「結算動畫」：它由 `0x405` 訊息觸發，而 `0x405` 在開場倒數 `[0x48bd84]` 歸零時 Post（@source 0x00414ca9），故「推断」為開場動畫；未找到其他觸發點。
- `0x497159`（RICH4.CFG 解析出的位元組）對應哪個設定項目未知。
- `0x48bd84` 為何在第一次 WM_PAINT 由 `0x63` 改寫為 `5`（@source 0x00414fb3）的設計意圖未定。
- 玩家 `+0x15`（`0x496b7d`）除 `1` 以外的取值語意未知。
- panel.mkf `0x4f` 的第 10..19 張圖（約 60×76）在本兩函式路徑中未被引用。
- `0x48bcc8` 只有在被讀時才確定方向（`-1`→加速、`+1`→減速），原本欄位語意未知。
- `0x4562cc`／`0x4562a5` 的完整參數語意（僅知 `0x4563f5` 為 `(surface,圖集,x,y)`）。

---

### 財神爺／喜從天降（入口 VA 0x004155FC）

入口邊界（任務要求核對）：真正的函式起點是 `0x004155FC`，不是 `0x00415A6F`。
- @source 0x004155fc `push ebx`、0x004155fd `push esi`、0x004155fe `push edi`、0x004155ff `push ebp`、0x00415600 `sub esp, 0x80` → 典型入口序言。
- 最後一條指令 @source 0x0041586d `jmp 0x4155e4`（機器碼 `e9 72 fd ff ff`），跳進 A 的共用尾端 `0x004155e4`（`call 0x456e11` → `_libc_free` → `0x004155ec mov eax,dword ptr [0x48bcec]` → 收尾 `ret`）。
- 下一個函式在 @source 0x00415872 `push ebx`／0x00415873 `push esi`／0x00415874 `push edi`／0x00415875 `push ebp`／0x00415876 `sub esp, 0x10`（讀 `JUMP.MKF`，@source 0x00415879 `push 0x4637cf`，播 AVI，`ret` 在 @source 0x00415d0c）。因此 B 的可執行範圍為 `0x004155FC`..`0x00415871`。
- `0x00415A6F` 落在上面那個 JUMP.MKF 函式內部：@source 0x00415a6d `call 0x4562cc`（`0x415A6D`..`0x415A71`），`0x415A6F` 是該指令的第 3 個位元組，**不是**函式起點。
- `0x00415D31` 確實是另一個函式（@source 0x00415d31 `push ebx`／0x00415d32 `push esi`／0x00415d33 `push edi`／0x00415d34 `push ebp`／0x00415d35 `sub esp, 0x10`；其間 `0x00415D0D`..`0x00415D30` 為對齊填充），與本遊戲無關。

**触发条件与触发点** — 事件分派表 `0x004197e9`，**事件類型 = 8**。@source 0x004197e9 表項 8（slot `0x00419809`）＝ `0x0041b16c`；@source 0x0041b16c `imul ebx,dword ptr [0x49910c],0x68`、@source 0x0041b173 `call 0x4155fc`、@source 0x0041b178 `jmp 0x41b152`、@source 0x0041b152 `add word ptr [ebx + 0x496b98], ax`。分派器閘門與 A 完全共用（同一段 `0x00419837`..`0x004198b2`，見 A 節），切換變數同為 `[0x498e80]` 結構 `+0x24` 位元組。

**前置闸门** — 與 A 相同的兩道：
- @source 0x00415606 `imul eax,dword ptr [0x49910c],0x68`、0x0041560d `cmp byte ptr [eax + 0x496b7d], 1`、0x00415614 `jne 0x415457`。
- @source 0x0041561a `cmp byte ptr [0x497159], 0`、0x00415621 `je 0x415457`。
任一不成立 → 走共享 fallback（`rand()%20+50`，見 A 節）。

**资源与音频** —
| 對象 | 指令 | 落點 |
|---|---|---|
| 音效組 | @source 0x00415627 `push 0x4750bf`、0x0041562c `call 0x454176` | effect.mkf 的 id `0x16,0x17,0x18,0x0f`（表 `0x4750bf`，記錄 `0x4750bf`/`0x4750c7`/`0x4750cf`/`0x4750d7`，`0x4750df` 為 `-1`） |
| 動畫 FLIC | @source 0x00415638 `push 0x4e`、0x00415641 `call 0x450441`、0x00415649 `mov dword ptr [0x48bd3c], eax` | panel.mkf `0x4e`（與 A 共用同一支 640×480、20 幀 FLIC，見 A 節） |
| HUD 數字 | @source 0x00415652 `push 0x4f`、0x0041565a `call 0x450441`、0x00415662 `mov dword ptr [0x48bcd0], eax` | panel.mkf `0x4f` |
| 全屏背景像素 | @source 0x0041566b `push 0x5c`、0x00415674 `call 0x450441`、0x0041567c `mov dword ptr [0x48bd38], eax`；@source 0x00415725 `mov eax,dword ptr [0x48bd38]`、0x0041572a `mov dword ptr [0x47504b], eax` | panel.mkf `0x5c`（解出後為 614400 B ＝ 640×480×2 RGB555，無圖像表）。全屏繪製時 @source 0x00414755 `push 0x475043` 把 DGROUP 靜態描述子 `0x475043` 當來源傳給 `0x4563f5`；而 @source 0x0041572a `mov dword ptr [0x47504b], eax` 把 `0x5c` 的 handle 寫進該描述子的第 5 個 dword（`0x475043+8 = 0x47504b`），即該處存放 `0x5c` 的像素資料。描述子內容（DGROUP）：@source 0x00475043 起 `80 02 e0 01 00 00 00 00` ＝ 640 / 480 / 0 / 0。逐位元組解譯與 `0x455b3a` 如何取用該欄位「未决」 |
| 玩家角色圖 | @source 0x00415685 `imul eax,dword ptr [0x49910c],0x68`、0x0041568c `mov al,byte ptr [eax + 0x496b7b]`、0x00415692 `and eax,0xff`、0x00415697 `add eax,0x64`、0x004156a2 `call 0x450441`、0x004156aa `mov dword ptr [0x48bd30], eax` | panel.mkf `0x64 + 角色編號`（角色編號 = 當前玩家 `+0x13`） |
| 財神爺 | @source 0x004156b3 `push 0x5d`、0x004156bc `call 0x450441`、0x004156c4 `mov dword ptr [0x48bce4], eax` | panel.mkf `0x5d` |
| 爆炸 | @source 0x004156cd `push 0x5e`、0x004156d6 `call 0x450441`、0x004156de `mov dword ptr [0x48bcf4], eax` | panel.mkf `0x5e` |
| 掉落物 5 型 | @source 0x004156e9 `lea eax,[ebx + 0x5f]`、0x004156f4 `call 0x450441`、0x004156fc `mov dword ptr [ebx*4 + 0x48bd14], eax` | panel.mkf `0x5f`..`0x63` → `0x48bd14[0..4]` |
| 被炸動畫 | @source 0x0041570d `push 0x20e`、0x00415712 `mov eax,dword ptr [0x48a0e4]`（data.mkf）、0x00415718 `call 0x450441`、0x00415720 `mov dword ptr [0x48bce8], eax` | data.mkf id `0x20e` |
| 背景音樂 | @source 0x004157ca `push 0xa`、0x004157cc `call 0x4549cf` | 曲目 id `0x0a` |
| 音效播放點 | `0x4750bf`(id `0x16`，@source 0x00413808)、`0x4750cf`(id `0x18`，@source 0x00413817 播、@source 0x004133de 停)、`0x4750d7`(id `0x0f`，@source 0x004133e8) | 播＝`call 0x4542ce`；停＝`call 0x4542e9` |
| 收尾 | @source 0x004157e8 `push 0x4750bf`、0x004157ed `call 0x454240` | 停止並釋放 |

**玩法规则（逐步）** —
1. 初始化：@source 0x0041570d 之後 @source 0x0041572f `push 0x10`、0x00415731 `push 0`、0x00415733 `push 0x48bbb4`、0x00415738 `call 0x456f60`（`_memset(0x48bbb4,0,0x10)`＝4 個 32 位元計數器，對應 type 0..3）。
2. @source 0x00415740 `xor bl,bl`＋0x00415742 `mov byte ptr [0x48bd5a], bl`（受擊/等待旗標=0）；@source 0x00415748 `xor edx,edx`＋0x0041574a `mov dword ptr [0x48bcec], edx`（分數=0）；@source 0x00415750 `xor bh,bh`＋0x00415752 `mov byte ptr [0x48bd58], bh`（狀態=0）。
3. 幾何/狀態初值：@source 0x00415758 `mov word ptr [0x48bd4c], 0x6e`（財神所在 x=110）、0x00415761 `mov word ptr [0x48bd44], 3`（狀態機=3）、0x0041576a `mov word ptr [0x48bd46], 4`（影格=4）、0x00415773 `mov word ptr [0x48bd42], 0xffff`（爆炸計數=-1 表示未啟動）、0x0041577e `mov word ptr [0x48bd54], di`（炸彈計數=0）、0x00415785 `mov word ptr [0x48bd4e], 0x140`（玩家角色 x=320）、0x0041578e `mov word ptr [0x48bd48], di`（角色動作=0 站立）、0x00415795 `mov word ptr [0x48bd50], di`（走路動畫計數=0）、0x0041579c `mov word ptr [0x48bd56], di`（角色狀態圖=0）。
4. @source 0x004157a3 `mov eax,dword ptr [0x48bd30]`、0x004157a8 `mov eax,dword ptr [eax + 4]`、0x004157ab `sub eax,5`、0x004157ae `sar eax,1`、0x004157b0 `mov word ptr [0x48bd52], ax`（＝(角色圖高−5)/2；注意 `+4` 是角色圖集第 0 張的高度欄位，@source 0x00413412 處實測為 `+4`）。
5. @source 0x004157b6 `push 0x80`、0x004157bb `push 0`、0x004157bd `push 0x48bbc4`、0x004157c2 `call 0x456f60`（16 槽 × 8 位元組掉落物陣列）。
6. @source 0x004157d4 `push 0`、0x004157d6 `push 0x414fcd`、0x004157db `call 0x4018e7`（訊息迴圈，機制同 A）。
7. WndProc `0x00414fcd`（@source 0x00414fcd `push ebx`／0x00414fce `push edi`／0x00414fcf `push ebp`／0x00414fd0 `sub esp, 8`；@source 0x00414fd3 `mov ebx,dword ptr [esp + 0x18]`＝hwnd、0x00414fd7 `mov eax,dword ptr [esp + 0x1c]`＝msg）。
   訊息映射（@source 0x00414fdb `cmp eax,0x113` 起的比較樹）：
   - `0xf` WM_PAINT → @source 0x004151c1：@source 0x004151c8..0x004151db 把後備表面 `[0x48a0e0]` Blt 到螢幕、@source 0x004151e1 `call dword ptr cs:[0x462340]`(ValidateRect)、@source 0x004151e8 `cmp dword ptr [0x48bd8c], 0x63`、0x004151ef `jne`、0x004151f1 `mov dword ptr [0x48bd8c], 0xa`（開場倒數 99 → 10 tick）。
   - `0x401` → @source 0x0041500f：@source 0x0041500f `mov dword ptr [0x48bd2c], 0x168`（可玩時間 360 tick）、0x00415019 `mov dword ptr [0x48bd8c], 0x63`、0x00415023 `call 0x41473b`（畫背景＋跑一次更新＋HUD）、@source 0x0041502a `push 0x32`（50 ms）、0x00415034 `call dword ptr cs:[0x462324]`(SetTimer)、0x0041503b `mov dword ptr [0x48bd88], eax`、@source 0x00415045 `call dword ptr cs:[0x4622f8]`(InvalidateRect)。
   - `0x113` WM_TIMER → @source 0x00415051：@source 0x00415051 `cmp byte ptr [0x46cb01], 0`、0x00415058 `je`；@source 0x00415062 `cmp eax,dword ptr [0x46cad8]`、0x00415068 `jne`。
     倒數：[0x48bd8c] 遞減（@source 0x0041507a `mov dword ptr [0x48bd8c], ecx`、0x00415082 `jne 0x415156`）；歸零 → @source 0x00415088 `push ecx`×2＋0x0041508a `push 0x405`＋0x00415090 `call dword ptr cs:[0x462310]`(PostMessage)。
     正式遊玩：@source 0x0041509c `mov edx,dword ptr [0x48bd2c]`、0x004150a9 `mov dword ptr [0x48bd2c], ecx`、0x004150b1 `jne 0x4150ba`、0x004150b3 `mov byte ptr [0x48bd58], 1`；@source 0x004150ba `push 2`＋0x004150bc `call 0x41417e`（每 tick 先把計時器值除以 2 再畫 HUD：@source 0x0041419b `mov eax,dword ptr [0x48bd2c]`、0x004141a0 `sar eax,1`）；@source 0x004150c4 `call 0x413248`（世界更新）；@source 0x004150c9 `cmp byte ptr [0x48bd58], 2`、0x004150d0 `jne 0x415156`。
     收尾：@source 0x004150d6..0x004150de `KillTimer(hwnd,[0x48bd88])`；@source 0x004150e5 `cmp word ptr [0x48bd56], 4`、@source 0x004150ed `je 0x415135`；否則 @source 0x004150ef `xor ebx,ebx`、0x004150f1 `mov word ptr [0x48bd48], bx`、@source 0x004150f8 `mov ebp,dword ptr [0x48bcec]`，依分數分級設 `[0x48bd56]`：@source 0x004150fe `cmp ebp,0x28`、0x00415101 `jge`／0x00415103 `mov word ptr [0x48bd56], 1`（＜40）；@source 0x0041510e `cmp ebp,0x32`、0x00415113 `mov word ptr [0x48bd56], 2`（40..49）；@source 0x0041511e `cmp ebp,0x3c`、0x00415123 `mov word ptr [0x48bd56], bx`(＝0)（50..59）；@source 0x0041512c `mov word ptr [0x48bd56], 3`（≥60）。
     之後 @source 0x00415135 `call 0x41473b`、0x0041513a `call 0x414789`、@source 0x0041513f `push 0x7d0`＋0x00415144 `call 0x45285e`（2000 ms）、@source 0x0041514c `push 0`＋0x0041514e `call 0x401966`（結束訊息迴圈）。
     受擊等待：@source 0x00415156 `cmp byte ptr [0x48bd5a], 0`、0x0041515d `je 0x41517f`；@source 0x00415163 `call 0x450f04`、0x00415168 `test eax,eax`、0x0041516a `jne 0x41517f`；@source 0x00415170 `xor bh,bh`、0x00415172 `mov byte ptr [0x48bd5a], bh`、0x00415178 `mov byte ptr [0x48bd58], 2`。
   - `0x405` → @source 0x0041518a：@source 0x00415192 `mov edx,dword ptr [0x48bd3c]`＋0x00415199 `call 0x45144f`（播同一支 `0x4e` FLIC）；@source 0x004151a1 `push 0`×2＋0x004151a6 `call dword ptr cs:[0x4622f8]`(InvalidateRect)；@source 0x004151ad `mov eax,esp`＋0x004151b0 `call dword ptr cs:[0x4622ec]`(GetCursorPos)、@source 0x004151b7 `mov eax,dword ptr [esp]`、0x004151ba `mov dword ptr [0x47504f], eax`（記錄游標 x 作為下一 frame 的基準，`0x47504f` 是 DGROUP 執行期變數）。
   - 其他（含 `0x100`/`0x101`/`0x200`/`0x201`/`0x202`）→ @source 0x004151fd `mov edi,dword ptr [esp + 0x24]`、0x00415201 `push edi`、0x00415202 `mov ebp,dword ptr [esp + 0x24]`、0x00415206 `push ebp`、0x00415207 `push eax`、0x00415208 `push ebx`、0x00415209 `call dword ptr cs:[0x4622d8]`(DefWindowProcA)。**本遊戲完全不接收滑鼠/鍵盤訊息，操作靠 GetCursorPos 輪詢。**
8. 世界更新 `0x00413248`（`0x00413248`..`0x00413a49`，由 WM_TIMER 每 50 ms 呼叫）：
   - 鋪背景：@source 0x00413285..0x004132a1 `push 0x183`／`push 0x280`／…／`push 0x475043`／`call 0x4562cc`（用 `0x5c` 的 640×480 全屏像素）。
   - 玩家輸入（滑鼠游標驅動角色，僅在 `[0x48bd58]!=2` 且 `[0x48bd5a]==0`）：@source 0x004135e0 `cmp byte ptr [0x48bd58], 2`、0x004135ed `cmp byte ptr [0x48bd5a], 0`、0x004135fa `lea eax,[esp + 0x1c]`、0x004135ff `call dword ptr cs:[0x4622ec]`（GetCursorPos）。
     @source 0x00413606 `mov esi,dword ptr [0x47504f]`、0x0041360c `sub esi,dword ptr [esp + 0x1c]`；@source 0x00413610 `cmp esi,8`、0x00413613 `jle`、@source 0x0041361a `push 0`、0x0041361c `call dword ptr cs:[0x46231c]`（SetCursorPos(0,y) 把游標夾回畫面）、0x00413625 `mov dword ptr [0x47504f], ecx`（=0）；@source 0x0041362d `cmp esi,-8`、0x00413630 `jge`、@source 0x00413637 `push 0x27f`(639)＋SetCursorPos(639,y)、0x00413643 `mov dword ptr [0x47504f], 0x27f`。
     角色移動：@source 0x0041364d `movsx esi,word ptr [0x48bd4e]`、0x00413654 `sub esi,dword ptr [esp + 0x1c]`（角色 x − 游標 x）、0x00413659 `call 0x458276`（絕對值）、@source 0x00413661 `cmp eax,8`、0x00413664 `jle 0x4136c1`（差距 ≤8 不動）；@source 0x00413666 `test esi,esi`、0x00413668 `jle 0x41367d`；向左 @source 0x0041366a `mov word ptr [0x48bd48], 1`、0x00413673 `sub word ptr [0x48bd4e], 0xa`（每 frame 10 px）；向右 @source 0x0041367f `mov word ptr [0x48bd48], 2`、0x00413688 `add word ptr [0x48bd4e], 0xa`；相同 @source 0x00413692 `xor ecx,ecx`、0x00413694 `mov word ptr [0x48bd48], cx`（站立）。
     走動動畫：@source 0x004136a2 `inc ebx`、0x004136a3 `mov word ptr [0x48bd50], bx`、@source 0x004136ad `movsx eax,word ptr [0x48bd52]`、0x004136b4 `cmp edx,eax`、0x004136b8 `xor ecx,ecx`、0x004136ba `mov word ptr [0x48bd50], cx`（循環 0..(h−5)/2）。
     畫角色：@source 0x004136c1 `mov si,word ptr [0x48bd48]`、0x004136c8 `test si,si`、0x004136cb `jne 0x4136d6`、0x004136cd `movsx eax,word ptr [0x48bd56]`（站立圖）／@source 0x004136d6..0x004136ee `movsx eax,si`、`dec eax`、`imul eax,edx`、`add eax,5`、`add eax,edx`（走動圖索引）；@source 0x004136f0 `push 0x17c`(y=380)、0x004136f5 `movsx edx,word ptr [0x48bd4e]`(x)、0x0041370b `call 0x45663e`（畫 `0x48bd30`，12 位元組/圖）。
   - 財神繪製＋爆炸：@source 0x0041356e `movsx eax,word ptr [0x48bd42]`、0x00413575 `cmp eax,-1`、0x00413578 `je 0x41359b`（未啟動不畫）；@source 0x0041357a `push 0x7d`(y=125)、0x0041357c `movsx edx,word ptr [0x48bd4a]`(x)、0x00413585 `mov edx,dword ptr [0x48bcf4]`、0x00413593 `call 0x45663e`（畫爆炸圖集 `0x5e`，索引＝`[0x48bd42]`）。
     @source 0x0041359b `push 0x7e`(y=126)、0x0041359d `movsx eax,word ptr [0x48bd4c]`(x)、@source 0x004135a5 `movsx edx,word ptr [0x48bd44]`、@source 0x004135b3 `lea edx,[eax + eax]`（×6）、@source 0x004135b6 `movsx eax,word ptr [0x48bd46]`、@source 0x004135bd `mov al,byte ptr [edx + eax + 0x475015]`（動畫表：狀態×6＋影格）、@source 0x004135ca `mov ebx,dword ptr [0x48bce4]`（財神圖集 `0x5d`）、0x004135d8 `call 0x45663e`。
   - 財神動作狀態機（跳表 `0x00413234`，@source 0x0041386a `mov ax,word ptr [0x48bd44]`、0x00413870 `cmp ax,4`、0x00413874 `ja 0x413a2b`、0x0041387f `jmp dword ptr [eax*4 + 0x413234]`；表項：0→`0x413886`、1→`0x413a2b`、2→`0x413934`、3→`0x413964`、4→`0x413986`）：
     - 狀態 0（向右走並投放）：@source 0x00413886 `mov bx,word ptr [0x48bd46]`、0x0041388d `cmp bx,5`、0x00413893 `movsx eax,bx`、0x00413896 `movsx edx,word ptr [0x48bd40]`、0x0041389d `cmp eax,edx`、0x0041389f `jne 0x4138b3`、@source 0x004138a1 `push 0`、0x004138a3 `movsx eax,word ptr [0x48bd4c]`、0x004138ab `call 0x4123d7`（投放）；@source 0x004138b3 `inc word ptr [0x48bd46]`、0x004138ba `add word ptr [0x48bd4c], 0xc`（每 frame 右移 12 px）。
       走完 6 格後（@source 0x004138c7 `cmp word ptr [0x48bd4c], 0x140`）：若 x>320 且 @source 0x004138d2 `call 0x456f2d`、0x004138d9 `mov ecx,4`、0x004138e1 `idiv ecx`、0x004138e3 `test edx,edx`、0x004138e5 `je 0x4138f2`，或 @source 0x004138e7 `cmp word ptr [0x48bd4c], 0x212`(530) 相等 → @source 0x004138f2 `mov word ptr [0x48bd44], 2`（轉攻擊）；否則 @source 0x004138fd `call 0x456f2d`、0x00413904 `mov ecx,5`、0x0041390c `idiv ecx`、0x0041390e `mov word ptr [0x48bd40], dx`（下一次投放的影格 rand()%5）、0x00413917 `mov word ptr [0x48bd44], di`(0)、0x0041391e `add word ptr [0x48bd4c], 0xc`。
     - 狀態 2（攻擊）：@source 0x00413934 `mov si,word ptr [0x48bd46]`、0x0041393b `inc esi`、0x00413943 `cmp si,5`、0x00413947 `jne`、@source 0x0041394d `mov word ptr [0x48bd44], 4`（轉向左走）、0x00413958 `mov word ptr [0x48bd46], dx`(0)。
     - 狀態 3（舉袋）：@source 0x00413964 `mov ax,word ptr [0x48bd46]`、0x0041396a `inc eax`、0x00413971 `cmp ax,5`、0x0041397b `xor ebx,ebx`、0x0041397d `mov word ptr [0x48bd44], bx`（回狀態 0）。
     - 狀態 4（向左走並投放，鏡像）：@source 0x00413986 `mov cx,word ptr [0x48bd46]`、0x00413996 `movsx eax,word ptr [0x48bd40]`、0x004139a1 `push 0`、0x004139ab `call 0x4123d7`、0x004139ba `sub word ptr [0x48bd4c], 0xc`；@source 0x004139c4 `cmp word ptr [0x48bd4c], 0x140`、0x004139cd `jge 0x4139e4`、0x004139cf `call 0x456f2d`、0x004139d6 `mov ecx,4`、0x004139e0 `test edx,edx`、0x004139e2 `je 0x4139ee`；@source 0x004139e4 `cmp word ptr [0x48bd4c], 0x6e`(110)、0x004139ec `jne 0x4139f9` → @source 0x004139ee `mov word ptr [0x48bd44], 3`；否則 @source 0x004139f9 `call 0x456f2d`、0x00413a00 `mov ecx,5`、0x00413a0a `mov word ptr [0x48bd40], dx`、0x00413a11 `mov word ptr [0x48bd44], 4`、0x00413a1a `sub word ptr [0x48bd4c], 0xc`。
     - 收尾：@source 0x00413a2b `cmp dword ptr [esp + 0x30], 0`、0x00413a30 `jne 0x413a42`、0x00413a32 `cmp byte ptr [0x48bd58], 1`、0x00413a39 `jne`、0x00413a3b `mov byte ptr [0x48bd58], 2`（時間到且畫面上無掉落物 → 進結算）。
   - 爆炸/定時投放：@source 0x0041374b `movsx eax,word ptr [0x48bd42]`、0x00413752 `cmp eax,-1`、0x00413755 `jne 0x4137e8`；未啟動時若「財神已走過中線」且 @source 0x0041378d `call 0x4123ba`（@source 0x004123ba `call 0x456f2d`、0x004123c1 `mov ecx,0xa`、0x004123c9 `idiv ecx`、0x004123cb `cmp edx,7`、0x004123ce `setl al`：`rand()%10 < 7`）成立且 `[0x48bd58]==0` → @source 0x004137a7 `call 0x456f2d`、0x004137ae `mov ecx,0x8c`(140)、0x004137b6 `idiv ecx`、0x004137ba `mov word ptr [0x48bd42], bx`(0)、@source 0x004137c1 `movsx eax,word ptr [0x48bd4c]`、0x004137c8 `sub eax,0x140`、0x004137cf `jle 0x4137e0`、@source 0x004137d1 `add edx,0xa0`(160)／@source 0x004137e0 `add edx,0x168`(360) → `[0x48bd4a] = rand()%140 + 160/360`（依財神在左半或右半）。
     進行中：@source 0x004137e8 `mov di,word ptr [0x48bd42]`、0x004137ef `inc edi`、0x004137f7 `cmp di,8`、@source 0x004137fd `cmp byte ptr [0x48bd5a], 0`、@source 0x00413806 `push 0`＋0x00413808 `push 0x4750bf`＋0x0041380d `call 0x4542ce`（音效 id `0x16`）、@source 0x00413815 `push 1`＋0x00413817 `push 0x4750cf`＋0x0041381c `call 0x4542ce`（id `0x18`）、@source 0x00413815 `push 1`／0x00413826 `movsx eax,word ptr [0x48bd4a]`／0x0041382e `call 0x4123d7`（在爆炸點投放**炸彈**）；@source 0x00413836 `cmp word ptr [0x48bd42], 0xc`、0x0041383e `jne`、0x00413840 `mov word ptr [0x48bd42], 0xffff`（回到未啟動）。
9. 掉落物生成 `0x004123d7(arg, x)`：
   - 找空槽 @source 0x004123e5 `cmp word ptr [ebx*8 + 0x48bbc4], 0`；@source 0x004123f0 `cmp ebx,0x10`、0x004123f3 `je 0x4124a4`（滿則放棄）。
   - `arg==0`（財神正常投放）：@source 0x00412400 `call 0x456f2d`、0x00412407 `mov ecx,0x14`(20)、0x0041240f `idiv ecx`；@source 0x00412411 `cmp edx,9`／0x00412416 `mov edx,3`（<9 → type 3 金幣 1 分，45%）；@source 0x0041241d `cmp edx,0xf`／0x00412422 `mov edx,2`（9..14 → type 2 元寶 3 分，30%）；@source 0x00412429 `cmp edx,0x12`／0x0041242e `mov edx,1`（15..17 → type 1 錢袋 5 分，15%）；@source 0x00412435 `xor edx,edx`（18..19 → type 0 寶箱 10 分，10%）。
   - `arg!=0`（爆炸投放）：@source 0x00412439 `mov edx,4`、0x0041243e `inc word ptr [0x48bd54]`（炸彈型、炸彈計數+1）。
   - 寫入：@source 0x00412449 `mov word ptr [ebx*8 + 0x48bbc4], ax`（x）、0x00412451 `mov word ptr [ebx*8 + 0x48bbc6], 0x64`（y=100）、0x0041245b `mov word ptr [ebx*8 + 0x48bbc8], dx`（低 4 位＝type）、0x00412463 `mov word ptr [ebx*8 + 0x48bbca], 0xfff0`（初速 −16）。
   - 透視係數：@source 0x00412471 `sub eax,0x140`（x−320）、0x0041247f `fdiv dword ptr [0x463774]`、0x00412485 `fmul dword ptr [0x463778]`、0x0041248b `fsub dword ptr [esp]`、0x00412496 `mov eax,dword ptr [esp]`、0x00412499 `shl eax,8`、0x0041249c `add word ptr [ebx*8 + 0x48bbc8], ax`（把水平收斂速度寫進狀態高位元組）。
10. 掉落物更新（`0x004132e1`..`0x0041352d`）：@source 0x0041348f `add word ptr [ebx + 0x48bbc8], 0x10`（動畫影格 +1，位於低位元組高 4 位）、0x00413497 `and byte ptr [ebx + 0x48bbc8], 0x7f`；
   - y<130 時加速：@source 0x004134ac `mov ax,word ptr [ebx + 0x48bbca]`、0x004134b3 `add eax,2`、0x004134bf `cmp ax,0x10`、0x004134c5 `mov word ptr [ebx + 0x48bbca], 0x10`（上限 16）、0x004134d6 `add word ptr [esi*8 + 0x48bbc6], dx`。
   - y>=130 時改為等速＋透視：@source 0x004134e2 `mov al,byte ptr [edi + 0x475010]`（type→速度：0→24、1→18、2→15、3→12、4→15）、0x004134ec `mov word ptr [ebx + 0x48bbc6], cx`。
   - 透視位移：@source 0x004132b4 `movsx eax,bx`、0x004132b7 `sub eax,0x82`(130)、0x004132d7 `fdiv dword ptr [0x463780]`（/250.0，@source 0x00463780 內容 `00007a43`＝250.0f）、@source 0x004132fa `fmul dword ptr [0x463784]`（×32768.0f）、0x00413300 `fadd dword ptr [0x463784]`、0x0041330f `movsx ebp,word ptr [ebx + 0x48bbc4]`、0x00413316 `add ebp,dword ptr [esp + 0x24]`（螢幕 x ＝ 記錄 x ＋ 透視位移）。
   - 出界移除：@source 0x004134f3 `cmp word ptr [esi*8 + 0x48bbc6], 0x17c`、0x004134fd `jle 0x41352d`；@source 0x00413523 `xor edx,edx`、0x00413525 `mov word ptr [esi*8 + 0x48bbc4], dx`；type 4 漏接時 @source 0x00413504 `mov di,word ptr [0x48bd54]`、0x0041350b `dec di`、0x00413516 `push 0x4750cf`＋0x0041351b `call 0x4542e9`（停止 id `0x18`）。
11. 碰撞（掉落物 vs 角色）：@source 0x00413328 `mov cx,word ptr [0x48bd48]`、0x0041332f `test cx,cx`、0x00413332 `je 0x413447`；@source 0x0041333b `movsx eax,word ptr [0x48bd52]`、0x00413343 `imul eax,edx`（以角色影格換算 y 偏移）… @source 0x0041336c `movsx edx,word ptr [0x48bd4e]`（角色 x=320 為中心）、0x0041337f `mov ecx,0x17c`（底線 y=380）、@source 0x004133a0 `cmp ebp,edx`、0x004133a8 `cmp ebp,dword ptr [esp + 0x2c]`、0x004133b2 `movsx eax,word ptr [ebx + 0x48bbc6]`、0x004133b9 `cmp eax,dword ptr [esp + 0x38]`、0x004133c3 `cmp eax,ecx`（矩形相交）；@source 0x004133cb `cmp byte ptr [0x48bd5a], 0`、0x004133d2 `jne 0x413447`。
   命中判定：@source 0x004133d4 `cmp edi,4`、0x004133d7 `jne 0x413436`。
   - type 0..3：@source 0x00413436 `inc dword ptr [edi*4 + 0x48bbb4]`（計數 +1）、@source 0x0041343d `xor ebx,ebx`、0x0041343f `mov word ptr [esi*8 + 0x48bbc4], bx`（吃掉）。
   - type 4（炸彈）：@source 0x004133d9 `push 0x4750cf`＋0x004133de `call 0x4542e9`（停 id `0x18`）、@source 0x004133e6 `push 0`＋0x004133e8 `push 0x4750d7`＋0x004133ed `call 0x4542ce`（id `0x0f`）、@source 0x004133f5 `push 1`／0x004133f7 `push 0x127`(295)／0x00413406 `push eax`／0x00413407 `mov eax,dword ptr [0x48bce8]`／0x0041340d `call 0x450ced`（載入 data.mkf `0x20e` 被炸動畫）、@source 0x00413417 `mov word ptr [0x48bd48], ax`(0)、@source 0x0041341d `mov word ptr [0x48bd56], 4`（角色死亡圖）、@source 0x00413426 `mov dl,1`、0x00413428 `mov byte ptr [0x48bd5a], dl`、0x0041342e `mov byte ptr [0x48bd58], dl`（**立即結束**）。

**胜负判定** —
- 三種終止：① `[0x48bd2c]` 歸零（時間到，@source 0x004150b3 `mov byte ptr [0x48bd58], 1`）＋畫面上無掉落物（@source 0x00413a3b `mov byte ptr [0x48bd58], 2`）；② 接到炸彈（@source 0x0041342e `mov byte ptr [0x48bd58], dl`，dl=1）→ 先播被炸動畫，@source 0x00415163 `call 0x450f04` 等到動畫結束才 `mov byte ptr [0x48bd58], 2`；③ 兩者皆進入同一收尾。
- 返回值：@source 0x00415866 `mov ecx,dword ptr [0x48bce8]`、0x0041586d `jmp 0x4155e4`（釋放該動畫）→ @source 0x004155ec `mov eax,dword ptr [0x48bcec]` → EAX = 本局點券。呼叫端 @source 0x0041b152 `add word ptr [ebx + 0x496b98], ax`。
- `0x496b98 == 0x496b68 + 0x30` 同上（算術恆等；@source 0x0042d17c `mov ax,word ptr [ecx + 0x496b98]` 佐證其為玩家結構中的 16 位元欄位）。

**奖罚数值** （分數＝加權計數，無上限比較指令）
| 項目 | 數值 | 立即數地址 |
|---|---|---|
| 分數公式 | `score = 10·c0 + 5·c1 + 3·c2 + 1·c3`（`ci` = `[0x48bbb4+4i]`） | @source 0x004144a6 `shl ecx,2`／0x004144a9 `add ecx,edx`（c1×5）、0x004144b3 `shl eax,2`／0x004144b6 `add eax,edx`／0x004144b8 `add eax,eax`（c0×10）、0x004144c4 `shl eax,2`／0x004144c7 `sub eax,edx`（c2×3）、0x004144cb `mov edx,dword ptr [0x48bbc0]`／0x004144d1 `add edx,eax`（+c3）、0x004144d3 `mov dword ptr [0x48bcec], edx` |
| type 0 寶箱 | 10 分 | @source 0x004144b8 `add eax,eax` |
| type 1 錢袋 | 5 分 | @source 0x004144a9 `add ecx,edx` |
| type 2 元寶 | 3 分 | @source 0x004144c7 `sub eax,edx` |
| type 3 金幣 | 1 分 | @source 0x004144d1 `add edx,eax` |
| type 4 炸彈 | 立即結束（無分） | @source 0x004133d4 `cmp edi,4` |
| 掉落物初始 y | 100 | @source 0x00412451 `mov word ptr [ebx*8 + 0x48bbc6], 0x64` |
| 掉落速度（type 0..4） | 24／18／15／12／15 | 表 `0x475010`，@source 0x004134e2 `mov al,byte ptr [edi + 0x475010]` |
| 加速段 | vy += 2（y<130），上限 16 | @source 0x004134b3 `add eax,2`、0x004134c5 `mov word ptr [ebx + 0x48bbca], 0x10` |
| 透視分母/基準 | 250.0f、32768.0f、起算 y=130 | @source 0x004132b7 `sub eax,0x82`、0x004132d7 `fdiv dword ptr [0x463780]`、0x004132fa `fmul dword ptr [0x463784]` |
| 財神投放影格 | `rand()%5` | @source 0x00413904 `mov ecx,5` |
| 爆炸 x | `rand()%140 + 160`（財神在左）／`+360`（在右） | @source 0x004137ae `mov ecx,0x8c`、0x004137d1 `add edx,0xa0`、0x004137e0 `add edx,0x168` |
| 爆炸觸發機率 | `rand()%10 < 7` | @source 0x004123c1 `mov ecx,0xa`、0x004123cb `cmp edx,7` |
| 掉落物種類機率 | 金幣45%／元寶30%／錢袋15%／寶箱10% | @source 0x00412407 `mov ecx,0x14`、0x00412411 `cmp edx,9`、0x0041241d `cmp edx,0xf`、0x00412429 `cmp edx,0x12` |
| 角色移動 | 每 frame 10 px，死區 8 px | @source 0x00413673 `sub word ptr [0x48bd4e], 0xa`、0x00413688 `add word ptr [0x48bd4e], 0xa`、0x00413661 `cmp eax,8` |
| 財神移動 | 每 frame 12 px；左界 110、右界 530、中線 320 | @source 0x004138ba `add word ptr [0x48bd4c], 0xc`、0x004139ba `sub word ptr [0x48bd4c], 0xc`、0x004139e4 `cmp word ptr [0x48bd4c], 0x6e`、0x004138e7 `cmp word ptr [0x48bd4c], 0x212`、0x004138c7 `cmp word ptr [0x48bd4c], 0x140` |
| 計時 | 360 tick × 50 ms ＝ 18 s；開場倒數 10 tick ＝ 0.5 s | @source 0x0041500f `mov dword ptr [0x48bd2c], 0x168`、0x0041502a `push 0x32`、0x004151f1 `mov dword ptr [0x48bd8c], 0xa` |
| HUD 顯示時間 | `[0x48bd2c] / 2` | @source 0x0041419b `mov eax,dword ptr [0x48bd2c]`、0x004141a0 `sar eax,1` |
| 結算分級（`[0x48bd56]`） | <40→1、40..49→2、50..59→0、≥60→3 | @source 0x004150fe `cmp ebp,0x28`、0x0041510e `cmp ebp,0x32`、0x0041511e `cmp ebp,0x3c` |
| 結算暫停 | 2000 ms | @source 0x0041513f `push 0x7d0` |
| **未遊玩 fallback** | `rand()%20 + 50`（50..69，同 A 的共享區塊） | @source 0x0041545e `mov ebx,0x14`、0x00415468 `add edx,0x32` |

**随机数使用点**
| VA | 取模/遮罩 | 選什麼 |
|---|---|---|
| @source 0x004137a7（更新 `0x413248`） | `mov ecx,0x8c`(140) | 爆炸/炸彈投放的 x 偏移 |
| @source 0x004138d2（狀態 0） | `mov ecx,4` | 是否提早轉入攻擊狀態 |
| @source 0x00413904（狀態 0） | `mov ecx,5` | `[0x48bd40]` = 下一次投放的動畫影格 |
| @source 0x004139cf（狀態 4） | `mov ecx,4` | 同狀態 0 的鏡像版 |
| @source 0x004139f9（狀態 4） | `mov ecx,5` | `[0x48bd40]` |
| @source 0x004123ba（`0x4123ba`，被 @source 0x0041378d 呼叫） | `mov ecx,0xa`＋`cmp edx,7`＋`setl al` | `rand()%10 < 7` → 是否啟動爆炸 |
| @source 0x00412400（`0x4123d7`，arg=0） | `mov ecx,0x14`(20) | 掉落物種類 0..3 加權抽取 |
| @source 0x00415457、0x004154b6（共享 fallback） | 20 / `and eax,1` | 未遊玩分數與角色台詞 |

（`0x00413xxx` 皆屬 `0x00413248` 這個函式體內；`0x4123ba`／`0x4123d7` 是被它呼叫的獨立小函式。B 的入口函式 `0x004155fc` 本身與其 WndProc `0x00414fcd` 內**沒有** `call 0x456f2d`。）

**动画与输入接线点** —
- IAT（同一組，已由 `.idata` hint/name 核對）：
  | slot | 函式 | 用在哪 |
  |---|---|---|
  | `cs:[0x462324]` | `SetTimer` | @source 0x00415034（間隔 `0x32`＝50 ms，@source 0x0041502a `push 0x32`） |
  | `cs:[0x4622fc]` | `KillTimer` | @source 0x004150de（id `[0x48bd88]`） |
  | `cs:[0x4622f8]` | `InvalidateRect` | @source 0x00415045、0x004151a6 |
  | `cs:[0x462340]` | `ValidateRect` | @source 0x004151e1 |
  | `cs:[0x462310]` | `PostMessageA` | @source 0x00415090（`push 0x405`）、`0x401966`（`push 0x402`） |
  | `cs:[0x4622d8]` | `DefWindowProcA` | @source 0x00415209 |
  | `cs:[0x4622ec]` | `GetCursorPos` | @source 0x004135ff（每 frame 讀游標）、0x004151b0（`0x405` 時初始化 `[0x47504f]`） |
  | `cs:[0x46231c]` | `SetCursorPos` | @source 0x0041361c、0x0041363c（把游標夾在 0..639） |
  | `cs:[0x46246c]` | `timeGetTime` | @source 0x0045286c（結算 2000 ms 延遲） |
- 動畫：`0x41473b` 每 tick 先鋪背景（@source 0x00414755 `push 0x475043`）→ @source 0x00414779 `call 0x413248` → @source 0x00414780 `push 0`＋0x00414780 `call 0x41417e`（HUD）；入場 `0x405` 播 `0x4e` 的 FLIC（@source 0x00415199 `call 0x45144f`）；被炸動畫由 data.mkf `0x20e` 經 @source 0x0041340d `call 0x450ced` 載入/播放，並以 @source 0x00415163 `call 0x450f04` 輪詢是否播完。
- `0x414789`（結算文字）為兩遊戲共用：@source 0x0041478f `mov edx,dword ptr [0x48bcec]`、0x00414796 `push 0x46377c`、0x004147a0 `call 0x457110`（sprintf）、0x004147ab `call 0x45825d`（字串寬度）→ 置中（@source 0x004147c6 `mov esi,0x161`）。
- `_libc_free` 逐項釋放：@source 0x004157fc（`0x48bd3c`）、0x0041580b（`0x48bcd0`）、0x0041581a（`0x48bd38`）、0x00415829（`0x48bd30`）、0x00415838（`0x48bce4`）、0x00415846（`0x48bcf4`）、0x00415858（`0x48bd14[0..4]` 迴圈 @source 0x00415850）、0x0041586d/0x004155e4（`0x48bce8`）。

**汇编摘录**
```asm
004155fc  push     ebx
004155fd  push     esi
004155fe  push     edi
004155ff  push     ebp
00415600  sub      esp, 0x80
00415606  imul     eax, dword ptr [0x49910c], 0x68
0041560d  cmp      byte ptr [eax + 0x496b7d], 1
00415614  jne      0x415457
0041561a  cmp      byte ptr [0x497159], 0
00415621  je       0x415457
00415627  push     0x4750bf
0041562c  call     0x454176
0041566b  push     0x5c
00415674  call     0x450441
0041567c  mov      dword ptr [0x48bd38], eax
00415697  add      eax, 0x64
004156aa  mov      dword ptr [0x48bd30], eax
004156e9  lea      eax, [ebx + 0x5f]
004156fc  mov      dword ptr [ebx*4 + 0x48bd14], eax
0041570d  push     0x20e
00415718  call     0x450441
00415720  mov      dword ptr [0x48bce8], eax
00415725  mov      eax, dword ptr [0x48bd38]
0041572a  mov      dword ptr [0x47504b], eax
00415785  mov      word ptr [0x48bd4e], 0x140
004157ca  push     0xa
004157cc  call     0x4549cf
004157d6  push     0x414fcd
004157db  call     0x4018e7
00415866  mov      ecx, dword ptr [0x48bce8]
0041586d  jmp      0x4155e4
```
```asm
0041b16c  imul     ebx, dword ptr [0x49910c], 0x68
0041b173  call     0x4155fc
0041b178  jmp      0x41b152
0041b152  add      word ptr [ebx + 0x496b98], ax
```
```asm
0041500f  mov      dword ptr [0x48bd2c], 0x168
00415019  mov      dword ptr [0x48bd8c], 0x63
0041502a  push     0x32
00415034  call     dword ptr cs:[0x462324]
004151f1  mov      dword ptr [0x48bd8c], 0xa
004150c4  call     0x413248
00415163  call     0x450f04
00415178  mov      byte ptr [0x48bd58], 2
00413606  mov      esi, dword ptr [0x47504f]
0041360c  sub      esi, dword ptr [esp + 0x1c]
0041361c  call     dword ptr cs:[0x46231c]
00413643  mov      dword ptr [0x47504f], 0x27f
00413661  cmp      eax, 8
00413673  sub      word ptr [0x48bd4e], 0xa
00413688  add      word ptr [0x48bd4e], 0xa
```
```asm
004123d7  push     ebx
004123e5  cmp      word ptr [ebx*8 + 0x48bbc4], 0
004123f9  cmp      dword ptr [esp + 0x10], 0
004123fe  jne      0x412439
00412400  call     0x456f2d
00412407  mov      ecx, 0x14
0041240f  idiv     ecx
00412411  cmp      edx, 9
00412416  mov      edx, 3
00412422  mov      edx, 2
0041242e  mov      edx, 1
00412435  xor      edx, edx
00412439  mov      edx, 4
0041243e  inc      word ptr [0x48bd54]
00412451  mov      word ptr [ebx*8 + 0x48bbc6], 0x64
0041245b  mov      word ptr [ebx*8 + 0x48bbc8], dx
00412463  mov      word ptr [ebx*8 + 0x48bbca], 0xfff0
00412499  shl      eax, 8
0041249c  add      word ptr [ebx*8 + 0x48bbc8], ax
004134e2  mov      al, byte ptr [edi + 0x475010]
004133d4  cmp      edi, 4
00413436  inc      dword ptr [edi*4 + 0x48bbb4]
00413428  mov      byte ptr [0x48bd5a], dl
004144b8  add      eax, eax
004144d3  mov      dword ptr [0x48bcec], edx
004150fe  cmp      ebp, 0x28
0041511e  cmp      ebp, 0x3c
0041513f  push     0x7d0
```

**未决**
- `0x48bd44`／`0x48bd46` 的狀態機語意（走/攻擊/舉袋）只由動作與跳表推得，未對應到 sprite 的具體幀語意；財神圖集 `0x5d` 有 19 張圖，動畫表 `0x475015`（type×6＋frame，例：type0=`{0,1,2,3,5,6}`、type4=`{0x0c,0x0d,0x0e,0x0f,0x11,0x12}`）的 type 索引與 `[0x48bd44]` 的對應關係未逐一驗證。
- `0x48bd54`（炸彈計數）遞減到 0 時只觸發 @source 0x00413516 `push 0x4750cf`＋`call 0x4542e9`（停止音效），沒有分數或結束效果 → 其完整作用未定。
- 爆炸圖集 `0x5e` 的 12 張與 `[0x48bd42]` 0..0x0c 的對應（索引看起來直接使用，未再加偏移）未對影像逐一核對。
- `0x48bd40`（`rand()%5`）在投放時的角色：只用於「財神影格等於該值時投放」，語意未定。
- `0x450f04` 的語意（輸入輪詢 or 動畫推進）未定；只知道 @source 0x00415163 用它判斷「被炸動畫是否還在播」。
- `0x48bd56` 取值 0..4 分別對應角色哪一張圖（圖集 `0x64+角色` 有 25 張）未逐一核對。
- `0x413248` 中 `0x4568c2`（帶縮放的貼圖，@source 0x00413487）之參數語意未完全確定。
- `0x455b3a`／`0x455e24` 如何從描述子第 5 個 dword（B 的 `0x47504b`）取像素資料未查（`0x45663e` 是 `arg2 + [arg2+8]` 的相對位移，但 B 寫進去的是絕對 handle，兩者是否同一解譯方式未定）。
- 角色圖集高度欄位：程式碼用 @source 0x004157a8 `mov eax,dword ptr [eax + 4]`，與碰撞用的 @source 0x00413377 `movsx ecx,word ptr [eax + 0x12]`（圖集 `+0xc` 起 12 位元組一筆，`+6`）位置不同，兩者關係未追平。

---

## 共享代碼與框架（不屬於兩個入口，但理解玩法必需）

| VA | 作用 | 關鍵證據 |
|---|---|---|
| `0x00415457`..`0x004154d7` | 三小遊戲共用的「未遊玩/設定關閉」分支：`rand()%20+50`、「得點券%d點」訊息框 2000 ms、隨機角色台詞 | @source 0x00415457、0x00415468 `add edx,0x32`、0x0041548e `call 0x440cac`、0x004154be `mov esi,dword ptr [ebx + eax*4 + 0x48084a]` |
| `0x004155ec`..`0x004155fb` | 共用返回：`mov eax,dword ptr [0x48bcec]` + `ret` | @source 0x004155ec |
| `0x00414858` | 另一支共用繪圖/HUD（小遊戲一使用，見 @source 0x004153aa `push 0x414858`） | 不在本次範圍 |
| `0x00415b3a`/`0x4563f5` | 圖集貼圖包裝：`0x4563f5(surface,圖集,x,y)` → `0x455b3a(surface,640,480,圖集,x,y)` | @source 0x00456404 `push 0x1e0`、0x00456409 `push 0x280`、0x0045640e `call 0x455b3a` |
| `0x45663e` | 依 12 位元組圖像表貼圖：`+0`寬、`+2`高、`+4`偏移x、`+6`偏移y、`+8`資料相對位移 | @source 0x0045665d `lea esi,[esi + eax + 0xc]`、0x00456661 `mov edx,dword ptr [eax + 8]`、0x00456664 `add edx,eax`、0x00456669 `movsx eax,word ptr [esi + 4]` |
| `0x401966` | `PostMessageA([0x48a0d4], 0x402, 0, arg)` → 讓 `0x4018e7` 的迴圈返回 | @source 0x00401966、0x0040196d `push 0x402`、0x00401979 `call dword ptr cs:[0x462310]` |
| `0x45285e` | 以 `timeGetTime` 計時的訊息泵延遲（參數 ms） | @source 0x0045286c `call dword ptr cs:[0x46246c]`、0x004528ae `cmp ebx,edi`、0x004528b0 `jb 0x452875` |

---

## 与既有文档的矛盾

1. **upstream asm 標籤位址錯**：`rich4-re/asm/rich4_small_games.asm` 把 `_rich4_ui_game_balloon` 放在 `0x004155FC`。但由 exe 實測：`0x004154DC` 才是氣球遊戲（載 panel.mkf `0x4e/0x4f/0x5b`，`0x5b` 的圖就是「1..9／x2／÷2／?」氣球），`0x004155FC` 是財神爺（載 `0x5c/0x5d/0x5e/0x5f..0x63/0x64+角色` 與 data.mkf `0x20e`）。標籤整體往後錯了一個函式。
2. **任務給的入口 B 位址錯**：`0x00415A6F` 不是函式起點，而是 `0x00415A6D call 0x4562cc` 這條指令的第 3 個位元組；真正的入口是 `0x004155FC`。`0x0041b173` 的 `call` 目標由 `r4dump` 線性反組譯可讀出為 `call 0x4155fc`，而非 `call 0x415a6f`。
3. **任務給的 dispatch 索引整體差 1**：表 `0x004197e9` 的實際內容（dword）為 idx6→`0x41b146`（`call 0x415215` 企鵝）、**idx7→`0x41b15e`（`call 0x4154dc` 氣球）**、**idx8→`0x41b16c`（`call 0x4155fc` 財神）**、idx9→`0x41b17a`（`call 0x4315cc`）。所以氣球是事件類型 7、財神是事件類型 8（任務描述為 8/9）。
4. **音效 id 與「表位址」易混**：`rich4-remake/docs/known-deviations.md` 把「氣球生成」音效寫成 id 19（`0x00413077` 附近的立即數），exe 實際是 `push 0x47509f` → `{0x13,0x14,0x15}` 這組表的第一筆 id `0x13`＝19，方向一致但那是「表位址」而非 id 本身；同一份文件把「氣球点空」寫成 20（`0x00414f0d`），該處立即數 `0x4750a7` 指向的是 id `0x14`＝20，也只是表位址。判讀時勿把表位址當成 id。
5. `rich4-remake/docs/PRD.md` REQ-12.16 說財神用的資源是「`#78/#79/#92/#93/#94/#95..#99/#100+角色`」；以 0-based 資源號核對 exe 常數 `0x4e/0x4f/0x5c/0x5d/0x5e/0x5f..0x63/(0x64+角色)` 完全一致（該文件的 `#` 號為同值十進位），此條**不矛盾**，列出供交叉確認。

---

## 全域狀態變數總表（0x48bc44..0x48bd90 區）

| 位址 | 寬度 | 屬於 | 語意 | 主要讀寫指令 |
|---|---|---|---|---|
| `0x48bbb4`+4i | dword×4 | B | type 0..3 吃到數 | @source 0x00413436 `inc dword ptr [edi*4 + 0x48bbb4]`；@source 0x00414276 `mov edi,dword ptr [0x48bbb4]` |
| `0x48bbc4`+8i | 16 槽×8B | B | 掉落物：`+0`x、`+2`y、`+4`狀態(低4位type/高位元組水平收斂速度、低位元組高4位動畫) 、`+6`vy | @source 0x00412449、0x00412451、0x0041245b、0x00412463 |
| `0x48bbc8` | word | B | 同上 `+4` | @source 0x0041348f `add word ptr [ebx + 0x48bbc8], 0x10` |
| `0x48bbca` | word | B | 同上 `+6`（y<130 時的加速度） | @source 0x004134c5 |
| `0x48bc44`+8i | 16 槽×8B | A | 氣球：`+0`x（0=空）、`+2`y、`+4`狀態（低4位＝圖/分值、高位元組＝爆破倒數×0x10） | @source 0x00413189 `mov eax,ebp`…0x0041318e `cmp word ptr [eax + 0x48bc44], 0`；0x00413093、0x0041309b、0x004130a9 |
| `0x48bcc8` | dword | A | 上升速度倍率：`-1`→×2、`0`→不變、`+1`→÷2 | @source 0x004130f9 `mov edx,dword ptr [0x48bcc8]`；@source 0x00414ea2／0x00414eae 寫入 |
| `0x48bcd0` | ptr | A/B | panel.mkf `0x4f` 數字圖集 | @source 0x00415542、0x00415662 |
| `0x48bce4` | ptr | B | panel.mkf `0x5d` 財神圖集 | @source 0x004156c4 |
| `0x48bce8` | ptr | B | data.mkf `0x20e` 被炸動畫 | @source 0x00415720 |
| `0x48bcec` | dword | A/B | **本局得分（＝返回值）**，A 上限 999 | @source 0x004155ec、0x00414eed、0x004144d3 |
| `0x48bcf0` | dword | 小遊戲一 | — | 不在範圍 |
| `0x48bcf4` | ptr | B | panel.mkf `0x5e` 爆炸圖集 | @source 0x004156de |
| `0x48bd14`+4i | ptr×5 | A/B | panel.mkf `0x5f..0x63`（B 為 5 種掉落物） | @source 0x004156fc、0x00413478 |
| `0x48bd2c` | dword | A/B | 可玩時間（tick）：A 150、B 360 | @source 0x00414c1d、0x0041500f |
| `0x48bd30` | ptr | B | panel.mkf `0x64+角色` 玩家角色圖集（12 位元組/圖；程式以 `handle + idx*12` 為基、再讀 `+0xc/+0xe/+0x10/+0x12`，等價於 `handle+0xc+idx*12` 的 `+0/+2/+4/+6`） | @source 0x004156aa、0x00413362 `add eax, ecx`、0x0041338c `movsx ecx, word ptr [eax + 0xc]` |
| `0x48bd34` | ptr | A | panel.mkf `0x5b` 背景＋氣球圖集 | @source 0x0041555c |
| `0x48bd38` | ptr | B | panel.mkf `0x5c` 640×480 全屏像素 | @source 0x0041567c |
| `0x48bd3c` | ptr | A/B | panel.mkf `0x4e` 640×480/20 幀 FLIC | @source 0x00415529、0x00415649 |
| `0x48bd42` | word | B | 爆炸動畫計數：`-1`=未啟動、`0..0x0c` | @source 0x00415773、0x004137ef、0x00413840 |
| `0x48bd44` | word | B | 財神狀態機 0..4 | @source 0x00415761、0x0041387f |
| `0x48bd46` | word | B | 財神動畫影格 0..5 | @source 0x0041576a、0x004138b3 |
| `0x48bd48` | word | B | 角色動作：0=站立、1=向左、2=向右 | @source 0x0041366a、0x00413694 |
| `0x48bd4a` | word | B | 爆炸/炸彈落點 x | @source 0x004137d7、0x0041357c |
| `0x48bd4c` | word | B | 財神 x（初始 0x6e=110） | @source 0x00415758、0x004138ba |
| `0x48bd4e` | word | B | 玩家角色 x（初始 0x140=320） | @source 0x00415785、0x00413673 |
| `0x48bd50` | word | B | 角色走路動畫計數 | @source 0x00415795、0x004136a3 |
| `0x48bd52` | word | B | (角色圖高−5)/2 | @source 0x004157b0 |
| `0x48bd54` | word | B | 炸彈計數（漏接遞減） | @source 0x0041577e、0x0041243e、0x0041350b |
| `0x48bd56` | word | B | 角色狀態圖 / 結算分級 0..4 | @source 0x0041341d、0x00415103 |
| `0x48bd58` | byte | A/B | 遊戲狀態：0=進行；A：1=時間到（等清場）→2=可收尾；B：被炸時直接=1，等動畫播完→2 | @source 0x0041557f、0x00414ce0、0x00413222、0x004150b3、0x00413a3b |
| `0x48bd59` | byte | A | 凍結計數（>0 時氣球不動） | @source 0x00415587、0x00414e99、0x004130de |
| `0x48bd5a` | byte | B | 受擊/等待旗標（1=被炸動畫播放中） | @source 0x00415742、0x00413428、0x00415156 |
| `0x48bd80` | dword | A | A 的 SetTimer 回傳 id | @source 0x00414c49、0x00414d1b |
| `0x48bd84` | dword | A | 開場倒數（0x63→5→0） | @source 0x00414c27、0x00414fb3 |
| `0x48bd88` | dword | B | B 的 SetTimer 回傳 id | @source 0x0041503b、0x004150d6 |
| `0x48bd8c` | dword | B | 開場倒數（0x63→0x0a→0） | @source 0x00415019、0x004151f1 |
| `0x475039` | byte×10 | A | 特殊氣球類型表 `{9,9,10,10,10,10,10,11,11,11}` | @source 0x00413014 |
| `0x475004` | byte×15 | A | 氣球上升速度表 | @source 0x004130ee |
| `0x475010` | byte×5 | B | 掉落速度表(type 0..4)＝24/18/15/12/15 | @source 0x004134e2 |
| `0x475015` | byte×30 | B | 財神動畫表(type×6＋frame) | @source 0x004135bd |
| `0x475043` | 12B 描述子；`0x47504b`(`+8`) 由程式寫入 | B | 全屏背景描述子（`+0`=0x280、`+2`=0x1e0、`+4`=`+6`=0、`+8`=`0x5c` 的 handle） | @source 0x00414755 `push 0x475043`、@source 0x0041572a `mov dword ptr [0x47504b], eax` |
| `0x47504f` | dword | B | 上一 frame 的游標 x（夾邊界用） | @source 0x00413606、0x004151ba |
| `0x46cad8` | dword | A/B | 定時器 id / 視窗槽計數（`0x4018e7` 遞增） | @source 0x004018f2、0x00415062 |
| `0x46cadc` | RECT(16B) | A/B | Blt 用的來源矩形 | @source 0x00414f71、0x004151ca |
| `0x46cb01` | byte | A/B | 音效子系統可用旗標（0 → 不更新） | @source 0x00414c69、0x00415051 |
| `0x49910c` | dword | 全域 | 當前玩家索引 | @source 0x004154e6、0x0041b146 |
| `0x496b68`+0x13 | byte | 全域 | 玩家角色編號 | @source 0x0041568c |
| `0x496b68`+0x15 | byte | 全域 | 玩家在場旗標（閘門要求 ==1） | @source 0x004154ed、0x0041560d |
| `0x496b68`+0x30 | word | 全域 | 玩家點券（小遊戲分數加在此） | @source 0x0041b152 |
| `0x496b68`+0x37 | byte | 全域 | 事件分派器的額外閘門 | @source 0x00419873 |
