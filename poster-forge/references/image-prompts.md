# Image prompts

สูตรสำหรับ `scripts/generate.ps1` เขียนพรอมต์เป็นภาษาอังกฤษ และเติมส่วนใน `<...>` จากโจทย์

## หลักที่ทำให้ภาพไม่จืด

งานอ้างอิงมีพลังเพราะการจัดกล้องและแสง ไม่ได้มาจากคำว่า high quality ให้ระบุสิ่งเหล่านี้เสมอ

- **ระยะภาพ:** ครอประยะใกล้ ถึงอกหรือเอว อย่าเจนยืนเต็มตัวนิ่ง ๆ
- **ของพุ่งเข้ากล้อง:** มือหรือของที่ถือใหญ่มากด้านหน้า ใบหน้าคมอยู่ด้านหลัง ใช้คำว่า strong foreshortening กับเลนส์กว้าง
- **แสง:** แสงขอบแรงสีเดียวกับธีมจากด้านหลัง แสงหลักนุ่มที่หน้า เงาดำลึก
- **ผิวและผม:** semi-realistic game render, visible skin pores, fine hair strands ป้องกันหน้าเรียบแบบภาพ AI ทั่วไป

## รูปอ้างอิง

- ลำดับ `-Ref` คือ image 1, image 2 ตามที่อ้างในพรอมต์
- รูปตัวละครของเจ้าของงาน 1-3 มุม เป็นภาพแรก ๆ
- รูปอารมณ์ได้ไม่เกิน 1 รูป และต้องเขียนว่าใช้เฉพาะแสงและอารมณ์
- ห้ามป้อนภาพรวมหลายโปสเตอร์ในรูปเดียว สไตล์จะถูกเฉลี่ยจนจืด

## ท้ายพรอมต์ที่ต้องมี

ใช้ปิดท้ายภาพตัวละครและของประกอบทุกครั้ง เพื่อให้ตัดพื้นได้:

```text
Isolated on a perfectly flat solid #00FF00 background with no gradient and no floor shadow.
No green light on the subject. Keep the whole silhouette inside the frame except where cropped.
No text, no logo, no UI, no watermark.
```

ธีม `toxic` หรือของสีเขียว: อย่าใช้แสงขอบสีเขียวตอนเจน ให้สั่งแสงขอบสีขาว แล้วเติมสีด้วย `rim` และ `grade` ในสเปก `-Chroma` จะลดสีเขียวทั้งภาพ ถ้าตัวแบบมีสีเขียวจริงให้เปลี่ยนไปใช้พื้นสีเรียบอื่นและ `cutout.ps1` แบบปกติ

## สูตร

เติม `<ท้ายพรอมต์>` ด้วยบล็อกด้านบน

### 1. ยื่นมือหรืออาวุธเข้ากล้อง (Support, Gang)

`-Aspect 1:1 -Ref <ตัวละคร>,<รูปอารมณ์>`

```text
Use image 1 for the character's identity: same face, hair and outfit.
Use image 2 for lighting and mood only. Do not copy its character or layout.

Promotional key art for an online roleplay game. Close-up three-quarter view.
<ตัวละคร> leans toward the camera, thrusting <มือหรือของที่ถือ> forward in strong
foreshortening: it is huge in the foreground, the face sharp behind it.
Cropped at the chest. Low camera angle, 35mm wide lens.

Semi-realistic game render, visible skin pores, fine hair strands.
Hard saturated <สีธีม> rim light from behind, soft white key light on the face, deep crushed blacks.

<ท้ายพรอมต์>
```

### 2. หน้าใหญ่นิ่ง ๆ (Welfare จตุรัส)

`-Aspect 1:1 -Ref <ตัวละคร>`

```text
Use image 1 for the character's identity: same face, hair and outfit.

Extreme close portrait of <ตัวละคร>, head tilted slightly down, looking past the camera,
<อุปกรณ์ เช่น dark sunglasses>. Cropped at the shoulders, the head fills most of the frame.
85mm lens. Semi-realistic game render, visible skin pores, fine hair strands.
Strong <สีธีม> rim light on one side of the face and hair, the other side falling into shadow,
small lens flare at the edge of the jaw.

<ท้ายพรอมต์>
```

### 3. คู่หรือกลุ่ม (ไม่เกิน 3 คน)

`-Aspect 4:5 -Ref <คนที่1>,<คนที่2>`

```text
Use image 1 and image 2 for the identities of the two characters. Keep each face and outfit.

Dynamic promotional group shot for an online roleplay game. <คนที่1> in the foreground,
large, reaching toward the camera. <คนที่2> behind and higher, in a mid-air or seated pose.
Clear separation between the figures, no overlapping faces. Wide lens, low angle.
Semi-realistic game render. <สีธีม> rim light on both figures, deep shadows.

<ท้ายพรอมต์>
```

### 5. รถหรือของประกอบ

`-Aspect 16:9 -Ref <รูปรถหรือของ>`

```text
Use image 1 as the exact design of the object. Do not change its shape.

<วัตถุ>, dramatic low front three-quarter view, wide lens, glossy reflections,
hard <สีธีม> rim light outlining the silhouette, dark underside.

<ท้ายพรอมต์>
```

### 6. พื้นหลัง

`-Aspect 16:9` หรือ `1:1` ใส่ในสเปกที่ `background.image` ไม่ต้องตัดพื้น

```text
Atmospheric background plate for a game poster, no people and no vehicles.
<สถานที่ เช่น night city street, orchard, school hallway>. Strong depth of field blur,
<สีธีม> palette, one bright light source at <ตำแหน่ง>, darker on the side reserved for text.
No text, no logo, no UI, no watermark.
```

## แก้ต่อจากภาพเดิม

ใส่ภาพที่เกือบใช่เป็น `-Ref` ตัวแรก แล้วเขียนเฉพาะสิ่งที่เปลี่ยน:

```text
Keep the character, pose, framing and background exactly the same.
Only change: <สิ่งที่ต้องแก้ เช่น make the rim light stronger / fix the hand so it has five natural fingers>.
```

