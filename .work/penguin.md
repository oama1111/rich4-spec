### 企鵝挖寶（入口 VA 0x00415215）

> 名稱證據：名稱指標表 @source 0x00476080 內含字串指標 0x00465e64 = `企鵝挖寶`（Big5；同表 `[0]=0x00465e56「七彩氣球」`、`[3]=0x00465e64「企鵝挖寶」`、`[4]=0x00465e6d「百貨公司」`…）。
> 0x00476080 由群組結構 @source 0x004761f8 描述：`{0x14, 0x3, 0x0, ptr@0x00466076「特殊地點」, 0x00476080, 0x17, 0x10, 0x0}`（前一組標籤 0x0046607f「特殊人物」、次組 0x00466088「卡  片」）；該群組結構本身在 exe 內找不到直接指令或指標引用（未決，見文末）。
> 上游檔案把本函式標為 `_rich4_ui_game_penguin_treasure`（僅為提示）。以事件型別索引 6 直接對應「企鵝挖寶」格屬**推断**：分派器的節點事件型別位元組來自地圖節點資料，不在 exe 內。

**触发条件与触发点** — 本函式無參數（`call 0x415215` 前沒有任何 push），由「機會／事件」分派器以**事件型別索引 6** 呼叫。
- 分派器函式起點 `0x0041982d`（`push ebx; push esi; push edi; push ebp; sub esp,0xf8`），其唯一呼叫點在 `0x00418e7f`（@source 0x00418e8d..0x00418ea1）：
  `00418e94  mov ax, word ptr [eax + 0x496b74]`（eax = `imul eax,[0x49910c],0x68`，即 `player+0x0C`）→ `00418ea1 call 0x41982d`。
  也就是說**分派器的參數 = 當前玩家的所在節點編號（player+0x0C）**，節點記錄 = `[0x498e80] + 節點*0x28`：
  `00419840 shl eax,2 / 00419843 add eax,edx / 00419845 shl eax,3` → `*0x28`；`0041985b mov ebx,[eax+0x24]` + `0041985e and ebx,0xff` = 事件型別位元組；`00419850 mov dx,[eax+0x20]` = 附帶的 word 參數（本函式不讀取）。
- 進入 case 前的閘門（@source 0x0041986c..0x004198b2）：
  1. `00419873 cmp byte ptr [eax+0x496b9f],0`（`player+0x37`）→ 若非 0：`0041987c test ebx,ebx / 0041987e jne 0x41b3d0`，即**該狀態非 0 時只有事件型別 0 會被處理，其餘（含 6）整場跳過**（0x0041b3d0 為分派器 return）。
  2. `00419884 cmp ebx,2 / 00419887 jb 0x4198a9`、`00419889 cmp ebx,0x10 / 0041988c ja 0x4198a9` → 型別 2..0x10 時先播音效：`00419892 mov al,byte ptr [ebx+0x475299]` → `00419898 shl eax,3` → `0041989b add eax,0x48234a` → `004198a1 call 0x4542ce`（0x475299 為 17 byte 索引表，0x48234a 為 8-byte 音效結構表；型別 6 → 索引 0x0a → 0x48239a，id=0x2b）。
  3. `004198a9 cmp ebx,0x10 / 004198ac ja 0x41b3d0` → 型別 > 0x10 直接跳過。
  4. `004198b2 jmp dword ptr [ebx*4 + 0x4197e9]` → 17 項跳表的第 6 項（0-based）為 `0x0041b146`。
     ⚠ 任務描述說「index 7 → 0x41b146」，但以 `jmp dword ptr [ebx*4+0x4197e9]` 逐 dword 讀出：`[0]=0x4198b9, [1]=0x41b3d0, [2]=0x41b11e, [3]=0x41b128, [4]=0x41b132, [5]=0x41b13c, [6]=0x41b146, [7]=0x41b15e, [8]=0x41b16c, …`，故**本函式為事件型別 6**（型別 7 → `0x4154dc`、型別 8 → `0x4155fc` 是另外兩個小遊戲）。
- 呼叫點與返回值（@source 0x0041b146）：
  ```
  0041b146  imul     ebx, dword ptr [0x49910c], 0x68
  0041b14d  call     0x415215
  0041b152  add      word ptr [ebx + 0x496b98], ax
  0041b159  jmp      0x41b3d0
  ```

**前置闸门** — 函式開頭兩道閘門，任一不成立即跳 0x00415457（停用分支，只發點券不玩遊戲）：
```
0041521f  imul     eax, dword ptr [0x49910c], 0x68
00415226  cmp      byte ptr [eax + 0x496b7d], 1
0041522d  jne      0x415457
00415233  cmp      byte ptr [0x497159], 0
0041523a  je       0x415457
```
- `[0x496b7d]` = `player+0x15`。語意為「該玩家的操作者型別旗標」：**值 1 = 人類玩家**。旁證：`0x00401196 cmp byte ptr [eax+0x496b7d],1`（迴圈中只挑這一個值來決定是否進 `0x401537`）、`0x004079d0 mov byte ptr [0x496b7d],1`（新遊戲初始化時把 player0 設為 1），而 `0x00407646 cmp byte ptr [eax+0x496b7d],0`、`0x00409964 test byte ptr [eax+0x496b7d],0x30`、`0x0040d60e or byte ptr [ebx+0x496b7d],0x20`、`0x0040d6d1 or byte ptr [ebx+0x496b7d],0x10`、`0x0040cd5e or byte ptr [eax+0x496b7d],0x40` 顯示它同時是 bitfield（0x10/0x20/0x40 等旗標語意**未決**）。因此本閘門 = 「只有真人操作時才玩這個小遊戲」。
- `[0x497159]` = 設定區塊 `0x497158` 的**第 2 個位元組**。`0x497158` 起 0x10 byte 存檔／讀檔於 `RICH4.CFG`：
  `00411e93 push 0x463764("rb") / 00411e98 push 0x463767("RICH4.CFG") / 00411e9d call 0x4573bf`→`00411eae push 0x10 / 00411eb0 push 0x497158 / 00411eb5 call 0x4576d0`；預設值 `00411edc mov byte ptr [0x497158],ah(1)`、`00411ee2 mov byte ptr [0x497159],ah(1)`、`00411eea mov byte ptr [0x49715a],dh(4)`、`00411ef0 mov byte ptr [0x49715b],dh(4)`、`00411ef6 mov byte ptr [0x49715c],ah`、`00411efc mov byte ptr [0x49715d],ah`、`00411f04 mov byte ptr [0x497164],ch(0)`。
  選項標籤表 `0x474a54`：`[0]=0x463534"遊戲速度" [1]=0x46353d"動畫過程" [2]=0x463546"音 樂" [3]=0x46354c"音 效" [4]=0x463552"自動存檔" [5]=0x46355b"樂  曲"`；`[0x49715a]`（=區塊[2]）確實被當「音樂」用（`0x4549cf`/`0x454bcc` 用它決定要不要 `mciSendStringA` 播 MIDI），`[0x49715d]`（=區塊[5]）被當「樂曲」用（`0x004014b1 cmp byte ptr [0x49715d],2`）。故 `[0x497159]` = 區塊[1] = **「動畫過程」開關（1=開）**；=0 時跳過小遊戲與相關事件動畫（`0x40ec14/0x40ecf1/…/0x40f31c` 共 11 處 `cmp byte ptr [0x497159],0` 都以它為「是否播事件動畫」閘門）。標籤與位元組的對應為**推断**（依相鄰選項 `[2]音樂`／`[5]樂曲` 的用法外推）。

