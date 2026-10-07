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

## 7a-bosqich: Haqiqiy robotda salomlashuvchi va ovozli yordamchi (2026-10-07 dan)

Kod: `real/thor/` (Mac'da), ishlaydigan nusxasi Thor'da `~/Dev/lumi-wave` (venv `.venv`). Qo'l, tana va AGV'ni Mac'dan sinash uchun skriptlar `tools/` da.

**Ulanish va tekshiruv**
- [x] Mac robot Wi-Fi'siga ulandi: `Lumi10000013-5G`, qo'lda IP 192.168.10.200/24, router bo'sh (DHCP 10.5.5.x beradi, u ishlamaydi). Internet bir vaqtda LAN kabel orqali.
- [x] Hamma qurilma javob berdi: controller .90, AGV .10, router .79, **Thor .240** (SSH user `cutshion`)
- [x] `tools/robot_check.py`: faqat o'qiydigan tekshiruv (portlar, tana holati, AGV holati, batareya, xarita); hisobotlar `docs/private/` da
- [x] Qo'l controller versiyasi: **3.3.8_beta_lumi_minicab** (Cobo π lumi 3.3.6), demak SDK'da `login(1)`
- [x] Port 10000 SDK'siz JSON ko'rinishida qo'l holatini uzatadi (macOS'dan ham ishlaydi)

**AGV (baza)**
- [x] Panel (:9001) va `tools/agv_teleop.py` (klaviatura bilan haydash), `tools/agv_route.py` (markerlar ro'yxati, markerga borish). Tezlik 0.3 / 0.5 m/s.
- [x] Robot eski xarita (`cutshion_708_0707`) qamramaydigan xonada edi, shuning uchun navigatsiya va dock ishlamadi. **Yangi xarita `cutshion_708_B_block` qurildi**.
- [x] Markerlar: `home_dock` (type 11, dock, kodda `home`) (−1.244, 0.054), `aisle_a`, `aisle_b`

**Qo'l**
- [x] Cobo π'da `hand_shaking.jks` (qo'l silkitish) dasturini o'zim yozdim
- [x] `tools/arm_program.py run hand_shaking`: TCP 10001 orqali SDK'siz ishga tushadi (ishladi)

