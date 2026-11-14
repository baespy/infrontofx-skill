# Character prompts

พรอมต์แปลงรูปตัวละครของผู้ใช้ (สกรีนช็อตในเกม รูปการ์ตูน หรือ 3D ดิบ) ให้เป็นตัวละคร Semi-Realistic 3D ระดับ AAA เพื่อเอาไปทำโปสเตอร์ มี 2 ทางใช้

- **ผู้ใช้เจนเอง** ในเว็บ Gemini / ChatGPT / เครื่องมืออื่น ให้ส่งพรอมต์ภาษาไทยแบบ "บล็อกวางได้เลย" ด้านล่างให้เขาคัดลอก
- **Claude เจนให้** ผ่าน `scripts/generate.ps1` ใช้พรอมต์ภาษาอังกฤษ (เสถียรกว่า) ตามหัวข้อ "ฉบับอังกฤษ" และต่อด้วย `cutout.ps1 -Chroma`

ก่อนเขียนพรอมต์ ให้ได้ 4 อย่างนี้จากผู้ใช้ ถามเฉพาะที่ขาด

1. รูปตัวละคร (ภาพที่ 1)
2. รูปท่าทางอ้างอิง ถ้ามี (ภาพที่ 2) ถ้าไม่มีให้เลือกท่าจากตาราง
3. อารมณ์สีหน้า
4. ระยะภาพ (ค่าเริ่มต้น: เห็นถึงเอว)

## เหตุผลที่พรอมต์ต้องเป็นแบบนี้

- **ล็อกตัวตนก่อน ปรับสไตล์ทีหลัง.** ประโยคแรกต้องระบุว่าอะไรห้ามเปลี่ยน (ใบหน้า สีผิว ทรงผม สีผม เสื้อผ้า ลายและรายละเอียดตัวละคร) ไม่งั้นโมเดลจะ "ปรับปรุง" ชุดและหน้าจนไม่ใช่ตัวเดิม
- **ภาพท่าทางต้องถูกจำกัดบทบาท.** ถ้าส่งรูปท่าทางมาด้วย ต้องเขียนชัดว่า "ใช้เฉพาะท่าทางและมุมกล้อง" ถ้าไม่เขียน โมเดลจะดึงหน้า ชุด ของในมือ หรือตัวหนังสือของภาพนั้นมาด้วย
- **กันคำว่า realistic เกินจริง.** คำว่า "สมจริง" อย่างเดียวทำให้หน้าเปลี่ยนเป็นคนจริงอีกคน ต้องมีประโยคกำกับว่ายังเป็นตัวละคร 3D เดิมที่น่ารัก ไม่ใช่การ์ตูน ไม่ใช่พลาสติก
- **ท่าทางกับสีหน้าแยกบรรทัดกัน** เพื่อสลับต่อแผ่นได้โดยไม่ต้องเขียนใหม่ทั้งก้อน

## บล็อกวางได้เลย (ภาษาไทย)

เติมส่วน `<...>` ก่อนส่งให้ผู้ใช้ ส่วนที่ไม่ใช้ให้ลบทิ้ง ห้ามทิ้งวงเล็บเปล่า