**资源与音频** — 13 個 panel.mkf 圖 + 8 個 effect.mkf 音效 + 1 首 MIDI。MKF 全域：`0x48a0e4`=data.mkf、`0x48a054`=speaking.mkf、`0x48a05c`=panel.mkf、`0x48a058`=effect.mkf（@source 0x0040172e/0x00401740/0x00401752/0x00401764，字串 0x46303e/0x463047/0x463054/0x46305e）。
- 音效結構：`00415240 push 0x475057 / 00415245 call 0x454176`（`_rich4_init_sound_effect_info`：對 `{id,handle}` 陣列逐項 `_read_mkf(effect.mkf,0,0,id)`→`0x453dcf`→`0x456e11`，見 0x00454176..0x004541bb）。陣列 `0x475057` 起 8-byte 一項，`0x475097` 為 `-1` 終止：
  `0x475057={0x0b,0} 0x47505f={0x0c,0} 0x475067={0x0d,0} 0x47506f={0x0e,0} 0x475077={0x10,0} 0x47507f={0x11,0} 0x475087={0x12,0} 0x47508f={0x0f,0}`。
- 圖（`_read_mkf(panel.mkf,0,0,id)` = `push 0; push 0; push id; push [0x48a05c]; call 0x450441`），id → 全域：
  | id | 全域 | 用途（依使用處推得） |
  |---|---|---|
  | 0x4e | 0x48bd3c | 全螢幕圖（0x00414a59 傳給 `0x45144f` 貼圖；失敗分支亦同） |
  | 0x4f | 0x48bcd0 | 數字字型（+0xc + glyph*12；HUD 以字元的 `-0x30` 當 glyph index） |
  | 0x50 | 0x48bd34 | 角色＋圖示 sprite sheet（+0xc 為 frame0；盤面圖示用 `(type+3)*12`，行走用 +0x18/+0x24/+0x30/+0x78） |
  | 0x51 | 0x48bd38 | 點擊命中圖：byte map，索引 `y*640+x`（0x00414aff..0x00414b06） |
  | 0x52 | 0x48bcf8 | 相位2（行走）sprite sheet：8 方向 × 4 子格 |
  | 0x53 | 0x48bd28 | 相位3（挖掘／結算）sprite sheet |
  | 0x54 | 0x48bcd8 | 相位4（高分結尾）sprite sheet（幀數 = `[sheet+4]`） |
  | 0x55 | 0x48bcd4 | 相位5（低分結尾）sprite sheet |
  | 0x56..0x5a | 0x48bd14+4i (i=0..4) | 5 種道具圖示（撿到時飛向 HUD 的動畫；`0x00412bda mov eax,[eax*4+0x48bd10]`，eax=道具型別 1..5） |
  載入指令：`00415251 push 0x4e`…`00415306 push 0x55` 各接 `call 0x450441`；迴圈 `0041531e push 0 / 00415322 lea eax,[ebx+0x56] / 0041532c call 0x450441 / 00415334 mov dword ptr [ebx*4+0x48bd14],eax / 0041533c cmp ebx,5 / 0041533f jl 0x41531e`。
- MIDI：`0041539a push 0xc / 0041539c call 0x4549cf` → `mciSendStringA("open sequencer!%s alias mid")` + `"play mid from %d notify"`（0x4664a4/0x4664de），表 `0x47e793[0xc]` = 0x4663ac = `MIDI13.MID`；`004153b2 call 0x454bcc`（等／續播，`"status cdtrack current track"`）。
- 釋放：`004153b7 push 0x475057 / 004153bc call 0x454240`（`_rich4_uninit_sound_effect_info`，0x00454240）後，對 8 張圖 + 5 張圖逐一 `call 0x456e11`（= `0x456e1f`，free）@source 0x004153c4..0x00415450。

