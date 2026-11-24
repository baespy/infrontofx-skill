# Verify

ห้ามพูดว่า เสร็จ ผ่าน แก้แล้ว หรือเร็วขึ้น ถ้ายังไม่มีหลักฐานสดของรอบนี้ หลักฐานสดคือผลของคำสั่งที่รันหลังการแก้ครั้งสุดท้ายของ resource นั้น ผลที่รันก่อนแก้ไม่นับ รายงานของ agent อื่นเป็นแค่คำอ้าง ต้องเปิดไฟล์และรันตัวตรวจเอง

## ห้าขั้นก่อนอ้าง

1. เลือกคำสั่งที่พิสูจน์คำที่จะพูด (ตารางถัดไป)
2. รันใหม่หลังการแก้ครั้งสุดท้าย
3. อ่าน output ทั้งหมดและ exit code ไม่ใช่แค่บรรทัดท้าย
4. เทียบกับคำที่จะพูด ไม่ตรงให้แก้ต่อ หรือรายงานตามที่เห็นจริง
5. อ้างพร้อมตัวเลข เช่น `lint 0 error(s), 2 warning(s)`

คำที่ใช้แทนหลักฐานไม่ได้: น่าจะ, ควรจะได้, ดูเหมือน, เรียบร้อย

## คำที่จะพูดกับหลักฐานที่ต้องมี

| จะพูดว่า | ต้องมี |
| --- | --- |
| lint ผ่าน | บรรทัดท้าย `0 error(s), ...` และ exit 0 อ่าน warning ครบทุกตัว แก้หรืออธิบายได้ |
| ไม่มี comment, block และวงเล็บครบ, ไม่มี `FC` และค่าคงที่ระดับไฟล์ | lint ไม่มีกฎ `no-comments`, `unbalanced-blocks`, `unbalanced-brackets`, `no-fc`, `no-local-function`, `no-file-constant` (lint นับ keyword หลังตัด string และ comment ออกแล้ว ห้ามนับเองด้วย grep ธรรมดา) |
| สัญญาเดิมครบ | บล็อกรายการสัญญาไม่มีบรรทัด `<=` หรือทุกบรรทัดมีเหตุผลในรายงาน |
| method ครบ | บล็อก method ที่เรียกแต่ไม่มีนิยาม ไม่แสดงชื่อใดที่เป็นของโมดูลนี้ |
| ถอด debug หมด | คำสั่งค้นป้ายตัวพิมพ์ชั่วคราวจาก `references/debug.md` ไม่เจออะไร |
| บั๊กหาย | วงทดสอบใน `references/debug.md` ไม่เกิดอาการ และ error บรรทัดเดิมไม่ขึ้นอีก |
| skill ถูกต้อง | ไฟล์ `scripts/validate-skill.mjs` ของ infrontofx พิมพ์ `infrontofx validation passed.` |
| prop ผ่าน | `RESULT fail=0 warn=0` ทุกไฟล์จาก `prop-forge/scripts/blender/validate_prop.py` |
| ปั้นเนียนผ่าน | `sculpt-forge/scripts/blender/validate_sculpt.py` รายงาน fail=0 ตามเกณฑ์ใน SKILL.md ของ sculpt-forge |
| แมพผ่าน | `MAP_INSPECT_PASS fail=0` จาก `map-forge/scripts/blender/inspect_map.py` |
| เร็วขึ้น เบาลง | ตัวเลขก่อนและหลังจากสถานการณ์เดียวกัน ตามหัวข้อ "วัดก่อน-หลัง" |
| ใช้ได้ในเกม | เจ้าของรายงานผลเอง ก่อนหน้านั้นเขียนว่า "ต้องลองในเกม" |

ภาพ preview จาก Eevee หรือ Cycles ไม่ใช่หลักฐานว่าในเกมถูก

## คำสั่งตรวจ

ตั้งค่าครั้งเดียวต่อหน้าต่าง PowerShell:

```powershell
$pack = "<project>\.claude\skills\infrontofx"
$old = "<project>\_backup\<YYYY-MM-DD>\<resource>"
$new = "<project>\resources\[resources]\[1nfx]\<resource>"
```

`$pack` คือโฟลเดอร์ที่ติดตั้งชุด infrontofx จริง เครื่องที่ไม่มี node ใน PATH ให้เติมโฟลเดอร์ node แบบ portable ก่อน เช่น `$env:Path = "<project>\.tools\node;" + $env:Path` พาธที่มี `[ ]` ต้องใช้ `-LiteralPath` เสมอ