```text
ใช้ภาพที่ 1 เป็นต้นแบบตัวละคร โดยคงเอกลักษณ์ใบหน้า สีผิว ทรงผม สีผม เสื้อผ้า และรายละเอียดของตัวละครทั้งหมดไว้เหมือนเดิม
<ถ้ามีภาพที่ 2: ใช้ภาพที่ 2 อ้างอิงเฉพาะ "ท่าทางและมุมกล้อง" เท่านั้น ห้ามนำใบหน้า เสื้อผ้า ของในมือ ตัวหนังสือ หรือโลโก้จากภาพที่ 2 มาใช้>

ปรับภาพให้เป็นสไตล์ Semi-Realistic 3D ระดับ AAA Game Character เน้นใบหน้าสมจริงแบบมนุษย์ ผิวเนียนละเอียดมีมิติ แสงและเงาธรรมชาติ ดวงตาสมจริง เส้นผมละเอียดเป็นเส้น แสงสะท้อนบนผิวอย่างนุ่มนวล ใช้แสงแบบภาพยนตร์ โทนสีละมุน องค์ประกอบภาพแบบถ่ายภาพจริง รายละเอียดคมชัดระดับ 4K แต่ยังคงความน่ารักและเอกลักษณ์ของตัวละคร 3D ไม่ให้ดูเหมือนภาพการ์ตูนหรือพลาสติก ฉากหลังสมจริง มีมิติและระยะชัดลึกอย่างเป็นธรรมชาติ

ท่าทาง: <ท่าทาง เช่น ยื่นมือเข้าหากล้อง / ถือมีดพุ่งเข้ากล้อง / ยืนกอดอก>
สีหน้า: <สีหน้า เช่น มั่นใจ ยิ้มมุมปาก>
ระยะภาพ: <เห็นถึงเอว / เห็นถึงอก / ครอปใบหน้าใหญ่> 4K
<ถ้าต้องการ: แสงขอบสี <สีธีม> จากด้านหลัง แสงหลักนุ่มที่ใบหน้า>
ไม่มีตัวหนังสือ ไม่มีโลโก้ ไม่มีลายน้ำ
```

ตัวอย่างที่เติมแล้ว (ตามที่ผู้ใช้ขอ)

```text
ท่าทาง: เปลี่ยนท่าทางให้เหมือนภาพที่ 2
สีหน้า: มั่นใจ ยิ้มมุมปาก
ระยะภาพ: เห็นถึงเอว 4K
```

## ท่าทางสำเร็จรูป

ผู้ใช้ไม่มีรูปท่าอ้างอิงให้เลือกจากตารางนี้ แล้วเติมลงบรรทัด "ท่าทาง" ในงานนี้ใช้เฉพาะท่าที่ตรงกับสองสไตล์ใน `support-styles.md` คือ "ยื่นมือหรือปืนเข้ากล้อง" และ "หน้าใหญ่นิ่ง" (เลขภาพ moodboard ในตารางไม่มีแล้ว ให้ดู `references/targets/` แทน)

| ใช้กับโปสเตอร์ | ท่าทาง (ไทย) | pose (English) | เลขภาพ |
| --- | --- | --- | --- |
| Support / Welfare / Gang | ยื่นมือข้างหนึ่งเข้าหากล้องใหญ่ ๆ ใบหน้าคมอยู่ด้านหลัง | one hand reaching toward the camera in strong foreshortening, face sharp behind it | 0, 7 |
| Gacha / Skin อาวุธ | ถืออาวุธชี้พุ่งเข้ากล้อง อีกมือกำแน่น | thrusting a weapon toward the camera, other fist clenched | 4, 6 |
| Ranking / ของรางวัล | เอียงตัวเข้ากล้อง ยกอาวุธขึ้นข้างลำตัว สายตามองกล้อง | leaning in, weapon raised beside the body, eyes on the camera | 6 |
| กิจกรรมทั่วไป ยิ้มต้อนรับ | ยืนเอียงไหล่เล็กน้อย ถือของประจำกิจกรรมไว้ที่อก | slight shoulder turn, holding the event prop at chest height | 2, 3 |
| ปกหน้าใหญ่ นิ่งเท่ | หันหน้ามองเฉียงผ่านกล้อง ก้มศีรษะเล็กน้อย | head tilted slightly down, looking past the camera | 10, 11 |
| ธีมน่ารัก / มาสคอต | กอดตุ๊กตาไว้ที่อก ยิ้มอ่อน เอียงคอ | hugging a plush at the chest, soft smile, head tilted | 8, 9 |
| แอ็กชันเต็มตัว (ใช้ระยะเต็มตัวแทนถึงเอว) | กระโดดกลางอากาศ แขนข้างหนึ่งเหยียดเข้ากล้อง | mid-air jump, one arm stretched to the camera | 7 |