**玩法規則（逐步）** — 一個「桌面盤面 + 點擊尋寶」小遊戲：把 28 個道具隨機撒在 9×9 = 81 格盤面上（座標表 `0x474d7c`，每格 8 byte），玩家用滑鼠點盤面格，企鵝角色沿直線走過去挖開該格；挖到炸彈（型別1）立刻爆炸結束，挖到寶物（型別2..5）得分。
1. **進場設定**（@source 0x00415341..0x0041538f）：`mov dword ptr [0x48bd04],0x20000`、`[0x48bd08],0x60000`（16.16 定點起點 = 格 (2,6)）；`[0x48bcec]=0`（得分）、`[0x48bcf0]=0xffffffff`（前一相位=-1）、`[0x48bccc]=0`（相位=待機）、`[0x48bcc4]=0`（動畫計數器）；`00415375 push 0x10 / 00415377 push ebx(0) / 00415378 push 0x48bbb4 / 0041537d call 0x456f60` = `memset(0x48bbb4,0,0x10)`（清空型別2..5 的計數器；型別1 的 0x48bbb0 不在此範圍內，且不計分）；`[0x48bd58]=0`（game state=遊玩中）、`[0x48bd5b]=0`（撞牆旗標）。
2. **盤面初始化** `00415395 call 0x412014`：
   - `0041202e..00412062`：對 81 格把 `[cell+4]` 的低 nibble 清 0（`and bl,0xf0`）。
   - 之後 5 個「道具群組」迴圈（`cl`=[esp+0x1c]=0..4，需要數 `[0x411fc8+4g]` = `3, 12, 3, 9, 1`，共 28 件）。每件：`0041208f call 0x456f2d`（rand）→ `00412094 imul eax,ebp(0x40) / 00412097 sar eax,0xf`（= `rand()%64`，取第 n 個合法格）→ 掃 `esi(列) 0..8 × edx(行) 0..8`，只取「`cmp word ptr [eax+0x474d7c],0` 不成立（word0≠0）」且 `test byte ptr [eax+0x474d80],0xf == 0` 的格，數到第 n 個就把該格 `[cell+4]` 低 nibble 設為 `g+1`（`004120fa or word ptr [eax+0x474d80],dx`，dx=g+1）。
   - 格內欄位：`+0` word0 = 可通行旗標（0=牆）、`+2` word1 = 畫面座標（sprite 貼圖用，`movsx esi,word ptr [...+0x474d7c]` / `+0x474d7e`）、`+4` 低 nibble = 道具型別（1..5）。
3. **開場**：`_Wait_0402_Message(0x414858, 0)`（`004153a4 push edi(0) / 004153a5 push 0x414858 / 004153aa call 0x4018e7`）→ 進入訊息迴圈，之後 `0x454bcc`、`0x454240`、釋放資源。實際的視窗訊息處理器是 **0x00414858**（不是任務描述的 0x414fcd，見下）。
4. **WM_USER+1（0x401）開局**（@source 0x004148b9）：`mov dword ptr [0x48bd2c],0x96`（倒數 150）、`mov dword ptr [0x48bd7c],0xa`（滑鼠停用 10 tick）、`push 1 / call 0x41461b`（畫盤面）、`SetTimer(hwnd,[0x46cad8],0x64,0)`（**100 ms**）、`mov [0x48bd78],eax`（timer id）、`InvalidateRect(hwnd,0,0)`。
   `0x41461b(arg)`：把角色 sheet `[0x48bd34]+0xc` 畫在 (0,0)；arg≠0 時再走 81 格，對有道具的格畫圖示 `frame=(type+3)`（`004146a6 lea edx,[eax+3] / 004146b3 mov edx,[0x48bd34] / 004146bc add eax,edx`），最後 `004146e2 call 0x413a4a(0)` 畫 HUD。
5. **每 tick（WM_TIMER 0x113）**（@source 0x00414900..0x00414a45）：
   - `00414900 cmp byte ptr [0x46cb01],0 / je 回傳`（視窗未 active 不跑）；`00414911 cmp eax,[0x46cad8] / jne 回傳`（只認自己的 timer id，eax=[esp+0x1c]=wParam）。
   - `0041491d mov eax,[0x48bd2c] / 00414922 dec eax`；若 `[0x48bd58]==2`（結束倒數）→ `[0x48bd2c]=eax`，歸零時 `KillTimer(hwnd,[0x48bd78])` + `0x401966(0)`（= PostMessage(main_hwnd,0x402,0,0)，讓 `_Wait_0402_Message` 返回）→ 收攤。
   - 否則 `00414957`：`[0x48bd7c]` 由 10 倒數，歸零時 `00414974 push 0x405 / call PostMessageA` → 觸發 0x405（結算畫面）。
   - `00414986 cmp dword ptr [0x48bd2c],0 / jle 0x414a0a`：時間 >0 才 `00414995 mov [0x48bd2c],eax`（扣 1）→ `0041499a call 0x413a4a(2)`（重畫 HUD 並**計算得分**）。時間歸零時：`004149ab push 0x475057 / call 0x4542e9`（停循環音）、`004149b8 and dword ptr [0x48bcc4],0xf00`（清動畫計數低位）、`004149c2 mov ecx,[0x48bcec]`，依分數選結尾相位：`cmp ecx,0x28 / jge`（<40 → `[0x48bccc]=5` + 播 0x47506f）、`cmp ecx,0x37 / jle`（>55 → `[0x48bccc]=4` + 播 0x475067）、否則 `[0x48bccc]=6`。
   - `00414a0a call 0x4124c8`（**每格畫面更新＋走位**，見 7）。
   - `00414a0f cmp byte ptr [0x48bd58],1 / jne`：一旦 state=1 → `[0x48bd58]=2`、`[0x48bd2c]=0x14`（20 tick = 2 秒）、`0x402460(0)`、`0x4021f8(0x29,1,0)`、`00414a45 call 0x414789`（畫最終得分：`sprintf(buf,"%d",[0x48bcec])` 後用 `[0x48bcd0]+0xc` 字型逐字畫在 y=0x96、x=0x161-總寬/2，字距 0x42）。
