# Tools and AI generation (full text)

Every script with its flags and the three generation routes, moved here from `SKILL.md` on 2026-11-24. The machine has no Python, Node or ImageMagick for this skill; everything runs on PowerShell and Chrome.

## Scripts

| สคริปต์ | หน้าที่ |
| --- | --- |
| `scripts/generate.ps1 -PromptFile p.txt -Out a.png [-Ref x.jpg,y.jpg] [-Aspect 4:5] [-Size 2K] [-Model pro\|fast] [-Count 1]` | เจนภาพด้วย Gemini รับรูปอ้างอิงได้ถึง 14 รูป ไม่เขียนทับไฟล์เดิม แสดงราคาโดยประมาณ |
| `scripts/render.ps1 -Spec x.json [-Out y.png]` | เรนเดอร์เป็น PNG บนการ์ดจอ แสดงชื่อ GPU ที่ใช้ และคำเตือน `POSTER-WARN` |
| `scripts/cutout.ps1 -In a.jpg -Out a.png [-Tolerance 26]` | ลบพื้นหลังเรียบจากขอบภาพเข้าหาตัวแบบ แล้วครอปชิด |
| `scripts/cutout.ps1 -In a.jpg -Out a.png -Chroma` | ลบกรีนสกรีน พร้อมลดสีเขียวที่ติดขอบ |
| `scripts/cutout-white.ps1 -In a.jpg -Out a.png -Keep "x,y ..." [-Free ..] [-Drop ..] [-Crop ..]` | ตัดตัวละครจากรูปต้นฉบับพื้นขาวแม้ใส่เสื้อขาว ใช้เส้น polygon (พิกัดพิกเซล) หลายรูปแบ่งด้วย `;` ภาพคู่/ตัวมืดใส่ `-Pocket 0 -Halo 0` |
| `scripts/agy-gen.ps1 -Ref a.jpg[,b.jpg] -Prompt "..." -Out x.png` หรือ `-Batch jobs.json` | เจน/แก้ภาพด้วย Gemini ผ่าน Antigravity CLI (ไม่ต้องมี API key) หลายงานขนาน ตั้งชื่อไฟล์ให้ขึ้นต้นด้วย `jobN_` เพื่อจับคู่ผลกับงาน และคัดลอกให้ที่ `-Out` ตรวจผลด้วยตาทุกครั้ง |
| `scripts/hero-prep.ps1 -In work\ai2\char_outfit.png -Out work\hero_char.png` | ขั้นเดียวจากภาพพื้นเขียวของ Gemini: ตัดพื้นเขียว → ครอปแนวนอนให้ชิดตัว (คงความสูงเต็ม) → ขยาย + ลับความคม พร้อมใส่ใน `heroes[0].src` |
| `scripts/fill-holes.ps1 -In hero.png -Out hero_f.png [-Color '#1a0610' -MinArea 150]` | หาช่องโปร่งใสที่ถูกล้อมอยู่ในตัวละคร (ไม่เชื่อมกับขอบภาพ) แล้วถมสีเข้ม ให้ช่องระหว่างผมกับคอดูเป็นเงา ไม่ใช่แผ่นพื้นหลังสว่าง ใช้หลัง hero-prep |
| `scripts/upscale.ps1 -In hero.png -Out hero_x.png [-Scale 1.6]` | ขยายตัวละครที่ตัดแล้ว + ลับความคม (ภาพ AI ~1000 px ขึ้นโปสเตอร์ 1920) |

**เรนเดอร์บนการ์ดจอเท่านั้น.** ถ้า Chrome ใช้การ์ดจอจริงไม่ได้ `render.ps1` จะหยุดและไม่สร้าง PNG ห้ามแก้ด้วยการเปิดซอฟต์แวร์เรนเดอร์หรือใส่ `--disable-gpu` ให้รายงานข้อความ error ให้ผู้ใช้แทน

**รูปพื้นขาว + เสื้อขาว.** `cutout.ps1` ตรง ๆ ทำเสื้อและมือเป็นรู ให้เลือก (1) `cutout-white.ps1` ตัดจากพิกเซลต้นฉบับด้วยเส้น polygon ที่วาดตามขอบ (คมที่สุด ไม่เปลี่ยนตัวละคร) หรือ (2) ให้ Gemini ทำพื้นเขียวจากภาพนั้นด้วย `agy-gen.ps1` แล้ว `cutout.ps1 -Chroma` (ใช้เมื่อผู้ใช้ขอเปลี่ยนสีผม/ของประดับ/มุมกล้องด้วย) ตรวจลายน้ำศิลปินก่อนใช้ทุกครั้ง ดู `references/support-styles.md`