## สีหน้า

| ไทย | English |
| --- | --- |
| มั่นใจ ยิ้มมุมปาก | confident smirk, one corner of the mouth raised |
| ยิ้มอ่อนโยน เป็นมิตร | warm gentle smile |
| เย็นชา นิ่ง | calm cold stare, lips closed |
| ดุ ท้าทาย | fierce challenging look, brows lowered |
| ตื่นเต้น ยิ้มกว้าง | excited wide smile showing teeth |

## ตัวแปรตามชนิดโปสเตอร์

ค่าที่ควรเปลี่ยนเมื่อทำเป็นชุด คงบล็อกตัวตนและบล็อกสไตล์ไว้เหมือนเดิมทุกแผ่น จะได้ตัวละครหน้าเดิมทั้งชุด

| ชนิด | ระยะภาพ | แสงขอบ | หมายเหตุ |
| --- | --- | --- | --- |
| Support Family / Gang | ถึงเอว | แดงเข้ม crimson | เว้นพื้นที่ด้านข้างให้การ์ดไอเทม ตัวละครอยู่ชิดขอบ |
| Welfare จตุรัส | ถึงอก ใบหน้าใหญ่ | น้ำเงิน cobalt | หน้าต้องคม ห้ามมีของบังหน้า |
| Gacha | ถึงเอว | ม่วง violet หรือเขียว toxic | ถ้าเขียว ใช้แสงขอบขาวตอนเจน ดูหัวข้อกรีนสกรีน |
| Ranking | ถึงเอว | ส้มทอง ember | ของรางวัลอยู่คนละภาพ ไม่เจนรวม |
| น่ารัก / เทศกาล | ถึงเอว | พาสเทล แสงนุ่ม | เปลี่ยน "โทนสีละมุน" เป็นสีของธีมเฉพาะ |

## ฉบับอังกฤษ (สำหรับ `generate.ps1`)

`-Ref <ตัวละคร>[,<รูปท่า>] -Aspect 4:5 -Size 4K` ภาพที่ 1 ต้องเป็นรูปตัวละคร ภาพที่ 2 (ถ้ามี) เป็นรูปท่าทาง ลำดับ `-Ref` กำหนดเลขภาพ

```text
Use image 1 as the character reference. Keep the exact face identity, skin tone, hairstyle, hair color, outfit and every character detail unchanged.
<If image 2 is given: Use image 2 for pose and camera angle ONLY. Do not copy its face, clothes, held objects, text or logos.>

Convert to a semi-realistic 3D AAA game character render. Human-realistic face, smooth detailed skin with depth and visible pores, natural light and shadow, realistic eyes, fine individual hair strands, soft specular highlights on the skin, cinematic lighting, soft muted color palette, photographic composition, 4K sharp detail. Keep the cute charm and identity of the 3D character: it must not look like a cartoon or plastic.

Pose: <pose>. Expression: <expression>. Framing: <waist-up / chest-up>.
<Optional: <theme color> rim light from behind, soft white key light on the face.>

Isolated on a perfectly flat solid #00FF00 background with no gradient and no floor shadow.
No green light on the subject. Keep the whole silhouette inside the frame except where cropped.
No text, no logo, no UI, no watermark.
```

ถ้าผู้ใช้ต้องการฉากหลังสมจริงในภาพเดียวกัน (ตามพรอมต์เดิม) ให้ตัดสามบรรทัดกรีนสกรีนออก แล้วเติม `Realistic background with natural depth of field, <สถานที่>.` แต่ภาพที่ได้จะตัดพื้นสำหรับประกอบโปสเตอร์ไม่ได้ ใช้เป็นภาพเต็มหรือพื้นหลังได้เท่านั้น

## ตรวจผลทุกครั้ง