6. **滑鼠**（WM_LBUTTONDOWN 0x201 / WM_LBUTTONDBLCLK 0x203，@source 0x00414aa9）：
   - 閘門：`00414aa9 cmp byte ptr [0x48bd58],2 / 00414ab2 mov dword ptr [0x48bd2c],1`（結束中按一下就加速倒數）；`00414abe cmp dword ptr [0x48bccc],0 / jne 回`（動畫中不吃點擊）；`00414ac7 cmp byte ptr [0x48bd58],0 / jne 回`（只在遊玩中）；`00414ad4 cmp dword ptr [0x48bd7c],0 / jne 回`（開場 1 秒內不吃）。
   - 命中測試：`00414ae3 mov bx,cx`（lParam 低字 = x）、`00414ae6 shr eax,0x10`（高字 = y）→ `00414af7 shl ecx,2 / 00414afa add ecx,eax / 00414afc shl ecx,7`（= y*640）→ `00414aff mov eax,[0x48bd38] / 00414b04 add ecx,eax / 00414b06 mov cl,byte ptr [ecx+ebx]`（取圖 0x51 的像素位元組 v）→ `00414b0f mov ebx,9 / 00414b1b idiv ebx`（`ebx = v%9` = 目標格 X）、`00414b2b idiv esi(9)`（`eax = v/9` = 目標格 Y）→ `00414b2f call 0x41211c(X,Y)`。
     ⚠ 此處取像素**沒有**加 sprite sheet 慣用的 `+0xc` 標頭位移，而其他圖都有（例：`00412e55 mov eax,[0x48bcd0] / 00412e5a add eax,0xc`）；0x48bd38 這張資源的格式與標頭處理**未決**。
   - `00414b37 test eax,eax / je 回`：`0x41211c` 回 0（目標格是牆／已在該格）則不動作；成功則 `00414b3f call 0x412287`（先走一格）、`00414b44 mov dword ptr [0x48bccc],2`（切到行走相位）、`00414b50 push 0x475057 / 00414b55 call 0x4542ce`（播循環走路音；`00414b4e push 1` → 第 2 參數=1）。
7. **`0x41211c(X,Y)` 設定路徑**（@source 0x0041211c）：目標格 `word0==0`（牆）→ `0041213a je 0x41227f` 回傳 0；已在同一格 → 回傳 0；否則 `0041218f shl edi,0x10 / 00412192 mov [0x48bcdc],edi`、`shl ebp,0x10 / mov [0x48bce0],ebp`（存目標 16.16），`00412181/00412188` 清 `[0x48bd04]/[0x48bd08]` 低位，`004121b6 add edx,0x8000`、`004121d7 add ecx,0x8000`（走到格心），以 `0x458276`（abs）算 `dx,dy` 後正規化：主軸步進 `±0x10000`（1.0/格），另一軸按比例（`0041223e mov [0x48bcfc],eax`、`00412275 mov [0x48bd00],eax`），回傳 1。
   `0x412287()`（@source 0x00412287）：把 `[0x48bd04]+=[0x48bcfc]`、`[0x48bd08]+=[0x48bd00]` 後用 `(pos>>16)` 查 `cmp word ptr [edx+eax*8+0x474d7c],0`：`word0==0`（牆）→ 走到該分支末 `0041239f mov byte ptr [0x48bd5b],1`（**撞牆旗標**）；`word0≠0` → `004123aa mov dword ptr [0x48bd10],esi / 004123b0 mov dword ptr [0x48bd0c],ebx`（提交新格座標）後返回。
8. **`0x4124c8()` 每格更新（相位機）**（@source 0x004124c8）：開頭讀 `[0x48bd04]/[0x48bd08]`（現在 16.16 位置）與 `[0x48bd10]/[0x48bd0c]`（下一個格心＝本幀插值終點，由 `0x412287` 提交；點擊的目的格另存於 `[0x48bcdc]/[0x48bce0]`），`cmp dword ptr [0x48bcf0],-1 / je 0x41258e`（非第一格才修補小地圖矩形），再 `0041258e mov eax,[0x48bccc] / 00412593 cmp eax,6 / 0041259c jmp dword ptr [eax*4+0x4124ac]`（7 相位跳表：`[0]=0x4125a3 [1]=0x4125e0 [2]=0x412651 [3]=0x412851 [4]=0x412a08 [5]=0x412aac [6]=0x412b45`）。`[0x48bcc4]` 是動畫計數器：低 nibble = 子格/階段，bit4-7 = 行走方向，bit8-11 = 撿到道具的飛行動畫階段。
   - 相位0（0x4125a3）待機：畫角色 sprite（`movsx esi,[cell+0] / movsx edi,[cell+2] / 004125d3 call 0x456418`）。
   - 相位1（0x4125e0）**爆炸**：依 `[0x48bcc4]&0xf` 選 `[0x48bd34]+0x18` 或 `+0x24` 兩張爆格輪播，計數到 0xf 後 `0041264c jmp 0x412b95` → **`00412b95 mov byte ptr [0x48bd58],1`（遊戲結束）**。
   - 相位2（0x412651）**行走**：每 4 子格重算方向 nibble（`dx-x`,`dy-y` → 0..7 方向寫入 `[0x48bcc4]` bit4-7，@source 0x00412651..0x004126af），用 `(dst-center)>>2 * (counter&3)` 內插位置，frame = `dir*4+sub`（`00412720 imul edx,ebx` / `00412749 call 0x45663e`），`00412751 inc edx / 00412760 and ecx,0xff3`。每 4 子格結算：位置 = `[0x48bd10]/[0x48bd0c]`；若已抵達**點擊的目的格**（`004127b1 cmp edx,eax` 比 `[0x48bd04]>>16` vs `[0x48bcdc]>>16`、`004127d9 cmp edx,eax` 比 `[0x48bd08]>>16` vs `[0x48bce0]>>16`）→ `004127dd push 0x475057 / call 0x4542e9`（停走路音）、`004127ec push 0x47505f / call 0x4542ce`（播音效12）、`004127f9 mov dword ptr [0x48bccc],3`（切挖掘相位）；若 `00412808 cmp byte ptr [0x48bd5b],0 / jne`（撞牆）→ 用 `[0x48bcdc]/[0x48bce0]` 重新 `call 0x41211c` 並清旗標，再 `00412847 call 0x412287`（沿牆滑行重試；此為**推断**）。
   - 相位3（0x412851）**挖掘**：先畫效果 sprite（`0041287c mov eax,[0x48bd34] / lea ebx,[eax+0x78]`，配 `0x4562a5`+`0x456418`）；第 4 子格（`test byte ptr [0x48bcc4],3 == 3`）做**道具判定**：
     `004128c5 test byte ptr [edx+0x474d80],0xf / je 0x41291d` → 有道具時：`004128ce and dword ptr [0x48bcc4],0xff`（清方向）、`004128d8 or byte ptr [0x48bcc5],1`（設 bit8 = 要播飛行）、`004128df mov ax,[edx+0x474d80]…and al,0xf` → `004128eb mov dword ptr [0x48bd6c],eax`（道具型別）、`004128f0/004128fc` 存該格畫面座標到 `[0x48bd70]/[0x48bd74]`、`00412914 mov word ptr [edx+0x474d80],bx`（**清掉該格道具**）；否則 `0041291f mov dword ptr [0x48bd6c],ebx`(0)。
     結算（`0041298e mov eax,[0x48bd6c]`）：=0 → `004129a0 mov [0x48bccc],0`（回待機）；=1（炸彈）→ `004129ab mov dword ptr [0x48bccc],eax`（相位1）＋`004129b0 push 0 / 004129b2 push 0x47508f / 004129b7 call 0x4542ce`（爆炸音，id 0x0f，第 2 參數=0）；≥2 → `004129c6 mov [0x48bccc],0`、`004129d2 mov al,byte ptr [eax+0x475051]`→`004129e0 add eax,0x475057`→`004129e6 call 0x4542ce`（依型別播音）、`004129f8 mov dword ptr [esp+0x44],1`（得分變髒旗標）、`004129fc add dword ptr [eax*4+0x48bbac],edx(1)`（**計數器++**，eax=型別 → 位址 = 0x48bbac+型別*4）。
   - 相位4/5/6（0x412a08/0x412aac/0x412b45）為**結尾動畫**：4/5 播撿到的道具 sheet `[0x48bcd8]/[0x48bcd4]`（`[sheet+4]`=幀數）飛向 HUD，`00412a87 and eax,0xf0 / cmp eax,0x40` 完成後 `00412aa7 jmp 0x412b95`；6 只播角色 sprite，計數到 0xf 後同樣 `0x412b95` → `[0x48bd58]=1`。
   - 收尾：`00412f4c cmp dword ptr [esp+0x44],0 / 00412f55 call 0x413a4a(1)`（本格有撿到東西就立刻重算得分）、`00412f5d mov eax,[0x48bccc] / 00412f62 mov dword ptr [0x48bcf0],eax`（記住本格相位）。
