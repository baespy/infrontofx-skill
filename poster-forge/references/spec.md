# Spec reference

## ระดับบนสุด

| ฟิลด์ | ค่า |
| --- | --- |
| `size` | `16:9` 1920×1080, `1:1` 1920×1920, `6:5` 2592×2160, `2:1` 2000×1000, `3:2` 2048×1365, `4:5` 1536×1920, `9:16` 1080×1920, `cover` 2000×761 หรือ `[w,h]` |
| `layout` | `square-support` (สไตล์ A), `gun-support` (สไตล์ B) ตัวอื่น `hero-right` `hero-left` `hero-center` `pack-grid` `product` มีในเอนจินแต่ไม่ใช้กับงานของ skill นี้ |
| `theme` | `crimson`, `cobalt`, `violet`, `toxic`, `ember`, `rose`, `haunt`, `teal`, `pastel`, `ocean` |
| `accent`, `accent2` | สี hex แทนสีของธีม |
| `seed` | ตัวเลข เปลี่ยนรูปแบบเอฟเฟกต์แบบสุ่ม ถ้าไม่เปลี่ยนจะได้ภาพเดิม |
| `grain` | ความแรงเม็ดฟิล์ม ค่าเริ่มต้น `.22`, `0` คือปิด |
| `vignette` | ความมืดที่มุม ค่าเริ่มต้น `.55`, `0` คือปิด |
| `shade` | เงาหลังข้อความ `left`, `right`, `bottom`, `none` |

## `background`

| ฟิลด์ | ค่า |
| --- | --- |
| `image` | รูปพื้นหลัง ถ้าไม่ใส่จะสร้างจากธีม |
| `blur`, `brightness`, `tint` | ค่าปรับรูปพื้นหลัง `tint` คือความเข้มของสีธีม |
| `shape` | `diagonal`, `triangle`, `burst`, `none` |
| `ghost`, `ghostAlpha`, `ghostX`, `ghostY`, `ghostSize` | ตัวอักษรยักษ์จางเป็นพื้นหลัง (สไตล์ B ใช้ `W`) `ghostAlpha` 0.2 |
| `weave` | ลายผ้าทอละเอียด (ตารางสลับ) `true` หรือ 0-1 (0.32) |
| `swirl`, `swirlX`, `swirlY` | วงแหวนแสงซ้อนกันหลังตัวละคร ความแรง 0-1+ ตำแหน่งเป็นสัดส่วนภาพ (**ผู้ใช้สั่งเอาออก ตั้ง 0 หรือไม่ใส่ในงาน Support**) |
| `image` | path ภาพพื้นหลัง (เจนด้วย Gemini ให้ฟุ้ง) ใช้คู่ `shape "none"`, `tint 0`, `brightness` |
| `watermark`, `wmAlpha`, `wmSize`, `wmX`, `wmY`, `wmRotate` | รูปโลโก้ยักษ์จางเป็นพื้นหลัง (ขาวดำ โหมด screen) `wmAlpha` 0.07 |
| `texture` | ลายผ้าทอเฉียง `true` หรือความแรง 0-1 (0.32) |
| `lightX`, `lightY` | จุดกำเนิดแสง |
| `clouds` | ความแรงหมอกเมื่อไม่มีรูปพื้นหลัง ค่าเริ่มต้น `1` |
| `ground`, `groundY` | `true` เพื่อเพิ่มพื้นถนนมืดด้านล่าง |

## `fx`

`lightning`, `sparks`, `bokeh`, `bokehFront`, `arcs`, `streaks`, `spikes` เป็นจำนวน (`bokeh` จุดเบลอชั้นหลัง 3 ความลึก, `bokehFront` จุดเบลอใหญ่ชั้นหน้าอยู่ขอบภาพ, `arcs` เส้นพลังงานเรืองแสงชั้นหลัง ตั้งช่วงแนวตั้งด้วย `arcsY [บน,ล่าง]`), `focus` คือ `[x,y]` ที่เอฟเฟกต์พุ่งเข้าหา, `flare` คือ `[x,y,รัศมี]`

## `heroes` และ `props`

`heroes` เรียงจากหลังไปหน้า และรับค่าตำแหน่งเริ่มต้นจาก layout ส่วน `props` ต้องระบุตำแหน่งเอง ใช้กับของลอยหรือรถ เพิ่ม `"behind": true` เพื่อวางหลังตัวละคร