- หน้าตรงตัวเดิมไหม ตา คิ้ว ทรงผม สีผม จุด ไฝ ตำหนิตรงกับต้นฉบับ
- เสื้อผ้า ลวดลาย อุปกรณ์ ตรงต้นฉบับ ไม่ถูกเติมหรือตัดทิ้ง
- ท่าทางตรงกับภาพอ้างอิง แต่ไม่มีหน้าหรือของของภาพอ้างอิงติดมา
- มือมีห้านิ้ว ไม่บิด ผิวไม่เป็นพลาสติกเรียบ ตาไม่ตาย
- ไม่มีตัวหนังสือ โลโก้ ลายน้ำแปลกปลอม

แก้เฉพาะจุดด้วย "แก้ต่อจากภาพเดิม" ใน `image-prompts.md` อย่าเจนใหม่ทั้งภาพ

## ตัวละครหน้าเด็ก (ทดสอบแล้ว Gemini เว็บปฏิเสธ)

ตัวละครสาวหน้าเด็ก (ใบหน้ากลม ตาโต สัดส่วนเด็ก) ที่ถูกสั่งให้เป็น "ใบหน้าสมจริงแบบมนุษย์ ผิวมีรูขุมขน" ถูก Gemini เว็บปฏิเสธว่า "สร้างรูปภาพที่ไม่ปลอดภัยไม่ได้" ห้ามเขียนพรอมต์เลี่ยงตัวกรอง (เช่น อ้างว่าเป็นผู้ใหญ่) ให้ทำดังนี้แทน

- ตัวละครที่ต้นฉบับเป็น 3D เรนเดอร์คุณภาพสูงอยู่แล้ว ข้ามขั้นแปลงสไตล์ ตัดพื้นต้นฉบับใช้ตรง ๆ (ขอ PNG โปร่งใส)
- ใช้พรอมต์แปลงสไตล์ "สมจริงแบบมนุษย์" เฉพาะตัวละครที่เป็นผู้ใหญ่ชัดเจน
- ก่อนเขียนพรอมต์ ให้ดูรูปจริงว่าเป็นตัวไหน อย่าเดาจากชื่อไฟล์

## ข้อควรแจ้งผู้ใช้

- ผลลัพธ์ขึ้นกับโมเดลที่ใช้ ใบหน้ามักเพี้ยนเมื่อต้นฉบับเป็นการ์ตูนแบนมาก ให้ใส่รูปตัวละครหลายมุม (หน้าตรง ข้าง) เป็นภาพที่ 1-2 จะช่วยให้หน้าตรง
- รูปท่าทางอ้างอิงที่มาจากโปสเตอร์ของเซิร์ฟเวอร์อื่นใช้ได้เฉพาะท่าทาง ตัวละคร ของ และโลโก้ในนั้นห้ามติดมา
- เจนบนเว็บของผู้ใช้เองเสียโควต้าของเขา เจนผ่าน `generate.ps1` เสียเงิน API แจ้งราคาก่อนเสมอ

## Codex: ตัวละครของผู้ใช้ เปลี่ยนแค่ท่ากับชุด (รักษาหน้าเดิม)

ใช้เมื่อผู้ใช้ให้ภาพตัวละครของตัวเองและสั่ง "เจนท่าทางและชุดใหม่แค่นั้น" (ทดสอบกับตัว 3D พื้นขาว 3 ตัว ได้หน้า ทรงผม แว่น สีปาก สีหน้าตรงต้นฉบับ)

