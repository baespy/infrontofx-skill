# Review และ Audit

รีวิวแบบ lazy senior คือคิดแบบคนที่ต้องตื่นมาแก้ตอนระบบพัง และอยากให้มีโค้ดน้อยที่สุด เช็กลิสต์รายข้ออยู่ที่ไฟล์ `checklists/review.md` ของ infrontofx ไฟล์นี้บอกวิธีรีวิว วิธีรายงาน การออดิตทั้งโฟลเดอร์ บัญชีหนี้เทคนิค และการรับรีวิวจากที่อื่น

## รีวิวหนึ่ง resource เทียบ backup

1. ยืนยันว่ามี backup และ `git -c core.autocrlf=false diff --no-index --stat <backup> <resource>` ไม่ว่าง ถ้าไม่มี backup ให้รีวิวทั้ง resource และบอกในรายงาน
2. อ่าน diff แล้วอ่านโค้ดที่มันแตะ: ผู้เรียกของทุก method ที่เปลี่ยน, อีกฝั่งของทุก event, JS ที่เรียก NUI callback และ resource อื่นที่เรียก export (คำสั่งหาผู้เรียกอยู่ใน `references/plan.md`)
3. รัน lint, รายการสัญญา และ method ครบ ตาม `references/verify.md`
4. ไล่ตามลำดับของเช็กลิสต์รีวิว: authority -> boundaries -> lifecycle -> performance -> style แล้วจบด้วยหัวข้อ "ล่าโค้ดที่ลบได้" ทุกครั้ง
5. ตัดสินแยกสองแกน ห้ามรวมกัน
   - **แกนมาตรฐาน** กฎใน `SKILL.md` ของ infrontofx, เช็กลิสต์รีวิว และผล lint
   - **แกนโจทย์** ทำครบตามที่เจ้าของขอไหม ทำเกินไหม สัญญาและสิ่งที่ผู้เล่นเห็นยังเหมือน backup ไหม
6. คิดที่โหลด 1,600 คน เว้นแต่ resource นั้นใช้เฉพาะแอดมิน และบอกโหลดที่สมมติไว้ในรายงาน

ทุกข้อที่รายงานต้องมีกรณีจริง (จำนวนคน ค่าที่ส่ง จังหวะเวลา) เช่น "สองคนกดรับพร้อมกันระหว่าง await ได้รางวัลคนละสองชิ้น" ไม่มีกรณีจริงไม่ใช่ข้อค้นพบ อ่านบรรทัดซ้ำก่อนรายงานว่าผู้เรียกมีอยู่จริง ค่าเป็น nil ได้จริง และโค้ดไม่ถูกใช้จริง ไม่รายงานรสนิยม ไม่เขียน "ลองพิจารณา"

## ล่าโค้ดที่ลบได้

ถามทุก block ว่า "ลบได้ไหม" ก่อนถามว่า "แก้ยังไง"

| เจอ | ทำ |
| --- | --- |
| ของตาย: method, callback หรือ event ที่ไม่มีใครเรียก, ไฟล์ที่ manifest ไม่โหลด, key ใน `Config` ที่ core ไม่อ่าน, โหมด preview หรือ mock | grep ทั้งโปรเจกต์รวมไฟล์ build ของหน้าเว็บก่อน แล้วลบ |
| ตัวห่อบรรทัดเดียวที่แค่ส่งต่อ export หรือ event | เขียนคำสั่งจริงตรงจุดที่เรียก |
| เขียนซ้ำของที่ `1nfx_lib` มีแล้ว: loop วัดระยะ, throttle หรือ lock ทำเอง, คู่ event ไป-กลับ, spawn และลบ entity เอง, เรียก `PlayerPedId()` ซ้ำใน loop, LRU หรือ heap ทำเอง | `lib.points` `lib.zones` `lib.grid`, `lib.guard`, `lib.callback`, `lib.spawn`, `cache`, `lru` `heap` `ringbuffer` |
| loop ซ้ำ: `while true` หลายตัวจังหวะเดียวกัน, ส่ง NUI ข้อมูลเดียวกันจากสอง loop | loop กลางตัวเดียวที่มีตัวนับต่อหัวข้อ |
| fallback หลายชั้น, เช็ก `GetResourceState` กับ provider ที่ต้องมีอยู่แล้ว | เหลือทางเดียวที่เซิร์ฟมีจริง |

