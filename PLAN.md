# JAKA Lumi loyihasi: ish rejasi

**Maqsad:** haqiqiy JAKA Lumi robotini MuJoCo'da simulyatsiya qilish, LLM + vision boshqaruvini shu yerda sinash, keyin xuddi shu kodni haqiqiy robotga ko'chirish. Qo'shimcha: robot oldiga odam kelsa, salomlashishi (qo'l silkitishi).

**Asosiy g'oya:** LLM faqat `LumiAPI` funksiyalarini chaqiradi. Simulyatsiyada ularni `LumiSim` bajaradi, haqiqiy robotda `LumiReal`. Backend almashadi, qolgan kod o'zgarmaydi.

```
LLM (vision) ──> LumiAPI ──┬─> LumiSim   (MuJoCo)
   ↑ kamera rasmi          └─> LumiReal  (jkrc SDK + HTTP + AGV TCP)
```

Har kuni shu fayldan navbatdagi belgilanmagan qadamni olaman. Tugagach `[x]` qo'yaman.

---

## 1-bosqich: Robot modeli (MJCF) ✅

- [x] Rasmiy URDF va mesh'larni yuklash (`lumi_description/`, JAKA_Lumi reposidan, Apache-2.0)
- [x] URDF'ni MuJoCo'da ochib tekshirish, robotning oldi qaysi tomon ekanini aniqlash (base_link ning −y tomoni)
- [x] `lumi.xml` ni yozish: erkin baza (`freejoint`), 2 g'ildirak, lift, bel, bosh, 6 bo'g'imli qo'l
- [x] 13 ta motor: g'ildiraklarga `velocity`, qolganiga `position`
- [x] Sodda collision (box, cylinder) va tayanch g'ildiraklar o'rniga ishqalanishsiz sharlar
- [x] Chegaralarni SDK hujjatiga moslash: lift 0–300 mm, bel ±140°
- [x] Robotiq 2F-85 gripperni qo'l uchiga ulash (`<attach>`)
- [x] `head_cam` va `torso_cam` kameralari
- [x] `scene.xml`: pol, stol, 2 kub, banka, suriladigan "odam" maneken

## 2-bosqich: Python API (`LumiSim`) ✅