1. ครอป **ภาพใบหน้าใกล้ ๆ** ของตัวละครเก็บเป็นรูปที่สอง (`face_x.jpg`) แล้วส่งสองรูปให้ Codex: รูป 1 ภาพเต็ม รูป 2 ใบหน้า ถ้าส่งภาพเดียวหน้าจะเพี้ยนเป็นหน้าสวยทั่วไป
2. พรอมต์ภาษาอังกฤษ ประกอบเป็นสตริงเดียวก่อนส่ง (ห้ามใช้ `@('a','b',$base+'x')`):
   - "Image 1 is one of my roleplay characters ... image 2 is a close-up of the same face. This is an EDIT of image 1, not a new design."
   - "copy the face exactly as in image 2: eye shape and size, eyebrows, nose, lips and lip colour, blush, skin tone, facial expression, glasses; same hair colour, length, hairstyle, accessories; same 3D render art style"
   - "Change ONLY the pose of the body and the outfit as described." + ชุด (ลวดลายเจาะจง) + ท่า (แขนข้างไหนทำอะไร ลำตัวหมุน 30 องศา ห้ามยืนแขนตก)
   - ถ้าต้องมองกล้อง: "head turned to look straight at the camera, face brightly lit by a soft front key light" (ถ้าไม่ระบุ Codex จะทำหน้าก้มตามต้นฉบับ แล้วหน้าจมเงา)
   - ภาพคู่: "the man in image 1 only, remove the woman completely"
   - "No watermark, signature, logo, floating stickers, doodles, text or extra objects. Waist-up, head fully inside the frame with space above, five fingers per hand. Background perfectly flat pure green #00FF00, no shadows. Square 1:1." + "Add a subtle <สีธีม> rim light"
3. ลิขสิทธิ์: ถ้าตัวละครมีของลิขสิทธิ์ (Hello Kitty) สั่งไม่ให้วาดหน้า/สติกเกอร์ แล้วแจ้งผู้ใช้ว่าโบแดงทรงนั้นยังเป็นเอกลักษณ์ของตัวการ์ตูน
4. รัน: `scripts/codex-gen.ps1 -Ref full.jpg,face.jpg -Prompt $p -Out gen.png` หรือ `-Batch jobs.json` (ขนานกัน ดู `templates/codex-jobs.example.json`) แล้ว `cutout.ps1 -Chroma` (เอา `-Erode 1` เป็นค่าเริ่มต้นอยู่แล้ว)
5. ตรวจเทียบกับต้นฉบับทุกตัวเคียงกัน ถ้าหน้าเพี้ยนให้เจนซ้ำพร้อมเน้นจุดที่เพี้ยน สีหน้าต้นฉบับ (เช่นอ้าปากตกใจ) ห้ามเขียน "friendly/smile" เพราะจะเปลี่ยนสีหน้า

## Gemini: แก้เฉพาะจุด มุมกล้อง และพื้นหลังฟุ้ง (`agy-gen.ps1`)

ทดสอบกับตัวละคร 3D พื้นขาวของผู้ใช้ 3 ตัว: ได้หน้า สีหน้า แว่น ท่ามือ ชุด เหมือนต้นฉบับ เปลี่ยนเฉพาะที่สั่ง ดีกว่าให้ Codex วาดใหม่ทั้งตัว (หน้าเพี้ยนจนผู้ใช้ว่า "แปลกไปเลย") หลักการเขียน:
- ขึ้นต้น "Edit the reference picture. Keep this exact same character: identical face, identical <expression>, identical <glasses>, identical <outfit>, identical camera framing and 3D game-avatar render style and lighting." แล้ว **"Change ONLY these things:"** ตามด้วยข้อ (1) (2) (3) ที่ต้องการ
- สีผมระบุเฉดชัด ("soft pastel lavender-pink with a subtle lighter gradient at the tips", "icy silver-blue with a gradient towards deeper blue at the ends", "bright silver-white" / "deep crimson burgundy red") และบอก "same hair shape and strands"
- ของประดับหัวบอกของเดิม + ของใหม่ ("the big teddy bear on top of her head is replaced by a small white satin ribbon bow") ของลิขสิทธิ์ (โบทรงแมว) เปลี่ยนเป็นของทั่วไป (กิ๊บผีเสื้อ กิ๊บดาว)
- ลบสติกเกอร์ ลายน้ำ โลโก้สตูดิโอ และลายการ์ตูนบนชุดในประโยคเดียวกัน
- ปิดท้าย: "Replace the whole white background with one flat solid chroma-key green (#00FF00), no gradient and no shadow on the background. Do not add any other object. Same composition as the reference."
- ส่ง `-Ref` ภาพต้นฉบับ ภาพคู่ระบุทั้งสองคนว่าเปลี่ยนอะไรของใคร