9. **HUD**（`0x413a4a`，@source 0x00413a67..0x00413df7）：字型 `[0x48bcd0]+0xc`，glyph 12 byte，`(char-0x30)` 取 index；時間 `[0x48bd2c]` 用 `"%03d"`(0x463788) 畫在 y=0x1a5 x=0x31/0x45/0x5e，分隔圖示 x=0x72；計數器各畫 `"%02d"`(0x46378d)：`[0x48bbc0]`@x=0xb9/0xcd、`[0x48bbb8]`@x=0x114/0x128、`[0x48bbbc]`@x=0x16f/0x183、`[0x48bbb4]`@x=0x1ca/0x1de；總分 `[0x48bcec]` 用 `"%03d"`@x=0x225（後續位數續畫）。

**勝負判定** — 沒有「失敗」以外的分支，**返回 EAX = `[0x48bcec]` 得分點數**，呼叫端把它加進玩家的點數字（word）：
```
004155ec  mov      eax, dword ptr [0x48bcec]
004155f1  add      esp, 0x80
004155f7  pop      ebp / 004155f8 pop edi / 004155f9 pop esi / 004155fa pop ebx
004155fb  ret
0041b152  add      word ptr [ebx + 0x496b98], ax     ; ebx = [0x49910c]*0x68
```
- `0x496b98` = 玩家結構基底 `0x496b68` + **0x30**（0x496b98 - 0x496b68 = 0x30，與 `imul …,0x68` 的 stride 一致）→ 就是 **點數／點券欄位（16-bit）**。旁證：玩家資訊面板 `004165ea mov ax, word ptr [ebx + 0x496b98]` → `004165f2 call 0x457d61`（itoa）→ 畫在 (0x258,0x66)。獎勵訊息字串 `0x463797 = "得點券%d點"` 亦相互印證。
- 結束條件三種：(a) 挖到炸彈（型別1）→ 相位1 播完 → state=1；(b) 15 秒倒數（150 × 100 ms）歸零 → 依分數選相位 4/5/6 播完 → state=1；(c) state=2 後再倒數 20 tick（2 秒）→ KillTimer + PostMessage(0x402) 收攤。
- 「牆」判定：`word0==0` = 不可通行（`0x41213a je`、`0x4122cc jne`）；`word0≠0` = 可走。道具只放在 `word0≠0` 的格（`0x412014`）。

**奖罚数值** — 表格：項目 | 數值 | 立即數地址

| 項目 | 數值 | 立即數地址 |
|---|---|---|
| 小遊戲時間（tick 數） | 0x96 = 150（×100 ms = 15 s） | @source 0x004148b9: `mov dword ptr [0x48bd2c],0x96` |
| 開場滑鼠停用 tick | 0xa = 10（1 s） | @source 0x004148c3: `mov dword ptr [0x48bd7c],0xa` |
| SetTimer 週期 | 0x64 = 100 ms | @source 0x004148d9: `push 0x64` |
| 結束序列 tick | 0x14 = 20（2 s） | @source 0x00414a23: `mov dword ptr [0x48bd2c],0x14` |
| 分數門檻（低） | 0x28 = 40 → 相位5 + 音效0x47506f | @source 0x004149c8: `cmp ecx,0x28`、0x004149cd |
| 分數門檻（高） | 0x37 = 55 → 相位4 + 音效0x475067 | @source 0x004149eb: `cmp ecx,0x37`、0x004149ed |
| 停用分支：隨機加成基數 | 0x32 = 50 | @source 0x00415468: `add edx,0x32` |
| 停用分支：隨機加成模數 | 0x14 = 20 | @source 0x0041545e: `mov ebx,0x14` |
| 停用分支：訊息顯示參數 | 0x7d0 = 2000 | @source 0x00415484: `push 0x7d0` |
| 道具群組數量 | 3, 12, 3, 9, 1（型別1..5，共28） | 資料 @source 0x00411fc8（非立即數）：`0x411fc8: 03 00 00 00 0c 00 00 00 03 00 00 00 09 00 00 00 01 00 00 00` |
| 得分權重（型別2） | ×5 = `shl eax,2` + `add eax,edx` | @source 0x00413d9f/0x00413da2（無立即數乘法） |
| 得分權重（型別3） | ×12 = `shl eax,2`、`sub eax,edx`、`shl eax,2` | @source 0x00413d82..0x00413d87 |
| 得分權重（型別4） | ×8 = `shl ecx,3` | @source 0x00413d92 |
| 得分權重（型別5） | ×20 = `shl ecx,2`、`add ecx,edx`、`shl ecx,2` | @source 0x00413d72..0x00413d77 |
| 理論最高分 | 12×5 + 3×12 + 9×8 + 1×20 = 188 | 由上式與 0x411fc8 推得 |

