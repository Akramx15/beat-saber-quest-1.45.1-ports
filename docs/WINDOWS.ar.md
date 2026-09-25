# التثبيت على ويندوز وQuest

هذا المسار لإصدار **1.45.1_27839، رقم 3071** على Quest المستقل. إصدارات Steam والنسخة 1.40.8 تحتاج ملفات مختلفة.

## 1. تجهيز النظارة والنسخة الاحتياطية

فعّل Developer Mode، وصّل النظارة بكابل USB، واقبل رسالة USB debugging داخل النظارة. استخدم [Android Platform Tools الرسمية](https://developer.android.com/tools/releases/platform-tools) لتشغيل ADB على ويندوز. أمر `adb devices` يجب أن يعرض الجهاز بحالة `device`.

خذ نسخة من بياناتك الموجودة قبل تعديل اللعبة. مسارا بيانات Beat Saber المعتادان هما:

```text
/sdcard/Android/data/com.beatgames.beatsaber/files
/sdcard/ModData/com.beatgames.beatsaber
```

احتفظ كذلك بنسختك الخاصة من APK وملفات OBB الموجودة. QuestPatcher يعيد تثبيت اللعبة أثناء patching، لذلك راجع نجاح النسخ الاحتياطي وحجم الملفات فعليًا قبل بدء تلك الخطوة. حزمة المودات لا تحتوي على نسخة احتياطية لبياناتك.

## 2. تفعيل Scotland2

حمّل [QuestPatcher 2.10.0 لويندوز](https://github.com/Lauriethefish/QuestPatcher/releases/tag/2.10.0)، وافتحه مع اتصال النظارة. تأكد أن التطبيق المحدد هو `com.beatgames.beatsaber` وأن إصدار اللعبة صحيح، واختر **Scotland2** أثناء patching.

إذا تعذّر العثور على unstripped Unity مطابق تمامًا لهذا الإصدار، احتفظ بملف Unity الأصلي؛ لا تستخدم ملف إصدار آخر. هذا المسار يعتمد على `LibMainLoader v0.2.0` و`Scotland2 v0.1.7`؛ أداة التثبيت تتحقق من بصمتيهما. إذا كان برنامج patching قد حمّل إصدارًا مختلفًا، توقف عند رسالة عدم التطابق وراجع النسخة بدل تعطيل الفحص.

لا تحتاج روت. لا تجعل أداة أخرى تستبدل الاعتماديات تلقائيًا بإصدارات 1.40.8 بعد تثبيت الحزمة.

## 3. تجهيز حزمة المودات

نزّل إصدار المستودع وافكّه في مجلد محلي. تحتاج Python 3 وADB لأداة التثبيت، وWSL2/Ubuntu لبناء المودات التي ليس لها QMOD موزّع هنا. خطوات البناء وتثبيت الأدوات موجودة في [BUILDING.md](../BUILDING.md).

استخدم نسخة APK التي تملكها أنت مع أمر توليد ملفات البناء. ملفات اللعبة المستخرجة تبقى في مجلد البناء المحلي، ولا ترفعها في issue أو GitHub.

افتح Terminal داخل مجلد الحزمة ونفّذ:

```powershell
py -3 manage_modpack.py plan --profile recommended
py -3 manage_modpack.py download --profile recommended
```

الأمر الثاني ينزّل الحزم الجاهزة إلى `qmods` ويعرض أسماء الحزم التي تحتاج بناءً محليًا. استخدم هذا المجلد نفسه لاعتماديات البناء، باتباع [BUILDING.md](../BUILDING.md). داخل WSL يظهر مسار ويندوز مثل `C:\Users\YourName\Downloads\ports\qmods` على شكل `/mnt/c/Users/YourName/Downloads/ports/qmods`.

بعد اكتمال البناء، انسخ ملفات QMOD الجديدة و`build-receipt.json` من مجلد `output` في WSL إلى مجلد `qmods` على ويندوز، مع إبقاء الملفات التي نزلها الأمر السابق. ثم نفّذ:

```powershell
py -3 manage_modpack.py verify --profile recommended --build-receipt .\qmods\build-receipt.json
adb devices
py -3 manage_modpack.py install --profile recommended --build-receipt .\qmods\build-receipt.json
```

إذا كان أكثر من جهاز متصل، أضف `--serial` ثم الرقم الذي ظهر لجهازك في `adb devices`. لا تنقل رقم جهاز شخص آخر. أمر `verify` لا يغيّر النظارة؛ `install` هو الذي ينسخ المودات بعد الفحوص والنسخ الاحتياطي.

توجد واجهة PowerShell اختيارية وأوامر اختيار الحزمة الأساسية والإضافات في [دليل أداة التثبيت](INSTALLER-CLI.md).

## 4. الاختبار بعد التثبيت

ابدأ بتشغيل اللعبة وفتح Solo، ثم جرّب أغنية Custom عادية. بعد ذلك جرّب البحث والتحميل، وأخيرًا خريطة معروفة تحتاج Chroma/Noodle. سجّل اسم الخريطة وصعوبتها إذا ظهرت مشكلة.

لمعايرة السيوف راجع [دليل CongXinJian](CONTROLLER-OFFSETS.ar.md). الحزمة لا تنقل إعدادات قبضة صاحب النظارة التي جُرّبت عليها.

إذا رفض المثبّت وجود ملفات مودات غير معروفة، راجعها أولًا؛ الرفض يمنع تركيب خليط من اعتماديات مختلفة. إذا فشلت عملية الكتابة، راجع تقرير العملية ونسخة مجلد المودات الاحتياطية قبل إعادة المحاولة.