สรุปยอดเป็น `ลดได้ราว -N บรรทัด`

## รูปแบบรายงานรีวิว

- สามกลุ่ม **ต้องแก้** (บั๊ก ช่องโหว่ ของหรือเงินงอก ข้อมูลหาย พังที่โหลดจริง), **ควรแก้** (ช้าจริง ซ้ำ โค้ดที่ไม่ควรมี ผิดมาตรฐาน), **มีก็ดี** (เร็วขึ้นเล็กน้อย เขียนสั้นลง) กลุ่มที่ว่างไม่ต้องเขียน
- เลขข้อต่อเนื่องข้ามกลุ่ม เจ้าของสั่ง "แก้ 2, 5" ได้ทันที
- ทุกข้อมี `ไฟล์:บรรทัด`, ปัญหาพร้อมกรณีจริง, วิธีแก้ที่เล็กที่สุด (ลบได้ยิ่งดี) และผลถ้าไม่แก้
- แกนมาตรฐานกับแกนโจทย์อยู่คนละหัวข้อ
- ปิดท้ายด้วยผลตัดสิน ยอดที่ลดได้ และสิ่งที่ยังไม่ได้ตรวจ

```text
แกนมาตรฐาน
ต้องแก้
1. core/sv_main.lua:88 handler รับ amount จาก client แล้วจ่ายตรง ส่ง 999999 มาได้เงินเท่านั้น
   แก้: lib.guard.toAmount และตรวจยอดฝั่ง server / ถ้าไม่แก้: ปั๊มเงินได้
ควรแก้
2. core/cl_main.lua:40 while true กับ Wait(0) วัดระยะ 30 จุดทุกเฟรมแม้อยู่ไกล
   แก้: lib.points / ถ้าไม่แก้: กิน CPU ของทุก client ตลอดเวลา
แกนโจทย์
ไม่มีข้อค้นพบ สัญญาเท่า backup
ผลตัดสิน: แก้ข้อ 1 ก่อน
ลดได้ราว -40 บรรทัด
ยังไม่ได้ตรวจ: html/ ที่เป็นไฟล์ build
```

หลังรีวิว ข้อที่เป็นบั๊ก ช่องโหว่ หรือ perf แก้ได้เลยโดยไม่ต้องถามไม่ว่าอยู่กลุ่มไหน (ทีละ resource สำรองก่อน) แล้วรายงานพร้อมหลักฐานตาม `references/verify.md` ข้อที่ต้องเปลี่ยนสัญญาหรือเปลี่ยนสิ่งที่ผู้เล่นเห็นรอเจ้าของตัดสิน ข้อที่เหลือรอคำสั่งแบบ "แก้ 2, 5" เว้นแต่งานนั้นเป็นการรีไรต์หรือ optimize อยู่แล้ว

## ออดิตทั้งโฟลเดอร์

ใช้กับโฟลเดอร์ใหญ่ เช่น `resources/[resources]/[1nfx]` resource ที่มีไฟล์ `.fxap` (escrow) หรือถูก obfuscate ให้ข้าม ห้ามเปิดแกะหรือแก้

```powershell
$pack = "<project>\.claude\skills\infrontofx"
$root = "<project>\resources\[resources]\[1nfx]"
$res = Get-ChildItem -LiteralPath $root -Directory | Where-Object { -not (Test-Path -LiteralPath (Join-Path $_.FullName ".fxap")) }
$lua = $res | ForEach-Object { Get-ChildItem -LiteralPath $_.FullName -Recurse -File -Filter *.lua } | Where-Object { $_.FullName -notmatch '\\(node_modules|stream|dist)\\' }
$show = { "{0}:{1}  {2}" -f $_.Path.Substring($root.Length + 1), $_.LineNumber, $_.Line.Trim() }
```

**1. lint ทุกตัว** บรรทัดสรุปต่อ resource แล้วนับกฎที่เจอบ่อยที่สุด