- **停用／跳過路徑（本函式內，非上游）** @source 0x00415457..0x004154d7：
  `call 0x456f2d`(rand) → `0041545e mov ebx,0x14` → `sar edx,0x1f`/`idiv ebx`（C 語意 `rand()%20`，值域 **0..19**）→ `00415468 add edx,0x32` → **獎勵 = 50 + rand()%20 = 50..69**，寫入 `0041546b mov dword ptr [0x48bcec],edx`（即回傳值）。接著 `0041547c call 0x457110`（sprintf，"得點券%d點"）→ `0041548e call 0x440cac`（訊息框，第2參數 2000）→ 依 `player+0x13`（角色）與 `rand()&1` 從表 `0x48084a + 角色*0x6C + r*4` 取一句角色台詞 → `004154cf call 0x44ef41(player, 0, 台詞)`。
  表 `0x48084a` 為**未對齊**的 dword 指標陣列（每 4 byte 一項）：`[0]=0x466bd8"#1050別忌妒我！"`、`[1]=0x466be8"#1051鴻運當頭！"`；`[27]=…`（角色1 的兩句）。即每個角色 27 項、此處只用前兩句（**推斷**：0x6C = 27×4 的角色區塊）。
- 遊戲內道具→分數對照（型別 → 計數器 → 權重）：2 → `0x48bbb4` ×5；3 → `0x48bbb8` ×12；4 → `0x48bbbc` ×8；5 → `0x48bbc0` ×20；**型別1（炸彈）不計分且立刻結束遊戲**。
  `00413da6 mov dword ptr [0x48bcec],ecx` 展開後 = `5*c2 + 12*c3 + 8*c4 + 20*c5`（c2..c5 = 上表計數器）。
- 音效對照：型別2 → `snd[byte[0x475051+2]]=snd[4]`(id 0x10)；型別3/4 → `snd[5]`(id 0x11)；型別5 → `snd[6]`(id 0x12)；炸彈 → `0x47508f`(id 0x0f)；行走循環 → `0x475057`(id 0x0b)；到位 → `0x47505f`(id 0x0c)；高分結尾 → `0x475067`(id 0x0d)；低分結尾 → `0x47506f`(id 0x0e)。（`0x475051` 位元組表 = `00 00 04 05 05 06`）

**随机数使用点** — `_libc_rand` = `0x456f2d`。**本函式自身路徑只有 3 處**（遊戲進行中的每格更新完全不使用隨機數）：
1. `0x00415457 call 0x456f2d`（停用分支）：`idiv 0x14` → `rand()%20`，再 `+0x32`；決定「跳過小遊戲」時發放的點券 50..69。@source 0x00415457..0x0041546b。
2. `0x004154b6 call 0x456f2d`（停用分支續）：`and eax,1` → 在 `0x48084a + 角色*0x6C + r*4` 兩句中選一句角色台詞。@source 0x004154b6..0x004154be。
3. `0x0041208f call 0x456f2d`（在 `0x412014` 盤面初始化內、由 `0x00415395` 呼叫）：`imul eax,0x40` + `sar eax,0xf` → `rand()%64`，決定第 i 個道具要放在第幾個「合法格」（i = 群組 0..4 共 28 件，故初始化時共呼叫 28 次）。@source 0x0041208f..0x0041209a。
- 以遞迴展開（`call rel32` + `push imm32` 函式指標為根）可達的整體閉包中另有 `0x408328`、`0x40aa53`、`0x40de50` 三處 `call 0x456f2d`，但它們位於共用框架／對話框／事件處理函式（**非**小遊戲玩法程式碼，且不在 `0x415215`/`0x414858`/`0x412014`/`0x41211c`/`0x412287`/`0x4124c8`/`0x413a4a`/`0x41461b`/`0x414789` 之中）；歸屬為**推断**。
- 「炸彈/道具出現機率」不用隨機數：型別與件數完全由 `0x411fc8 = {3,12,3,9,1}` 與隨機選格決定。

**动画与输入接线点**
- IAT（已由 PE import descriptor 逐項核對，VA = ImageBase + FirstThunk RVA）：`0x462324 = USER32!SetTimer`（`0x004148e3 call dword ptr cs:[0x462324]`）、`0x4622fc = KillTimer`（`0x00414941`）、`0x462310 = PostMessageA`（`0x00401979`、`0x0041497a`）、`0x4622f8 = InvalidateRect`（`0x004148f4`）
  `0x462340 = ValidateRect`（`0x00414b82`）、`0x4622d8 = DefWindowProcA`（`0x00414b96`）、`0x4622ec = GetCursorPos`（`0x004151b0`）、`0x46231c = SetCursorPos`、`0x46230c = PeekMessageA`、`0x462334 = TranslateMessage`、`0x4622e0 = DispatchMessageA`、`0x46245c = WINMM!mciSendStringA`。
  ⚠ 任務提示把 `0x462310` 當成 SetTimer，實際是 **PostMessageA**；SetTimer 是 `0x462324`。