**เปลี่ยนมุมกล้อง / ให้เห็นชุดครบ** (ผู้ใช้บ่นว่า "เสื้อตัวละครขาด"): ส่งสอง ref (1 = ภาพที่แก้สีผมแล้ว, 2 = ต้นฉบับเพื่อดูชุด) แล้วสั่ง "Change ONLY the camera framing: pull the camera back and show her from the top of her head down to her thighs (knees for a long dress, hips for a couple), standing, a slight three-quarter turn, with the complete outfit visible and not cropped... She occupies the centre about 55 percent of the width with green margin on both sides. Portrait 3:4 image." ส่วนของชุดที่ต้นฉบับไม่เห็น (กระโปรง) ให้ระบุเองให้เข้าชุดเดิม (เช่น กระโปรงลายสก็อตสีเดียวกับเนกไท) และแจ้งผู้ใช้ว่าเป็นส่วนที่ AI เติม

**พื้นหลังฟุ้งต่อระดับ** (ใส่ `-Ref` โปสเตอร์ในโฟลเดอร์ posterphoto สีใกล้เคียง 1 รูปเป็นอารมณ์แสงเท่านั้น):
"Create a cinematic abstract POSTER BACKGROUND only, square 1:1, in the lighting and colour mood of the reference poster but with NO characters, NO people, NO text, NO logos, NO icons, NO UI frames, NO objects, NO cars. Dreamy, hazy, airy and very colourful across the WHOLE frame: soft volumetric fog and haze layers, a large glowing light bloom in the upper-left, soft light rays, floating glowing dust and ember particles, many big and small out-of-focus bokeh discs at different depths, a few thin glowing light streaks, subtle film grain. IMPORTANT: the lower third of the image must stay just as rich in colour and light as the top: no black band, no dark strip, no empty black ground at the bottom, no hard dark vignette; the darkest areas must still be a deep saturated tone of the theme colour, never black. Keep the right-centre area a little calmer so a title can sit there. Do not draw rings, circles or concentric waves. Colour theme: <vivid crimson red with warm orange-gold highlights and deep wine-red shadows | vivid violet purple with magenta-pink highlights and deep indigo shadows | vivid cobalt blue with cyan highlights and deep navy-blue shadows>."
รอบแรกที่เขียนว่า "lower 35 percent darker and calmer" ได้พื้นที่มืดด้านล่าง ผู้ใช้ติว่าเป็นแถบสีดำ ห้ามเขียนแบบนั้น