`-Tolerance` เริ่มที่ค่าเดิม แล้วเพิ่มทีละน้อย เสื้อผ้าสีเดียวกับพื้นหลังจะเริ่มเป็นรูเมื่อค่าสูงเกินไป มาสคอตพื้นเทาเข้มตอนทดสอบใช้ 40 ได้ แต่ 55 ทำให้กางเกงดำเป็นรู เงาบนพื้นอาจติดมาด้วย

## Gemini API (generate.ps1)

สูตรพรอมต์และวิธีเลือกรูปอ้างอิงอยู่ใน `references/image-prompts.md` อ่านก่อนเขียนพรอมต์ทุกครั้ง พรอมต์แปลงตัวละครจากรูปของผู้ใช้ (คงหน้า ชุด เปลี่ยนท่า) อยู่ใน `references/character-prompts.md`

1. เขียนพรอมต์ภาษาอังกฤษลงไฟล์ `<ชื่อ>.prompt.txt` ในโฟลเดอร์งาน
2. รัน `scripts/generate.ps1 -PromptFile hero.prompt.txt -Out hero_raw.png -Ref <รูปตัวละคร> -Aspect 4:5`
3. เปิดดูทุกภาพที่ได้ ตรวจหน้า มือ นิ้ว และว่าไม่มีตัวหนังสือหรือโลโก้แปลกปลอม
4. ภาพเกือบใช่ให้แก้ต่อจากภาพนั้น โดยใส่เป็น `-Ref` ตัวแรกแล้วสั่งเฉพาะจุดที่ต้องเปลี่ยน อย่าเจนใหม่ทั้งภาพ
5. ตัดพื้นด้วย `cutout.ps1 -Chroma` แล้วนำไปใส่ใน `heroes` หรือ `props`

กติกาการเจน:

- **ให้ AI ทำแค่ภาพ.** ห้ามสั่งให้เจนหัวข้อ ตัวเลข การ์ด หรือโลโก้ ส่วนเหล่านี้ให้เรนเดอร์จากสเปกเท่านั้น
- **ไอคอนไอเทมที่มีในเกมต้องใช้ไฟล์จริง.** เจนเฉพาะของที่ไม่มีไฟล์ และต้องแจ้งผู้ใช้ว่าเป็นภาพเจน
- **ค่าใช้จ่าย.** แจ้งราคาโดยประมาณก่อนเจน ลองท่าด้วย `-Model fast` (ประมาณ $0.05 ต่อภาพ 2K) และทำภาพจริงด้วย `-Model pro` (ค่าเริ่มต้น ประมาณ $0.134 ต่อภาพ 2K) รอบหนึ่งไม่เกิน `-Count 2` ถ้าเจนภาพเดียวกันเกิน 3 รอบแล้วยังไม่ผ่าน ให้หยุดเอาผลให้ผู้ใช้ดูก่อน
- **API key.** ถ้าสคริปต์แจ้งว่าไม่มี `GEMINI_API_KEY` ให้ผู้ใช้สร้างคีย์ที่ `https://aistudio.google.com/apikey` เปิด billing (คีย์ Free Tier เจนภาพไม่ได้ ได้ error 429 "limit: 0" ทดสอบแล้ว) แล้วตั้งค่าเองด้วย `setx GEMINI_API_KEY "<คีย์>"` ห้ามขอให้วางคีย์ในแชต ห้ามเขียนคีย์ลงไฟล์ และห้ามพิมพ์ค่าออกมา
- **ถ้า API error หรือถูกบล็อก** ให้รายงานข้อความจริงจากสคริปต์ แล้วปรับพรอมต์ถ้าเป็นเรื่องเนื้อหา อย่าส่งซ้ำแบบเดิม

## Codex CLI (codex-gen.ps1)

Original heading: เจนตัวละครผ่าน Codex CLI (เมื่อผู้ใช้ขอเปลี่ยนท่า/ชุดทั้งตัว หน้าอาจเพี้ยน ถ้าแค่เปลี่ยนสีผม ของประดับ มุมกล้อง ใช้ Gemini ด้านล่างแทน)