- `_Wait_0402_Message = 0x4018e7`（@source 0x004018e7）：`mov dword ptr [eax*4+0x48a010],edx`（把傳入的 WndProc 指標登錄到 0x48a010 表）→ `PostMessageA([0x48a0d4], 0x401, 0, param)` → `PeekMessageA` 迴圈（非 0x402 就 `TranslateMessage`+`DispatchMessageA`）→ 收到 `WM_USER+2 (0x402)` 時 `dec dword ptr [0x46cad8]` 並 `ret`。結束訊號 `0x401966(v)` = `PostMessageA([0x48a0d4],0x402,0,v)`（@source 0x00401966）。
- **實際接線**：`0x415215` 把 **`0x414858`** 交給 `0x4018e7`（`004153a5 push 0x414858`，原始 bytes `68 58 48 41 00` @0x4153a5）。
  ⚠ 任務描述「companion WndProc = 0x414fcd」有誤：`0x414fcd` 是被 **`0x4155fc`（事件型別 8 的另一個小遊戲）** 推入的（`004157d6 push 0x414fcd`，bytes `68 cd 4f 41 00` @0x4157d6）；`0x4154dc`（型別7）推 `0x414bbc`（`004155a0 push 0x414bbc`）。三者共用尾段（例：`00414c64 jmp 0x414a4a`、`00414aa4 jmp 0x41494f`）與同一組狀態全域，故舊 ASM 檔把 0x414fcd 標成 0x415215 的 WndProc 是錯的。
- WndProc 訊息對應（**0x414858**，@source 0x00414858 起）：
  `0x201/0x203` → `0x414aa9`（滑鼠點擊，見玩法第6步）；`0x401`(WM_USER+1) → `0x4148b9`（開局，見第4步）；`0x405`(WM_USER+5) → `0x414a51`（結尾畫面：`push -1/1/0/0` + `push [0x48bd3c]` + `call 0x45144f` 貼背景圖 → `call 0x41461b(0)` → 直接 blit → `0x4021f8(0x2a,1,0)` → `0x402460(1)`）；
  `0xf`(WM_PAINT) → `0x414b62`（表面 `[0x48a0dc]` vtable+0x1c blit + `ValidateRect`；任務提到的 `0x4151c1` 是 **0x414fcd** 的 WM_PAINT 尾段：`00415001 cmp eax,0xf / 00415004 je 0x4151c1`，確實在 0x414fcd 內而不屬於本函式）；`0x113`(WM_TIMER) → `0x414900`（見第5步）；其餘 → `0x414b8e`→`DefWindowProcA`。
  **WndProc 不處理 WM_KEYDOWN(0x100)、WM_KEYUP(0x101)、WM_MOUSEMOVE(0x200)、WM_COMMAND(0x111)** —— 分派邏輯 `cmp eax,0x201 / jb 0x41489e`、`0x41489e cmp eax,0xf / jb 0x414b8e`、`cmp eax,0x113 / je`，落在 [0x10,0x112] 的訊息（含 0x100/0x101/0x111）一律走 DefWindowProcA。本小遊戲**沒有鍵盤輸入**，唯一輸入是滑鼠左鍵。
- 動畫驅動：相位機在 `0x4124c8`（跳表 `0x4124ac`），由 WM_TIMER 每 100 ms 呼叫一次；`0x41461b` 只負責畫靜態盤面（開局與 0x405 各一次）。`0x413a4a` 為 HUD/得分計算（由 WM_TIMER 傳 2、由 `0x412f55` 傳 1、由 `0x4146e2` 傳 0）。
- 資源／音效／MIDI／free 接線：`0x450441` = 從 MKF 讀資源（`SetFilePointer`+`ReadFile`+`0x456f80` 配置，@source 0x00450463..0x004504cb）；`0x454176` = 音效資訊載入（effect.mkf，@0x00454176）；`0x454240` = 音效資訊釋放（@0x00454240）；`0x4542ce` = 播（`push id,handle`+`0x4540d8`）；`0x4542e9` = 停；`0x4549cf(n)` = MCI 播 MIDI 第 n 首；`0x454bcc` = MCI 續／等；`0x456e11` → `0x456e1f` = free；`0x456f60` → `0x458ae0` = memset。

**汇编摘录**
```asm
; ── 觸發：事件型別索引 6（跳表 0x4197e9 第 6 項）
00419840  shl      eax, 2
00419843  add      eax, edx
00419845  shl      eax, 3
00419848  mov      edx, dword ptr [0x498e80]
0041984e  add      eax, edx
0041985b  mov      ebx, dword ptr [eax + 0x24]
0041985e  and      ebx, 0xff
00419873  cmp      byte ptr [eax + 0x496b9f], 0
0041987e  jne      0x41b3d0
004198b2  jmp      dword ptr [ebx*4 + 0x4197e9]
0041b146  imul     ebx, dword ptr [0x49910c], 0x68
0041b14d  call     0x415215
0041b152  add      word ptr [ebx + 0x496b98], ax
; ── 前置閘門
00415226  cmp      byte ptr [eax + 0x496b7d], 1
0041522d  jne      0x415457
00415233  cmp      byte ptr [0x497159], 0
0041523a  je       0x415457
; ── 資源與初始化
00415245  call     0x454176
00415251  push     0x4e
0041525a  call     0x450441
00415262  mov      dword ptr [0x48bd3c], eax
00415322  lea      eax, [ebx + 0x56]
0041532c  call     0x450441
00415334  mov      dword ptr [ebx*4 + 0x48bd14], eax
00415341  mov      dword ptr [0x48bd04], 0x20000
0041534b  mov      dword ptr [0x48bd08], 0x60000
0041535d  mov      dword ptr [0x48bcf0], 0xffffffff
00415378  push     0x48bbb4
0041537d  call     0x456f60
00415395  call     0x412014
0041539c  call     0x4549cf
004153a5  push     0x414858
004153aa  call     0x4018e7
; ── WndProc 0x414858：開局 / 每格 / 滑鼠
004148b9  mov      dword ptr [0x48bd2c], 0x96
004148c3  mov      dword ptr [0x48bd7c], 0xa
004148e3  call     dword ptr cs:[0x462324]        ; SetTimer(hwnd,[0x46cad8],0x64,0)
004148ea  mov      dword ptr [0x48bd78], eax
00414922  dec      eax
00414941  call     dword ptr cs:[0x4622fc]        ; KillTimer
0041494a  call     0x401966                      ; PostMessage(0x402) → 收攤
004149c8  cmp      ecx, 0x28
004149eb  cmp      ecx, 0x37
00414a0a  call     0x4124c8
00414a16  jne      0x414a4a
00414a1c  mov      byte ptr [0x48bd58], 2
00414a23  mov      dword ptr [0x48bd2c], 0x14
00414a45  call     0x414789
00414ae3  mov      bx, cx
00414afc  shl      ecx, 7
00414b06  mov      cl, byte ptr [ecx + ebx]
00414b0f  mov      ebx, 9
00414b1b  idiv     ebx
00414b2f  call     0x41211c
00414b3f  call     0x412287
00414b44  mov      dword ptr [0x48bccc], 2
00414b55  call     0x4542ce
; ── 相位機與撿寶（0x4124c8）
00412593  cmp      eax, 6
0041259c  jmp      dword ptr [eax*4 + 0x4124ac]
004127d9  cmp      edx, eax
004127e2  call     0x4542e9
004127f9  mov      dword ptr [0x48bccc], 3
00412808  cmp      byte ptr [0x48bd5b], 0
00412837  call     0x41211c
004128c5  test     byte ptr [edx + 0x474d80], 0xf
004128d8  or       byte ptr [0x48bcc5], 1
004128eb  mov      dword ptr [0x48bd6c], eax
00412914  mov      word ptr [edx + 0x474d80], bx
004129ab  mov      dword ptr [0x48bccc], eax
004129e6  call     0x4542ce
004129fc  add      dword ptr [eax*4 + 0x48bbac], edx
00412b95  mov      byte ptr [0x48bd58], 1
00412f55  call     0x413a4a
; ── 得分公式（0x413a4a）
00413d6a  mov      edx, dword ptr [0x48bbc0]
00413d72  shl      ecx, 2
00413d77  shl      ecx, 2
00413d7a  mov      edx, dword ptr [0x48bbb8]
00413d87  shl      eax, 2
00413d8c  mov      ecx, dword ptr [0x48bbbc]
00413d92  shl      ecx, 3
00413d97  mov      edx, dword ptr [0x48bbb4]
00413da6  mov      dword ptr [0x48bcec], ecx
; ── 停用分支：50+rand()%20
00415457  call     0x456f2d
0041545e  mov      ebx, 0x14
00415466  idiv     ebx
00415468  add      edx, 0x32
0041546b  mov      dword ptr [0x48bcec], edx
00415472  push     0x463797                      ; "得點券%d點"
00415484  push     0x7d0
0041548e  call     0x440cac
004154b6  call     0x456f2d
004154bb  and      eax, 1
004154be  mov      esi, dword ptr [ebx + eax*4 + 0x48084a]
004154cf  call     0x44ef41
; ── 返回
004155ec  mov      eax, dword ptr [0x48bcec]
004155fb  ret
```