**แนวรูปตัวอย่าง "X-slab" (รอบหลังสุด)** พรอมต์พื้นหลัง (ส่ง `-Ref` โปสเตอร์ตัวอย่างสีใกล้เคียง 1 รูป และสั่งให้ไม่วาดคน/ตัวหนังสือ/การ์ดในนั้น):
"Create a cinematic poster BACKGROUND only, square 1:1, copying the mood, composition and texture of the reference poster but ignoring the person, the title text and the item cards in it (do not draw any of them). Very dark, moody, single-colour toned image: two large diagonal torn-paper slabs crossing behind the centre to form a big X shape, rough torn edges, a fine halftone and woven dot texture on the slabs, a soft hard-edged spotlight beam falling diagonally from the upper-left, a small bright anamorphic lens flare to the right of centre, heavy fine film grain, dark vignette in the corners, subtle dust. NO people, NO faces, NO text, NO logos, NO cards, NO objects. The whole frame is toned in ONE colour family, deep and rich, and even the darkest areas keep a hint of that colour (never pure black). Colour theme: <deep crimson red with hot pink-red glow on the slabs | deep violet purple with magenta glow on the slabs | deep cobalt navy blue with electric blue glow on the slabs>." (ได้ผลทั้งสามสีในรอบแรก)
พรอมต์ตัวละครระยะ medium close-up: "The reference image is the character to keep EXACTLY: <ลิสต์ของที่ต้องคงรวมสีผมใหม่ และใส่ตัวพิมพ์ใหญ่ว่าสีผมต้องคงสีใหม่ ไม่ใช่สีเดิม> Change ONLY the camera framing: a medium close-up portrait from the top of <accessory> down to the waist, the head (from the top of the hair to the chin) occupying about 45 percent of the image height and centred, the shoulders and clothes filling the rest of the frame down to the bottom edge with no gap at the bottom. Do not crop the top of the hair or the accessory. Flat solid chroma-key green background (#00FF00)... Square 1:1 image."
**บทเรียน:** ส่งภาพต้นฉบับเป็น ref ที่สองทำให้ Gemini ย้อนสีผมกลับเป็นสีเดิม (ผมม่วงกลายเป็นน้ำตาล) ให้ส่งเฉพาะภาพที่แก้สีผมแล้วเป็น ref เดียว และเน้นสีผมด้วยตัวพิมพ์ใหญ่ในพรอมต์


**พื้นหลังห้องสตรีมภาพกว้าง 2:1 (Streamer, ไม่ต้องใช้ ref)** ผู้ใช้สั่ง "เปลี่ยนพื้นหลังบ้าง" จาก X-slab: "Create a cinematic wide poster BACKGROUND only: a 2:1 ultra-wide panoramic landscape image, twice as wide as it is tall. A dreamy out-of-focus game-streaming room at night, seen as pure atmosphere: rose magenta-pink and soft violet neon LED light strips running along the walls and shelves, a big glowing circular ring-light and monitor glow far in the distance, all completely blurred, many big and small round bokeh discs ..., soft volumetric haze and light rays, a gentle anamorphic lens flare, fine film grain and a soft dark vignette. Everything is heavily blurred, abstract and atmospheric, with no sharp objects. The left-centre area is a calm soft glow where a character will stand, and the right side is slightly darker and calmer so a title can sit there. NO people, NO faces, NO text, NO letters, NO logos, NO signs with writing, NO UI, NO screens showing pictures, NO cards. The whole frame is toned in ONE rose magenta-pink colour family, rich and saturated; even the darkest areas keep a deep plum tone, never pure black, and there is no black band at the bottom." (ได้ผลในรอบแรก ผลลัพธ์ 1376×768) ระวังวงแหวนไฟสว่างอยู่ราว x .6 ของภาพ: วางหัวข้อใต้วงแหวน ไม่ใช่ทับ

**พื้นหลังตกแต่งเยอะตามธีมอาชีพ (ไม่ใช้ ref; ได้ผลรอบแรกทั้ง 2:1 และ 1:1)** "Create a dreamy, hazy, richly decorated POSTER BACKGROUND only: a 2:1 ultra-wide panoramic landscape image [หรือ square 1:1]. Theme: live streaming and gaming content creator culture. Soft glowing rose-pink fog and volumetric haze over the whole frame, big out-of-focus bokeh discs, light rays and sparkles, and MANY floating semi-transparent glowing streamer-themed objects and icons at different depths, some sharp and some blurred: a pink LIVE record badge with a red dot (the word LIVE is the only text allowed), chat bubbles filled with hearts and emoji faces (no readable words), heart and thumbs-up reaction icons, a play-button triangle, a gaming headset, a studio microphone, a webcam, a game controller, a subscribe bell, a neon ring light, pixel hearts and pixel stars, blank glowing floating UI windows, rising like-count bars, confetti and glitter. Keep the left-centre 40 percent calm, soft and uncluttered because a character will stand there, keep the middle of the right half fairly calm for a title, and put the dense decoration around the edges, the top and the bottom corners. Heavy visible fine film grain, soft bloom glow, dreamy haze. NO people, NO faces, NO real brand logos (no Twitch, no YouTube, no Discord), no other text. The whole frame is toned in ONE rose magenta-pink colour family with soft violet accents; even the darkest areas keep a deep plum tone, never pure black, and there is no black band anywhere." เปลี่ยนรายการไอคอนตามธีม (แก๊ง = ปืน/เหรียญ ฯลฯ) ห้ามโลโก้แบรนด์จริง ไอคอนแถวล่างของภาพกว้างมักถูกตัวละครบัง ให้เลื่อนตัวละครไปข้างที่ไอคอนน้อย