**lint**

```powershell
node "$pack\scripts\lint-resource.mjs" $new
"exit=$LASTEXITCODE"
```

**ไฟล์ที่เปลี่ยน** git จบด้วย exit 1 เมื่อสองโฟลเดอร์ต่างกัน เป็นเรื่องปกติ ไม่ใช่ error

```powershell
git -c core.autocrlf=false diff --no-index --stat $old $new
```

**รายการสัญญา** เทียบ backup กับของใหม่ `<=` คือมีใน backup แต่หายไป ต้องไม่มี หรืออธิบายได้ทุกบรรทัด `=>` คือเพิ่มใหม่ ตรวจว่าตั้งใจ กลุ่ม `events` ครอบ `RegisterNetEvent`, `AddEventHandler`, `RegisterNUICallback`, `lib.callback.register`, `RegisterCommand` และ `exports(` กลุ่มอื่นคือ `action` ของ NUI, ตาราง DB และ key ใน `Config` ที่ core อ่าน

```powershell
$list = {
    param($dir, $rx)
    Get-ChildItem -LiteralPath $dir -Recurse -File -Filter *.lua |
        ForEach-Object { [regex]::Matches([IO.File]::ReadAllText($_.FullName), $rx) } |
        ForEach-Object { (($_.Groups[1].Value + " " + $_.Groups[2].Value) -replace "\s+", " ").Trim() } |
        Sort-Object -Unique
}
$checks = [ordered]@{
    events = '(RegisterNetEvent|AddEventHandler|RegisterNUICallback|lib\.callback\.register|RegisterCommand|exports)\s*\(\s*([^,)]+)'
    nui = '(action)\s*=\s*("[^"]+")'
    sql = '(?i)\b(FROM|INTO|UPDATE|JOIN)\s+`?(\w+)'
    config = '()(Config(?:\.\w+)+)'
}
foreach ($label in $checks.Keys) {
    "=== $label"
    Compare-Object @(& $list $old $checks[$label]) @(& $list $new $checks[$label]) |
        ForEach-Object { "{0} {1}" -f $_.SideIndicator, $_.InputObject }
}
```

ดูฝั่งเดียว (ใช้ตอนวางแผน ก่อนแก้) ประกาศ `$list` และ `$checks` จากบล็อกบนก่อน แล้วรัน `foreach ($label in $checks.Keys) { "=== $label"; & $list $new $checks[$label] }`

แบบ grep ใน Git Bash สำหรับกลุ่ม `events` (`<` คือมีแค่ใน backup, `>` คือมีแค่ในของใหม่):

```bash
rx='(RegisterNetEvent|AddEventHandler|RegisterNUICallback|lib\.callback\.register|RegisterCommand|exports)[[:space:]]*\([[:space:]]*[^,)]+'
diff <(grep -rhoE --include='*.lua' "$rx" "<backup>" | tr -s ' ' | sort -u) <(grep -rhoE --include='*.lua' "$rx" "<resource>" | tr -s ' ' | sort -u)
```

**method ที่เรียกแต่ไม่มีนิยาม** ชื่อที่ขึ้นมาอาจเป็น method ของตารางอื่น (เช่น `GlobalState:set`) เปิดดูก่อนสรุป

```powershell
$code = (Get-ChildItem -LiteralPath $new -Recurse -File -Filter *.lua | ForEach-Object { [IO.File]::ReadAllText($_.FullName) }) -join "`n"
$defined = [regex]::Matches($code, 'function\s+[\w.]+[:.](\w+)\s*\(|(\w+)\s*=\s*function\s*\(\s*self\b') | ForEach-Object { $_.Groups[1].Value + $_.Groups[2].Value } | Sort-Object -Unique
[regex]::Matches($code, '(?:\bself|\b[A-Z]\w*):(\w+)\s*\(') | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique | Where-Object { $_ -notin $defined }
```

**ชุด skill** หลังแก้ไฟล์ใดๆ ในชุด infrontofx

```powershell
node "$pack\scripts\validate-skill.mjs"
```

**asset จาก forge** `<blender>` คือ `blender.exe` รุ่นที่ forge นั้นกำหนด

```powershell
& "<blender>" -b --factory-startup -P "$pack\prop-forge\scripts\blender\validate_prop.py" -- --blend "<ไฟล์ .blend หรือโฟลเดอร์>"
& "<blender>" -b -P "$pack\map-forge\scripts\blender\inspect_map.py" -- --dir "<โฟลเดอร์ stream>"
```

`validate_sculpt.py` ใช้คำสั่งและเกณฑ์ตาม SKILL.md ของ sculpt-forge

## วัดก่อน-หลัง

- วัดก่อนแก้เสมอ ใช้สถานการณ์เดียวกันทั้งสองรอบ: จำนวนผู้เล่น จุดที่ยืน ฟีเจอร์ที่เปิด ระยะเวลา และวิธีวัด
- ดู spike ไม่ใช่แค่ค่าเฉลี่ย ไม่มีเกณฑ์ ms ตายตัว ใช้ผลวัดตั้งงบของ resource นั้น (ไฟล์ `skills/common/performance.md` ของ infrontofx)
- แยกตัวเลขแต่ละชนิด ห้ามรวมเป็นคะแนนเดียว

| รายการ | ก่อน | หลัง | วิธีวัด |
| --- | --- | --- | --- |
| client ms ตอนว่าง และตอนใช้งาน | | | `resmon 1` อย่างละ 60 วินาที |
| spike สูงสุด | | | `profiler record 500` แล้ว `profiler view` |
| ข้อความ network ต่อวินาที | | | นับจากโค้ด: ครั้งต่อวินาที × ผู้รับ |
| query DB ต่อนาที | | | นับจากโค้ด หรือ log ของ oxmysql |
| NUI message ต่อวินาที | | | NUI devtools |

วัดในเครื่องไม่ได้เพราะต้องมีผู้เล่นจริง ให้ใส่ตัวเลขที่คำนวณจากโค้ดโดยบอกว่าเป็นค่าคำนวณ แล้วย้ายการวัดจริงไปไว้ใน "ต้องลองในเกม"

## เช็กลิสต์ทดสอบในเกม

ส่งให้เจ้าของเฉพาะข้อที่ตรงงาน ข้อละหนึ่งการกระทำ พร้อมผลที่ต้องเห็น

1. server console: `refresh` แล้ว `ensure <resource>` ต้องไม่มี `SCRIPT ERROR`
2. เข้าเกม เปิด F8 ทิ้งไว้ 60 วินาที ต้องไม่มี error
3. ทำสิ่งที่งานนี้แก้ทีละขั้น ทุกขั้นมีผลที่ต้องเห็น
4. `restart <resource>` สองครั้ง ต้องไม่มี blip, point, prop หรือ UI ซ้ำ และเมาส์ไม่ค้าง
5. สองคนทำพร้อมกัน, กดรัว, ออกเกมกลางคัน, อยู่ต่าง routing bucket, อยู่ไกลเกินระยะ ต้องไม่ได้ของซ้ำและไม่ค้าง
6. `resmon 1` ตอนว่างและตอนใช้งาน จดตัวเลขส่งกลับมา
7. asset ที่ stream: เข้าเกมใหม่ ดูที่ระยะ 2, 10 และ 50 เมตร เดินชน และดูตอนกลางคืน ไฟล์ stream ให้เปลี่ยนตอน restart เซิร์ฟรอบถัดไปของ txAdmin ไม่เปลี่ยนระหว่างมีผู้เล่น

## แม่แบบรายงาน

```text
<resource>: <ผลหนึ่งบรรทัด>
backup: _backup/<YYYY-MM-DD>/<resource>
เปลี่ยน:
- <ไฟล์:บรรทัด หรือ method> <เดิม> เป็น <ใหม่> เพราะ <เหตุผลสั้น>
พฤติกรรมที่ผู้เล่นเห็นเปลี่ยน: ไม่มี | <อะไร>
ตรวจแล้ว: lint 0 error(s) exit 0, สัญญาเทียบ backup ไม่มี <=, method ครบ, <ตัวเลขก่อน-หลัง>
ยังไม่ได้ตรวจ: <อะไร และทำไม>
ต้องลองในเกม:
1. <การกระทำ> -> <ผลที่ต้องเห็น>
ตัดสินใจเอง: <อะไร> เพราะ <เหตุผล> ถ้าผิดเสีย <อะไร>
```

บรรทัดที่ว่างให้ตัดทิ้ง ยกเว้น "ตรวจแล้ว" และ "ต้องลองในเกม" ที่ต้องมีเสมอ
