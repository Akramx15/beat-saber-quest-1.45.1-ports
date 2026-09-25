# التثبيت على ويندوز وQuest

هذا المسار لإصدار **1.45.1_27839، رقم 3071** على Quest المستقل. إصدارات Steam والنسخة 1.40.8 تحتاج ملفات مختلفة.

**حالة هذه النسخة: تجريبية ومطروحة للمراجعة.** بناء الملفات اختُبر على Linux؛ مسار WSL2 الكامل على ويندوز لم يُختبر بعد. اختبارات المثبّت دون نظارة نجحت على ويندوز ولينكس، لكنها لا تثبت نجاح التثبيت الفعلي على كل جهاز.

## 1. تجهيز النظارة والنسخة الاحتياطية

ثبّت [Python لويندوز](https://www.python.org/downloads/windows/) بإصدار 3.10 أو أحدث، مع Python Launcher. افتح PowerShell جديدًا وتأكد أن الأمر التالي يعرض الإصدار:

```powershell
py -3 --version
```

فعّل Developer Mode، وصّل النظارة بكابل USB، واقبل رسالة USB debugging داخل النظارة. فك [Android Platform Tools الرسمية](https://developer.android.com/tools/releases/platform-tools) في مجلد مثل `C:\Tools\platform-tools`. استخدم المسار الفعلي عندك في الأوامر التالية؛ لا تحتاج إضافة ADB إلى PATH:

```powershell
$adb = 'C:\Tools\platform-tools\adb.exe'
& $adb devices
```

يجب أن يظهر الجهاز بحالة `device`. عند ظهور أكثر من جهاز، افصل الأجهزة الأخرى أثناء هذه الخطوات. الأمثلة التالية تفترض نظارة واحدة متصلة.

خذ نسخة من بياناتك الموجودة قبل تعديل اللعبة. مسارا بيانات Beat Saber المعتادان هما:

```text
/sdcard/Android/data/com.beatgames.beatsaber/files
/sdcard/ModData/com.beatgames.beatsaber
```

احتفظ كذلك بملفات OBB الموجودة في `/sdcard/Android/obb/com.beatgames.beatsaber`. لتصدير APK نسختك المثبتة إلى مجلد احتياطي جديد على الكمبيوتر، نفّذ في PowerShell نفسه:

```powershell
$backupDir = Join-Path $env:USERPROFILE ('Documents\BeatSaber-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backupDir -ErrorAction Stop | Out-Null
$apkLines = @(& $adb shell pm path com.beatgames.beatsaber)
if ($LASTEXITCODE -ne 0) { throw 'تعذر قراءة مسار APK؛ توقف هنا.' }
$apkPaths = @($apkLines | Where-Object { $_.StartsWith('package:') } | ForEach-Object { $_.Substring(8).Trim() })
if ($apkPaths.Count -ne 1) { throw 'لم يظهر APK واحد. راجع المسارات قبل المتابعة؛ لا تخمّن اسم الملف.' }
$apkCopy = Join-Path $backupDir 'BeatSaber.apk'
& $adb pull $apkPaths[0] $apkCopy
if ($LASTEXITCODE -ne 0) { throw 'فشل نسخ APK؛ توقف هنا.' }
Get-Item -LiteralPath $apkCopy | Select-Object FullName, Length
```

هذا ينسخ APK فقط؛ انسخ أيضًا مجلدي البيانات أعلاه وملفات OBB الموجودة إلى مجلد النسخة الاحتياطية باستخدام `adb pull` أو أداة النسخ التي تستخدمها. مثال لبيانات اللعبة:

```powershell
& $adb pull '/sdcard/Android/data/com.beatgames.beatsaber/files' (Join-Path $backupDir 'game-files')
if ($LASTEXITCODE -ne 0) { throw 'لم تكتمل نسخة بيانات اللعبة؛ لا تبدأ patching.' }
```

هذه الأوامر تقرأ النظارة وتكتب النسخة على الكمبيوتر. QuestPatcher يعيد تثبيت اللعبة أثناء patching، لذلك راجع نجاح نسخ بياناتك وحجم الملفات فعليًا قبل بدء تلك الخطوة. حزمة المودات لا تحتوي على نسخة احتياطية لبياناتك. احتفظ بالمسار الذي ظهر لملف `BeatSaber.apk` لاستخدامه في البناء.

## 2. تفعيل Scotland2

حمّل [QuestPatcher 2.10.0 لويندوز](https://github.com/Lauriethefish/QuestPatcher/releases/tag/2.10.0)، وافتحه مع اتصال النظارة. تأكد أن التطبيق المحدد هو `com.beatgames.beatsaber` وأن إصدار اللعبة صحيح، واختر **Scotland2** أثناء patching.

إذا تعذّر العثور على unstripped Unity مطابق تمامًا لهذا الإصدار، احتفظ بملف Unity الأصلي؛ لا تستخدم ملف إصدار آخر. هذا المسار يعتمد على `LibMainLoader v0.2.0` و`Scotland2 v0.1.7`؛ أداة التثبيت تتحقق من بصمتيهما. إذا كان برنامج patching قد حمّل إصدارًا مختلفًا، توقف عند رسالة عدم التطابق وراجع النسخة بدل تعطيل الفحص.

لا تحتاج روت. لا تجعل أداة أخرى تستبدل الاعتماديات تلقائيًا بإصدارات 1.40.8 بعد تثبيت الحزمة.

## 3. تجهيز حزمة المودات

نزّل ملف **Windows kit** من [صفحة الإصدارات](https://github.com/Akramx15/beat-saber-quest-1.45.1-ports/releases) وافكّه في مجلد محلي مثل `C:\Users\YourName\Downloads\ports`. استخدم ملفات الإصدار نفسه طوال الخطوات، لأن ملف الحزمة ووصفة البناء مرتبطان ببصمات محددة. تحتاج WSL2/Ubuntu لبناء المودات التي ليس لها QMOD موزّع هنا. خطوات تجهيز Ubuntu والأدوات موجودة في [BUILDING.md](../BUILDING.md).

داخل ZIP يوجد مجلد `beat-saber-quest-1.45.1-ports`؛ انقله أو غيّر اسمه إلى `ports` في المثال. يجب أن يكون `manage_modpack.py` مباشرة داخل مجلد `ports`، وليس داخل مجلد إضافي تحته.

استخدم نسخة APK التي تملكها أنت مع أمر توليد ملفات البناء. ملفات اللعبة المستخرجة تبقى في مجلد البناء المحلي، ولا ترفعها في issue أو GitHub.

افتح Terminal داخل مجلد الحزمة ونفّذ:

```powershell
py -3 manage_modpack.py plan --profile recommended
py -3 manage_modpack.py download --profile recommended
```

الأمر الثاني ينزّل الحزم الجاهزة إلى `qmods` ويعرض أسماء الحزم التي تحتاج بناءً محليًا. داخل WSL يظهر مسار ويندوز مثل `C:\Users\YourName\Downloads\ports\qmods` على شكل `/mnt/c/Users/YourName/Downloads/ports/qmods`.

بعد تجهيز Ubuntu، أنشئ نسخة نظيفة من ملفات الإصدار داخل مجلد Linux الشخصي. في **طرفية Ubuntu**، استبدل `YourName` ومسار الحزمة بمسارك الفعلي:

```sh
mkdir -p "$HOME/bs1451"
mkdir "$HOME/bs1451/ports" &&
  cp -a "/mnt/c/Users/YourName/Downloads/ports/." "$HOME/bs1451/ports/" &&
  cd "$HOME/bs1451/ports/builder" &&
  chmod +x clang_ndk.py
```

إذا كان مجلد `ports` داخل Linux موجودًا، يتوقف أمر الإنشاء؛ اختر اسمًا جديدًا للنسخة النظيفة وعدّل المسار في الأوامر. لا تخلط ملفات إصدار جديد مع مجلد بناء قديم.

أكمل إعداد أدوات البناء من [دليل البناء](../builder/README.md). ثم من مجلد `builder` نفسه نفّذ الأمرين التاليين. استبدل مسار APK بالمسار الذي صدّرته في الخطوة الأولى؛ اسم مجلد النسخة الاحتياطية هنا مثال:

```sh
python3 build.py generate --apk "/mnt/c/Users/YourName/Documents/BeatSaber-backup-YYYYMMDD-HHmmss/BeatSaber.apk"
python3 build.py build --dependency-qmods "/mnt/c/Users/YourName/Downloads/ports/qmods"
```

انتظر نجاح كل أمر قبل التالي. ملفات البناء تبقى افتراضيًا داخل `$HOME/.cache/bs1451-builder`. بعد اكتمال البناء فقط، انسخ النتائج من **Ubuntu** إلى مجلد الحزمة في ويندوز:

```sh
cp "$HOME/.cache/bs1451-builder/output/"*.qmod "/mnt/c/Users/YourName/Downloads/ports/qmods/"
cp "$HOME/.cache/bs1451-builder/output/build-receipt.json" "/mnt/c/Users/YourName/Downloads/ports/qmods/"
```

احتفظ أيضًا بالحزم الجاهزة التي نزلتها سابقًا. ارجع إلى **PowerShell داخل مجلد الحزمة في ويندوز** ثم نفّذ؛ عرّف `$adb` مجددًا إذا فتحت نافذة جديدة:

```powershell
py -3 manage_modpack.py verify --profile recommended --build-receipt .\qmods\build-receipt.json
& $adb devices
py -3 manage_modpack.py install --profile recommended --build-receipt .\qmods\build-receipt.json --adb "$adb"
```

إذا كان أكثر من جهاز متصل، أضف `--serial` ثم الرقم الذي ظهر لجهازك في `adb devices`. لا تنقل رقم جهاز شخص آخر. أمر `verify` لا يغيّر النظارة؛ `install` هو الذي ينسخ المودات بعد الفحوص والنسخ الاحتياطي.

توجد واجهة PowerShell اختيارية وأوامر اختيار الحزمة الأساسية والإضافات في [دليل أداة التثبيت](INSTALLER-CLI.md).

## 4. الاختبار بعد التثبيت

ابدأ بتشغيل اللعبة وفتح Solo، ثم جرّب أغنية Custom عادية. بعد ذلك جرّب البحث والتحميل، وأخيرًا خريطة معروفة تحتاج Chroma/Noodle. سجّل اسم الخريطة وصعوبتها إذا ظهرت مشكلة.

وصفة CongXinJian موجودة ضمن الحزمة الموصى بها؛ راجع [دليل CongXinJian وحدود اختباره](CONTROLLER-OFFSETS.ar.md) بعد بناء المود وتثبيته. الحزمة لا تنقل إعدادات قبضة صاحب النظارة التي جُرّبت عليها.

إذا رفض المثبّت وجود ملفات مودات غير معروفة، راجعها أولًا؛ الرفض يمنع تركيب خليط من اعتماديات مختلفة. إذا فشلت عملية الكتابة، راجع تقرير العملية ونسخة مجلد المودات الاحتياطية قبل إعادة المحاولة.