**ตัวละครแต่งตัว/ทรงผม/ของที่ถือใหม่ (Streamer)** ส่ง `strm_edit.png` (ภาพที่แก้แล้ว) เป็น ref เดียว: "Keep this exact same character: identical face, expression, glasses, blunt bangs, star clip, pose ... The hair colour stays BLACK. Change ONLY: (1) the hairstyle: the two low pigtails are replaced by long straight BLACK hair worn half-up in a neat high bun ...; (2) the polka-dot shirt is replaced by an oversized black zip-up hoodie with soft pink drawstrings over a plain white t-shirt, no logos/text/patterns; (3) the plate with the tomato and the fork are removed and in the hand that held the plate she holds a pastel pink wireless gaming controller at chest height (generic design, no brand marks)." ได้ผลรอบแรก (หน้า แว่น กิ๊บดาวคงเดิม ท่าทางเปลี่ยนเป็นถือจอยสองมือ) ตัวละครแคบกว่าเดิม ไม่มีช่องปิดล้อมให้ fill-holes

**ตัวละครจากครีเอเตอร์อื่น (Streamer)** รูปต้นฉบับมีโลโก้ครีเอเตอร์ล่างภาพ ลายน้ำจางทั้งภาพ และกิ๊บ/ปักทรง Hello Kitty: พรอมต์ขั้น (ก) สั่งทั้งสามข้อในประโยคเดียว ("the white cartoon-cat hair clip ... is replaced by a small plain silver star hair clip; remove the cartoon cat embroidery on the shirt; remove every watermark, faint ghost text, signature and small round logo anywhere in the picture, including the faint lettering over her face and shirt and the small logo at the bottom centre") ได้ผลในรอบแรก ผมดำยังดำอยู่ ต้องแจ้งผู้ใช้ทุกครั้งว่าลายน้ำ/ของลิขสิทธิ์ถูกลบ

**เปลี่ยนเสื้อผ้า (ทดสอบแล้ว ได้หน้า/ผม/ท่าเดิมครบ)** ส่งภาพ medium close-up เป็น ref เดียว: "The reference image is the character to keep EXACTLY: <หน้า สีหน้า แว่น สีผมเป็นตัวพิมพ์ใหญ่ ของประดับ ท่า มุมกล้อง สไตล์เรนเดอร์>. Change ONLY the clothes: replace <ชุดเดิม> with <ชุดใหม่>. No logos, no text and no patterns on the clothes. Flat solid chroma-key green background (#00FF00)... Square 1:1 image." เช่น "the white school shirt and the red plaid tie → an oversized soft lilac knit cardigan worn open over a plain white t-shirt, and a thin black choker necklace", "the white polka-dot dress and the white tote bag → a light-blue denim jacket worn open over a plain white fitted t-shirt, and a small silver pendant necklace, no bag", ภาพคู่ระบุทีละคน (ผู้ชาย: black leather biker jacket with silver zippers over a white t-shirt, keeps his thin silver chain; ผู้หญิง: black cropped varsity jacket with thin red sleeve stripes over a black top) ห้ามลายดาว/ตัวหนังสือ/โลโก้ เพื่อไม่ให้ติดลิขสิทธิ์หรือแบรนด์