```powershell
$res | ForEach-Object { "{0,-28} {1}" -f $_.Name, (node "$pack\scripts\lint-resource.mjs" $_.FullName | Select-Object -Last 1) }
node "$pack\scripts\lint-resource.mjs" @($res.FullName) | Select-String -Pattern '\[(error|warn)\] ([\w-]+)' | ForEach-Object { $_.Matches[0].Groups[1].Value + " " + $_.Matches[0].Groups[2].Value } | Group-Object | Sort-Object Count -Descending | ForEach-Object { "{0,5} {1}" -f $_.Count, $_.Name }
```

**2. ค้นจุดเสี่ยงที่ lint จับไม่หมด**

| บล็อก | มองหา | ทำไมสำคัญที่ 1,600 คน | กฎ lint ที่ช่วย |
| --- | --- | --- | --- |
| A | `Wait(0)` ตอนว่าง | กิน CPU ของทุก client ตลอดเวลา | `wait-zero` |
| B | `TriggerClientEvent` ถึง `-1` ใน loop หรือ timer | ข้อความคูณจำนวนคนทุกรอบ | `latent-broadcast` (เฉพาะ latent) |
| C | query DB ใน loop | await ต่อแถวหรือต่อคน server ค้างเป็นช่วง | ไม่มี |
| D | ตาราง `[src]` แต่ไม่มี `playerDropped` | หน่วยความจำโตไม่หยุด id ที่ถูกใช้ซ้ำได้ค่าของคนเก่า | ไม่มี |
| E | handler ฝั่ง server รับค่าแบบ price, amount, reward, coords | ปั๊มของ ปั๊มเงิน วาร์ป ถ้า server ไม่ตรวจเอง | `client-identity`, `client-economy` |
| F | ตาราง `FC` และค่าคงที่ระดับไฟล์ | ผิดมาตรฐาน มีชั้นห่อซ้อน | `no-fc`, `no-config-function`, `no-file-constant` |

```powershell
"A"; $lua | Select-String -Pattern '\bWait\(\s*0\s*\)' | Group-Object { $_.Path.Substring($root.Length + 1).Split('\')[0] } | Sort-Object Count -Descending | ForEach-Object { "{0,5} {1}" -f $_.Count, $_.Name }
"B"; $lua | Select-String -Pattern 'TriggerClientEvent\s*\([^,]+,\s*-1' -Context 12, 0 | Where-Object { $_.Context.PreContext -match '\b(while|for|SetInterval|CreateThread|SetTimeout)\b' } | ForEach-Object $show
"C"; $lua | Select-String -Pattern 'MySQL\.\w+|oxmysql' -Context 8, 0 | Where-Object { $_.Context.PreContext -match '^\s*(for|while)\b' } | ForEach-Object $show
"D"; $res | Where-Object { $f = Get-ChildItem -LiteralPath $_.FullName -Recurse -File -Filter *.lua; ($f | Select-String -Pattern '\[\s*(src|source|playerId)\s*\]\s*=' -List) -and -not ($f | Select-String -SimpleMatch "playerDropped" -List) } | ForEach-Object Name
"E"; $lua | Where-Object Name -like "sv_*" | Select-String -Pattern '(RegisterNetEvent|lib\.callback\.register)\s*\([^,]+,\s*function\s*\([^)]*\b(price|cost|amount|reward|money|count|coords)\b' | ForEach-Object $show
"F"; $lua | Select-String -Pattern '\bFC\b|^local [A-Z][A-Z0-9_]* = ' -CaseSensitive | ForEach-Object $show
```

`Select-String` ไม่สนตัวพิมพ์เล็กใหญ่เป็นค่าเริ่มต้น บล็อก F จึงต้องมี `-CaseSensitive` ไม่อย่างนั้นจะจับ `local scriptname =` ไปด้วย

**3. ยืนยันทุกจุด** ผลค้นจับเกินได้ (loop ที่ปิดไปแล้วก่อน query, amount ที่ server ตรวจอยู่แล้ว) เปิดอ่านบรรทัดจริงทุกจุด แล้วใส่กรณีจริงตามกติการีวิวก่อนนับเป็นข้อค้นพบ