Codex ในเครื่องผู้ใช้มีตัวเจนภาพในตัว ให้ภาพกรีนสกรีนสะอาด ไม่มีลายน้ำ และเก็บหน้าตัวละครของผู้ใช้ได้ถ้าส่งภาพใบหน้าใกล้ ๆ ไปด้วย ใช้สคริปต์ห่อไว้แล้ว ไม่ต้องเรียก `codex.exe` เอง:

```powershell
scripts\codex-gen.ps1 -Ref work\src\char.jpg,work\ai\face_char.jpg -Prompt $prompt -Out work\ai\gen_char.png
scripts\codex-gen.ps1 -Batch work\ai\jobs.json      # หลายตัวขนานกัน (templates\codex-jobs.example.json)
```

สคริปต์หา `codex.exe` เอง (อยู่ในส่วนเสริม VS Code ไม่ใช่ PATH) ส่งพรอมต์ทาง stdin (เพราะ `-i` กินอาร์กิวเมนต์ถัดไป) แยกโฟลเดอร์งานต่อ job ดึงภาพจาก `generated_images` ในล็อก และหยุดถ้าพรอมต์สั้นผิดปกติ (บั๊ก `+` ต่อ array ของ PowerShell) พรอมต์สำหรับตัวละครของผู้ใช้ดู `references/character-prompts.md` หัวข้อ Codex จากนั้น `cutout.ps1 -Chroma` และเปิดดูภาพจริงเทียบกับต้นฉบับ ถ้า Codex ปฏิเสธหรือถามกลับ สคริปต์รายงาน FAILED ห้ามหาทางเลี่ยง ใช้ตัวตัดจากภาพต้นฉบับแทน (`isolate.ps1` + `erase-white.ps1`)

## Antigravity CLI / Gemini (agy-gen.ps1, no API key)

ใช้ผ่านบัญชีของผู้ใช้ ใช้ได้จริงทั้ง **แก้ภาพต้นฉบับเฉพาะจุด** (เปลี่ยนสีผม ของประดับหัว มุมกล้อง ย้ายพื้นเป็นเขียว) และ **เจนพื้นหลังโปสเตอร์** ผ่านสคริปต์ห่อ:

```powershell
scripts\agy-gen.ps1 -Ref work\src\a.jpg -Prompt $prompt -Out work\ai2\a_edit.png
scripts\agy-gen.ps1 -Batch work\ai2\jobs.json -TimeoutSec 480      # หลายงานขนาน (templates\codex-jobs.example.json รูปแบบเดียวกัน)
```

- ต้องมี `--add-dir` ของโฟลเดอร์งานเพื่อให้ agy อ่านรูปอ้างอิงในโหมด headless (สคริปต์ทำให้: คัดลอก ref เข้าโฟลเดอร์ชั่วคราวต่องาน) ถ้าไม่มี agy จะตอบว่า "read_file permission auto-denied" และไม่เจนอะไร ห้ามแก้ด้วย `--dangerously-skip-permissions`
- agy ตอบก่อนภาพเสร็จและเซฟไฟล์ชื่อของมันเองใน `%USERPROFILE%\.gemini\antigravity-cli\brain\<id>\` สคริปต์เฝ้าโฟลเดอร์นั้นแล้วคัดลอกภาพใหม่ให้ งานขนานเคยจับคู่สลับ (ภาพ Newbie ไปอยู่ชื่อ Gang) สคริปต์จึงสั่งให้ตั้งชื่อไฟล์ขึ้นต้น `jobN_` ให้ **เปิดดูภาพทุกใบ** ว่าตรงงานก่อนใช้
- ผลลัพธ์ ~1024 px (แนวตั้ง 768x1376) ใช้ `upscale.ps1` ช่วยให้คมก่อนขึ้นโปสเตอร์ ถ้าขยายเกิน 1.6 เท่าจะนุ่ม
- พรอมต์ที่ผ่านการทดสอบอยู่ใน `references/character-prompts.md` หัวข้อ "Gemini: แก้เฉพาะจุด มุมกล้อง และพื้นหลังฟุ้ง"
- ใช้กับตัวละครผู้ใหญ่ชัดเจนเท่านั้น ดู "ตัวละครหน้าเด็ก" ถ้า agy ปฏิเสธ ห้ามหาทางเลี่ยง