- [x] `body_moveto` / `body_status`: haqiqiy HTTP API bilan bir xil birliklar (mm, gradus)
- [x] `arm_joint_move`, `arm_joints`, `tcp_position`
- [x] IK (`solve_ik`): bel + 6 bo'g'im, tasodifiy boshlanish nuqtalari, to'qnashuv tekshiruvi
- [x] `arm_move_to`, `arm_move_line` (to'g'ri chiziq bo'ylab)
- [x] `gripper`, `pick`, `place`
- [x] `drive` (differensial baza), `base_pose`
- [x] `get_image` (RGB va chuqurlik)
- [x] `wave` va `set_person`
- [x] `demo.py`: oynasiz sinov. Natija: kub 2 mm aniqlikda qo'yildi, baza 0.40 m / 89.2°, qo'l silkitish ishladi

## 3-bosqich: O'z ko'zim bilan tekshirish (keyingi qadam)

- [x] `mjpython demo.py --viewer` ni ishga tushirib, harakatlarni oynada ko'rish (2026-10-02, qo'l pozalaridagi muammo shu yerda topildi)
- [ ] `scene.xml` ni MuJoCo.app'ga tashlab, har bir motorni slayder bilan qimirlatib ko'rish
- [ ] `lumi.xml` ni o'qib chiqish: tushunmagan teglarni XML Reference'dan qarash (`attach`, `gravcomp`, `dampratio`)
- [ ] `ARM_HOME` va `ARM_WAVE` pozalari haqiqiy robotdagiga o'xshaydimi, solishtirish
- [x] Qo'l chegaraga yopishib, chalkash harakatlanardi: IK'ga 15° zaxira (`JOINT_MARGIN`) va eng yaqin yechimni tanlash qo'shildi, `ARM_HOME` va `ARM_WAVE` ushlash pozalari bilan bir "oila"dan tanlandi (harakatlar orasida bo'g'imlar ≤ 38° buriladi, oldin 133–166°)
- [x] Robotni rasmdagi haqiqiy robotga o'xshatish: qora kamera oynalari va linzalar, lift chizig'ida qizil halqa, qo'lda "JAKA" yozuvlari (`assets/`, `tools/make_decals.py`)
- [ ] Rasmdagi qolgan belgilar: bel ustidagi ikkinchi qizil halqa, yelka bo'g'imidagi yashil halqa (ixtiyoriy)
- [x] Odamni stol yoniga, qo'l tomoniga qo'yish va robotga qaratish, ko'z va burun qo'shish
- [ ] Loyihani tushunish uchun savol-javob: `scene.xml` tugadi, keyingisi `lumi.xml` (qo'llanmalar pastda)
- [ ] Qisqa demo video yozish (`media/demo.mp4` yoki GIF), README'ga qo'yish

## 4-bosqich: Ko'rish (vision), LLM'siz

- [ ] `vision.py`: bosh kamerasi rasmidan rangli buyumni topish (OpenCV, PiCar loyihasidagidek)
- [ ] Chuqurlik rasmi + piksel → robot koordinatasi (`pixel_to_robot`)
- [ ] Topilgan nuqtani `object_position` (haqiqiy qiymat) bilan solishtirib, xatoni o'lchash
- [ ] Odamni aniqlash: `detect_person()` (avval oddiy usul, keyin kerak bo'lsa tayyor detektor)
- [ ] "Odam ko'rindi → bosh unga buriladi → `wave()`" ssenariysi, LLM'siz

## 5-bosqich: LLM vision sikli

- [ ] Qaysi LLM ishlatilishini tanlash va API kalitni `.env` ga qo'yish (kalit hech qachon repoga tushmaydi)
- [ ] `tools.py`: `LumiAPI` funksiyalarini LLM uchun tool ta'riflariga aylantirish
- [ ] `agent.py`: rasm → LLM → tool chaqiruvi → natija → keyingi qadam sikli
- [ ] Xavfsizlik qatlami: har chaqiruvdan oldin chegara va yetish masofasini tekshirish, xato bo'lsa LLM'ga matn bilan qaytarish
- [ ] Vazifalar: "qizil kubni ko'k kubning yoniga qo'y", "bankani ko'tar", "odam kelsa salomlash"
- [ ] `evaluate.py`: tasodifiy joylashuvlarda N ta urinish, muvaffaqiyat foizi

## 6-bosqich: Simulyatsiyani haqiqatga yaqinlashtirish

- [ ] Haqiqiy robotdan o'lchash: bo'g'im tezliklari, lift tezligi, baza tezligi → `BODY_SPEED`, `ARM_SPEED`, `kp`
- [ ] MiniCobo qo'lining yuk ko'tarishini qo'llanmadan tekshirish (2F-85 ning o'zi ~0.9 kg)
- [ ] Haqiqiy robotga qaysi gripper qo'yilishini aniqlash; kerak bo'lsa modelni almashtirish
- [ ] Kameralar: haqiqiy Orbbec kameraning o'lchami va ko'rish burchagini modelga kiritish
- [ ] Kamera rasmiga shovqin va yorug'lik o'zgarishi qo'shib, LLM siklini qayta sinash
- [ ] Katta mesh'larni soddalashtirish (`link_4.STL` 9.6 MB)

## 7-bosqich: Haqiqiy robot (`LumiReal`)

- [ ] `lumi_real.py`: `LumiSim` bilan bir xil metodlar
  - [ ] tana: HTTP `/api/extaxis/enable`, `/moveto`, `/status`
  - [ ] qo'l: JAKA SDK (`jkrc`, 2.2.7 yoki yangiroq)
  - [ ] baza: AGV TCP buyruqlari (repodagi `JAKA_Lumi_Demo_Case/agv` namunalari)
  - [ ] kamera: Orbbec SDK
- [ ] Burchak ishoralarini bittalab tekshirish: har bo'g'imni +5° ga burib, simulyatsiya bilan solishtirish
- [ ] Hand-eye kalibrovka (repoda `handToEyeCalibration.py` bor)
- [ ] Birinchi sinovlar: past tezlik (`vel=10`), bo'sh joy, qo'l E-stop ustida
- [ ] Simda ishlagan vazifalarni bittalab haqiqiy robotda takrorlash

## 8-bosqich: Portfolio

- [ ] Sim va haqiqiy robot yonma-yon video
- [ ] README'ni natijalar (muvaffaqiyat foizi, video) bilan yangilash
- [ ] Notion'dagi "MuJoCo O'rganish Rejasi" sahifasiga shu loyihani qo'shish

---

## Kundalik

| Sana | Nima qilindi |
|---|---|
| 2026-09-30 | 1- va 2-bosqich tugadi: `lumi.xml`, `scene.xml`, `lumi_api.py`, `demo.py`. Oynasiz sinov o'tdi. Reja va README yozildi, GitHub'ga yuklandi. |
| 2026-10-01 | Robot ko'rinishi haqiqiyga yaqinlashtirildi: qora kameralar, lift chizig'i, "JAKA" yozuvlari. Kameralar oynalar markaziga siljitildi (bosh 1.3 sm, tutqich ~4 sm). Odam stol yoniga ko'chirildi va robotga qaratildi, qizil kub 4 × 6 × 4 sm, 60 g bo'ldi. Izohlar inglizchaga o'girildi. `demo.py` natijalari o'zgarmadi. Loyihani tushuntiruvchi ikki qo'llanma yozildi. Global agentlar o'rnatildi (`~/.claude/agents/`). |
| 2026-10-02 | Demo oynada birinchi marta ko'rildi. Qo'l bo'g'imlari chegaraga 0–2° yaqin kelayotgani topildi va tuzatildi: IK chegaradan 15° ichkarida ishlaydi va hozirgi pozaga eng yaqin yechimni tanlaydi, yangi `ARM_HOME` o'ng yondagi "tayyor" holat, stolga borish asosan bel burilishi bilan. Demo davomida eng kichik zaxira 28°, bir harakatdagi eng katta aylanish 38°, kub maqsaddan 3 mm uzoqda. |

## Qo'llanmalar

- Butun loyiha: https://claude.ai/artifact/2FQCeYgSrXRYYWwNWhCPmX
- `scene.xml` qatorma-qator: https://claude.ai/artifact/7QaR4iTLaGR7TVwWb5Lgdx

## Ochiq savollar

- Haqiqiy robotga qaysi gripper o'rnatiladi? (hozir simda Robotiq 2F-85)
- Qaysi LLM ishlatiladi?
- Haqiqiy robotning boshida va tutqichida aynan qaysi Orbbec kamera modeli turibdi?