**Thor'dagi dasturlar (`real/thor/`)**
- [x] Thor sozlandi: internet juda sekin edi, hamma paketlar Mac'da yuklab olinib `scp` bilan ko'chirildi (offline o'rnatish). Orbbec udev qoidasi qo'shildi.
- [x] `camera_test.py`: kamera 0 (SN CPA9B520037, USB 3) ishlaydi. Kamera 1 (CPA9B52007A) USB 2 uzaytirgichda bo'lgani uchun uzilib qoladi.
- [x] `person.py`: YOLOv8n (ONNX, OpenCV DNN), ~14 fps, chuqurlik bilan masofa va burchak
- [x] `speak.py`, `head.py` (bosh yaw ±60°, sekin), `arm.py` (hand_shaking.jks)
- [x] `greeter.py`: odam 0.5–1.2 m da tursa, bosh unga buriladi, qo'l silkitadi va "Hello, I am Lumi Robot Assistant. How can I help you?" deydi (tasdiqlandi)
- [x] `knowledge.py`: bilim bazasi (RAG), bge-m3 (llama-server :8095), 32 bo'lak (`knowledge/lumi_about_en.md` + JAKA'ning 13 ta xitoycha matni)
- [x] `brain.py`: Ollama `gemma4:e4b`, ~2.5 s, faqat EN/KO javob beradi, bilmasa "aniq bilmayman" deydi. JSON harakat: go_to / look / wave / stop / end / none
- [x] `ears.py`: AIUI mikrofon → ovoz detektori → whisper.cpp (CUDA, large-v3-turbo, :8096), ~0.45 s
- [x] `mouth.py`: Supertonic-3 TTS, EN/KO, ovoz F1
- [x] `agv.py`: holat, markerlar, markerga borish, bekor qilish
- [x] `lumi.py` v2: odamlarni kuzatish (har kimga ID), har yangi odam bir marta salomlashadi, 12 s indamasa o'zi so'raydi (ko'pi bilan 2 marta), odam ketsa gap to'xtaydi, qaytib kelsa yana salomlashadi. Qo'l kamerani to'sib qolishi tuzatildi (tasdiqlandi).
- [x] Patrol rejimi: `lumi.py --patrol aisle_a,aisle_b` markerlar orasida aylanadi va oldida turgan odam uchun to'xtaydi. Batareya **5 %** dan pastga tushsa dockka qaytadi (oldin 20 % edi), 60 % da yana chiqadi.
- [ ] Patrolni oxirigacha sinash (birinchi urinishda batareya 13 % edi va 20 % chegarasi sabab robot uyga ketdi; chegara 5 % ga tushirildi)
- [ ] `HEAD_SIGN` va `LOOK` ishoralarini tekshirish (+yaw robotning chapimi, +pitch pastmi): `python head.py 10`, `python head.py 0 10`
- [ ] Haqiqiy mehmon bilan to'liq suhbat sinovi
- [ ] Kamera 1 uchun USB 3 kabel
- [ ] Boshqaruv sahifasi (Thor :8099, Start / Stop / batareya / log) yoki systemd bilan avtomatik ishga tushirish (qaysi biri ekani hal qilinmagan)

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
| 2026-10-04 | Haqiqiy robotga o'tishga tayyorgarlik: rasmiy JAKA_Lumi repo (barcha branch'lar), jaka-robot-demos, JAKA SDK 2.2.7, Python SDK qo'llanmasi, JAKA App, Mini 2, AGV qo'llanmalari va kompaniya Notion ma'lumotlari o'qildi. `docs/` papkasida mavzular bo'yicha 13 ta inglizcha hujjat yozildi (`docs/00_START_HERE.md` dan boshlanadi). Parollar va ichki ma'lumotlar `docs/private/` da (git'ga kirmaydi). Topildi: qo'l IP 192.168.10.90, qo'l MiniCobo2 = Mini 2, URDF va SDK bo'g'im burchaklari bir xil (vendor ROS kodi va haqiqiy poza bilan tekshirildi). |
| 2026-10-05 | Notion'dagi qo'shimcha ma'lumotlar (AGV API sahifasi, haqiqiy javoblar, markerlar) va AGV API PDF to'liq kiritildi. `docs/13_TO_VERIFY_ON_ROBOT.md` (robotda aniqlanadigan 11 ta narsa va usullari) yozildi. Haqiqiy robot hujjatlaridan sim qiymatlari olib tashlandi. Kompaniya ichki qismlari `docs/private/` ga ko'chirildi (git'ga kirmaydi, repo public qoladi). Keyingi qadam: robotga ulanish (Lumi Wi-Fi), 13-hujjat bo'yicha tekshiruvlar, keyin `real/` kutubxonasi (agv.py, body.py, arm.py). |
| 2026-10-07 | **Haqiqiy robotda birinchi kun.** Robot Wi-Fi'siga ulandim, hamma qurilma topildi (Thor 192.168.10.240), controller versiyasi 3.3.8 → `login(1)`. AGV panel va skript bilan yurdi. Yangi xarita `cutshion_708_B_block` qurildi, markerlar `home_dock`, `aisle_a`, `aisle_b` qo'yildi. Cobo π'da `hand_shaking.jks` yozildi va TCP 10001 orqali ishga tushirildi. Thor'da `~/Dev/lumi-wave` papkasi bor: odamni ko'rish (YOLOv8n), salomlashish (bosh + qo'l + ovoz), RAG bilim bazasi, gemma4 bilan EN/KO javob, whisper.cpp bilan eshitish, Supertonic bilan gapirish, `lumi.py` (kuzatish, suhbat, ovozli buyruqlar, patrol). Salomlashish va qo'l to'siq tuzatishi tasdiqlandi. Patrol birinchi urinishda batareya past (13 %) bo'lgani uchun uyga ketdi, chegara 20 % → 5 % qilindi. Hammasi 7a-bosqichda batafsil yozilgan. |

## Ertaga (2026-10-08) shu yerdan davom etamiz

1. Robotni zaryadlash (batareya 13 % edi). Mac'ni `Lumi10000013-5G` ga ulash (IP 192.168.10.200).
2. Thor'da: `cd ~/Dev/lumi-wave && .venv/bin/python lumi.py --patrol aisle_a,aisle_b` (**venv bilan**, oddiy `python` da cv2 yo'q). Eski jarayon ishlayotgan bo'lsa, avval Ctrl+C.
3. Patrolni kuzatish: markerlar orasida yuradimi, oldidagi odam uchun to'xtaydimi, suhbatdan keyin davom etadimi.
4. `HEAD_SIGN` va `LOOK` ishoralarini tekshirish, haqiqiy mehmon bilan suhbat.
5. Boshqaruv sahifasi yoki avtomatik ishga tushirishni tanlash va qilish.

## Qo'llanmalar

- Butun loyiha: https://claude.ai/artifact/2FQCeYgSrXRYYWwNWhCPmX
- `scene.xml` qatorma-qator: https://claude.ai/artifact/7QaR4iTLaGR7TVwWb5Lgdx

## Ochiq savollar

- Haqiqiy robotga qaysi gripper o'rnatiladi? (JAKA'ning Lumi to'plamida DH-PGEA-50; variantlar `docs/10_GRIPPER.md` da)
- Qaysi LLM ishlatiladi? (kompaniya Jetson Thor'da Qwen3-Omni ishlatyapti, `docs/08_NVIDIA_THOR.md`)
- ~~Qo'l controller versiyasi 1.7 mi yoki 3.2 mi?~~ Javob: 3.3.8_beta_lumi_minicab, `login(1)` (2026-10-07)
- Mikrofon massividan ovoz yo'nalishini qanday o'qish mumkin? (`docs/07_VOICE_AND_AUDIO.md`)
- Robotda tekshiriladigan qolgan narsalar: `docs/00_START_HERE.md` 9-bo'lim