**未决** — 明確列出沒查清的，不猜：
1. **事件型別 6 == 「企鵝挖寶」格**：本函式內沒有任何字串指向名稱。名稱 0x465e64 只在「特殊地點」名稱表 `0x476080[3]` 出現，而該表在 exe 內找不到直接指令引用（0x476208 群組結構亦無直接引用，疑似由執行期或地圖資料填入）；事件型別位元組來自地圖節點資料（`0x498e80 + 節點*0x28 + 0x24`），該資料不在 exe。因此名稱與本函式的對應屬**推斷**（依字串表 + 玩法 + 上游檔名提示）。
2. **`0x475043` / `0x47504b` / `0x47504f` 三個 0x4750xx 常數的格式**：0x475043 = `80 02 e0 01`（=640,480，疑為畫面尺寸）只用於 `0x413248`/`0x41473b`；0x47504f 由 `0x414fcd`(0x4151ba) 與 `0x413248` 讀寫、0x47504b 由 `0x4155fc`(0x41572a) 寫入 — 三者屬於另兩個小遊戲（0x4154dc/0x4155fc），未細查。（本函式用的 `0x475051` 為道具型別→音效結構索引的 6 byte 表，已在前文列出 `00 00 04 05 05 06`。）
3. **影像 0x51（0x48bd38）的資源格式**：點擊命中測試直接以 `[0x48bd38] + y*640 + x` 取 byte，**未加** sprite sheet 慣用的 `+0xc` 標頭；是格式不同還是原程式 bug，未確認。也沒有把該 byte map 的實際像素內容取出比對（panel.mkf 不在本次取證範圍）。
4. **player+0x15 的其餘位元（0x10/0x20/0x30/0x40）與 player+0x37（0x496b9f）的語意**：只確認閘門條件（=1 / =0）與數個 test/or/and 站點（0x4079d0、0x401196、0x40cd5e、0x40d60e、0x40d6d1、0x409964、0x41c84f 等），未逐一定名。「人類玩家」「夢遊中只有型別0事件」是依這些站點與分派器邏輯的**推断**。
5. **`0x440cac(buf, 0x7d0)` 的精確定義**：只確認它會 `0x4024a1`/`0x402460`/`0x44f9d8` 畫框並使用 `[0x48bdb8..0x48bdc4]`；0x7d0 是否為「顯示毫秒數」未定。
6. **撞牆後的「沿牆滑行」行為**：`0x412808` 在 `[0x48bd5b]!=0` 時重新 `0x41211c` 再 `0x412287`，且**丟棄** `0x41211c` 的回傳值；若目標長期被牆擋住是否會一直重試到時間到，未以動態驗證確認（**推断**為沿牆滑行）。
7. **停用分支台詞表的完整結構**：只確認 `0x48084a` 為未對齊 dword 指標陣列、`0x48084a + 角色*0x6C + r*4`，並讀出前幾項字串；「每角色 27 句」為算術**推断**，未展開 12 個角色驗證。
8. **`0x48bbb0`（型別1 計數器）**：被 `0x4129fc` 累加、不在 `memset(0x48bbb4,0,0x10)` 範圍內、也不參與任何得分公式；是否有其他用途未確認。
9. 任務列出的 helper `0x413248`、`0x414ba4`、`0x414c69`、`0x414dec`、`0x414e8d`、`0x414f6b`、`0x415156`、`0x41518a`、`0x4151fd`、`0x414fcd` **不屬於本函式（0x415215）的呼叫樹**，而是 0x4154dc / 0x4155fc 兩個小遊戲及其 WndProc（0x414bbc / 0x414fcd）的程式碼；本次僅確認其接線（推入 0x4018e7 的位址與 IAT），未展開其玩法。