| ฟิลด์ | ความหมาย |
| --- | --- |
| `src` | รูป PNG โปร่งใส |
| `x`, `y` | ตำแหน่งกึ่งกลางแนวนอน และตำแหน่งขอบล่าง |
| `h` หรือ `w` | ความสูงหรือความกว้างเทียบกับภาพ |
| `flip`, `rotate` | กลับซ้ายขวา, หมุนเป็นองศา |
| `grade` | ย้อมสีธีม ค่าเริ่มต้น `.32`, `0` คือคงสีจริง |
| `rim` | แสงขอบ `false` หรือตัวเลขความแรง |
| `glow`, `glowSize` | แสงฟุ้งรอบตัว |
| `opacity`, `blur` | ใช้ทำเงาตัวละครใหญ่ด้านหลัง |
| `soften` | ความนุ่มของขอบตัด ค่าเริ่มต้น 1 `0` คือปิด |
| `bright`, `contrast`, `saturate` | ตัวคูณ CSS filter ของตัวละคร (เช่น `bright 1.1`) ใช้กับชุดขาวที่ดูหม่น |
| `fade` | `{"bottom":.3,"left":.2}` ไล่จางจากขอบ ใช้กับรูปที่ไม่ได้ตัดพื้นหลัง |

## `title`

| ฟิลด์ | ความหมาย |
| --- | --- |
| `style` | `stack`, `tone`, `racing`, `gold`, `neon`, `bubble` |
| `lines` | ข้อความ หรือ `{ "t": "...", "scale": 1, "color": "a" }` โดย `color` เป็น `a`, `a2` หรือ hex |
| `kicker`, `sub`, `note` | ข้อความเหนือหัวข้อ, คำรองคาบใต้หัวข้อ, บรรทัดข้อมูล |
| `script` | ลายเซ็นพาดทับ ใช้ตัวอักษรละตินเท่านั้น `scriptColor`, `scriptX`, `scriptY`, `scriptWidth` |
| `width` | ความกว้างเทียบกับคอลัมน์ ค่าเริ่มต้น `1` |
| `justify` | `false` เพื่อให้ทุกบรรทัดขนาดเท่ากัน |
| `textAlign` | จัดข้อความภายในบล็อก |
| `behindHero` | `true` วางคอลัมน์ข้อความไว้หลังตัวละคร เหมาะกับคำใหญ่ ต้องตรวจว่ายังอ่านออก |

## ส่วนอื่น

| ฟิลด์ | ค่า |
| --- | --- |
| `column` | `{x,w,top,bottom,justify,align}` ย้ายคอลัมน์ข้อความ |
| `badge`, `badgeSize` | แถบข้อความไล่จาง เช่น วันที่กิจกรรม |
| `items` | `{style,cols,gap,w,x,y,list:[{name,qty,img}]}` โดย `style` เป็น `stripe`, `chamfer`, `dark`, `glass`, `hex` |
| `panel` | `[x,y,w,h]` แผงโปร่งแสงหลังการ์ด (ค่าเริ่มต้นตาม layout `gun-support`) `false` ปิด |
| `items.opacity` | **0-1** การ์ดสไตล์ `tag` โปร่งแสงแบบกระจกฝ้า (ขอบเป็นเส้นบาง พื้นการ์ดโปร่งตามค่า) 0.5 = ครึ่งหนึ่ง ไม่ใส่ = ทึบ |
| `items.cardLogo` | path โลโก้ใช้เป็นพื้นหลังการ์ดสไตล์ `stripe` เห็นครึ่งเดียว แทนลายขีด |
| `logo` | `{src,w,corner}` โดย `corner` เป็น `tl`, `tr`, `bl`, `br` |
| `footer` | `{style,size,x,y,align,socials:[{type,text}]}` โดย `style` เป็น `chips`, `pill`, `slash` และ `type` เป็น `facebook`, `discord`, `tiktok` |

## ข้อความจากตัวเรนเดอร์

| ข้อความ | แก้อย่างไร |
| --- | --- |
| `image not found` | ตรวจ path เทียบกับไฟล์สเปก |
| `low-res subject` / `low-res item` | ขอรูปใหญ่กว่า หรือแจ้งผู้ใช้ว่าภาพจะนุ่ม |
| `column content is taller` | ลดการ์ด เปลี่ยน `cols` หรือขยาย `column` |
| `overflows the poster` | ลดขนาดหรือย้ายตำแหน่ง |
| `no hardware GPU` หรือ `did not confirm a hardware GPU` | การ์ดจอใช้ไม่ได้ ตรวจไดรเวอร์หรือการเชื่อมต่อแบบ remote ห้ามเปลี่ยนไปเรนเดอร์ด้วยซอฟต์แวร์ |



## ระดับสเปกบนสุดที่เพิ่ม (ไม่อยู่ในตารางด้านบน)

| คีย์ | ความหมาย |
| --- | --- |
| `bloom` | {blur, bright, saturate, alpha} แสงฟุ้งทั้งภาพ (สำเนาเบลอสว่างซ้อนแบบ screen) ใช้ `alpha` .2 ถ้าเกิน .25 หน้าไหม้ |
| `frontShade` | [บน,ล่าง] สัดส่วนจากขอบล่าง ทับค่า layout (square-support เดิม [.6,.34] ทำให้ตัวละครคล้ำ) `false` = ปิด |