**4. รายงานเป็นตารางเดียว** เรียงจากร้ายแรงที่สุด ไม่เกิน 20 แถวต่อ resource ที่เหลือสรุปเป็นจำนวน ลำดับความร้ายแรง: ช่องโหว่ ของหรือเงินงอก ข้อมูลหาย > พังหรือกระตุกเมื่อคนเยอะ > ผิดบางกรณี > เปลือง CPU ตอนว่าง > ผิดมาตรฐานหรือลบได้

```text
| # | ระดับ | resource | ไฟล์:บรรทัด | ปัญหา (กรณีจริง) | ที่ 1,600 คน | แก้ |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | ต้องแก้ | <resource> | core/sv_main.lua:96 | deposit รับ amount จาก client ไม่ตรวจยอดในตัว | ปั๊มเงินได้ทุกคน | lib.guard.toAmount และตรวจยอดฝั่ง server |
| 2 | ต้องแก้ | <resource> | core/sv_state.lua:210 | ส่งถึง -1 ทุกครั้งที่จำนวนคนในโซนเปลี่ยน | 1,600 ข้อความต่อครั้ง | ส่งเฉพาะคนในโซน |
```

**5. แก้ตามลำดับในตาราง** ทีละ resource ตาม `references/plan.md` สำรองก่อนทุกตัว

## บัญชีหนี้เทคนิค

ทางลัดที่ตั้งใจทิ้งไว้จดเป็นแถวใน `PROGRESS.md` ของเจ้าของ หัวข้อ "หนี้เทคนิค" ห้ามเขียน comment แบบ `TODO` หรือ `shortcut:` ในโค้ด

```markdown
## หนี้เทคนิค
| ที่ | ทางลัด | รับได้ถึง | ยกระดับเมื่อ |
| --- | --- | --- | --- |
| <resource>/core/sv_main.lua:Save | เขียน DB ทั้งก้อนทุก 60 วินาที | ราว 300 แถว | เกิน 1,000 แถว หรือ save นานเกิน 50 ms |
```

- ทุกแถวต้องมีช่อง "ยกระดับเมื่อ" แถวที่ไม่มีคือข้อค้นพบในตัวมันเอง
- อ่านบัญชีนี้ก่อนเริ่มออดิตทุกครั้ง แถวที่ถึงเงื่อนไขแล้วขึ้นเป็นข้อ "ต้องแก้"
- จ่ายหนี้แล้วลบแถวนั้นออก

## รับรีวิวจากที่อื่น

ใช้เมื่อเจ้าของส่งผลรีวิวจาก agent อื่น เครื่องมืออื่น หรือคนอื่นมาให้

1. เขียนแต่ละข้อใหม่ด้วยคำของตัวเองเพื่อยืนยันว่าเข้าใจตรง ข้อที่ไม่ชัดให้ถามเฉพาะข้อนั้น
2. ตรวจทางเทคนิคกับโค้ดจริงก่อนรับ: เปิดบรรทัดนั้น grep ผู้เรียก รัน lint หรือวงทดสอบ
3. ข้อที่ผิด ขัดกฎของชุด หรือขัดสัญญา ให้แย้งพร้อมหลักฐาน (บรรทัด ผล grep กฎที่ขัด) เช่น ข้อเสนอให้เพิ่ม comment, ตัวห่อหรือ abstraction, `dependencies` ใน manifest หรือตรวจค่าซ้อนทุกชั้น
4. ก่อนสร้างของ "ให้ถูกหลัก" ตามรีวิว grep ดูว่ามีคนใช้จริงไหม ไม่มีคนใช้ไม่ต้องสร้าง
5. ทำข้อที่ขวางงานก่อน ต่อด้วยข้อง่าย แล้วข้อซับซ้อน ตรวจทีละข้อ
6. ตอบเป็น `แก้แล้ว: <ข้อ> <หลักฐาน>` หรือ `ไม่แก้: <ข้อ> เพราะ <หลักฐาน>` ไม่ขอบคุณ ไม่ชมรีวิว และไม่รับข้อที่ยังไม่ได้ตรวจ
