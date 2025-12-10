const express = require('express');
const multer = require('multer');
// Налаштування multer для збереження файлів у папці 'uploads/'
const upload = multer({ dest: 'uploads/' }); 
const app = express();

// !!! УВАГА: Для тестування на емуляторі використовуйте IP вашої машини або спеціальний IP емулятора
// !!! Змініть порт, якщо 3000 зайнятий
const PORT = 3000; 

app.use(express.json());

// ----------------------------------------------------
// 1. ЕНДПОІНТИ КАТАЛОГУ (API, ЯКІ ОЧІКУЄ КЛІЄНТ)
// ----------------------------------------------------

// Маршрут 1: Отримання деталей програми за ID (Очікується Kotlin-клієнтом)
// Цей ендпоінт повертає метадані для перехопленого пакету.
app.get('/api/v1/apps/details/:packageName', (req, res) => {
    const packageName = req.params.packageName;
    const sdkVersion = req.query.sdk_version;
    
    console.log(`[API] Запит деталей для пакету: ${packageName} (SDK: ${sdkVersion})`);

    // Мокап-відповідь, що імітує структуру AppMetadata.kt
    res.json({ 
        package_name: packageName,
        title: `Архівна версія ${packageName}`,
        version_name: '1.0.1-old',
        // ВАЖЛИВО: download_url має бути відносним шляхом до файлу на вашому сервері
        download_url: `/download/${packageName}_${sdkVersion}.apk`, 
        sha256: 'a94a8fe5ccb19ba61c4c0873d391e987982fbbd3', // Фейковий хеш
        min_sdk: 8,
        permissions_summary: 'Інтернет, Контакти, GPS (Перевірено)'
    });
});

// Маршрут 2: Реальний API для завантаження APK
// В реальному проекті тут має бути логіка, що віддає файл
app.get('/download/:filename', (req, res) => {
    const filename = req.params.filename;
    // ТУТ МАЄ БУТИ ЛОГІКА ВІДДАЧІ APK-файлу
    console.log(`[API] Спроба скачати: ${filename}`);
    
    // Заглушка: Ви можете відправити будь-який маленький тестовий APK-файл
    // res.sendFile(path.join(__dirname, 'mock_test.apk')); 
    res.status(404).send('APK File Not Found (Mock)');
});


// ----------------------------------------------------
// 2. ВЛАСНІ СЛУЖБОВІ ЕНДПОІНТИ
// ----------------------------------------------------

// Отримання повного списку (залишимо як заглушку)
app.get('/apps', (req, res) => {
  res.json([]);
});

// Завантаження APK через Multer (з вашого коду)
app.post('/upload', upload.single('apk'), (req, res) => {
    console.log(`[SERVICE] Отримано файл: ${req.file.originalname}`);
    // compute sha256 on server side, validate metadata, save
    res.json({ ok: true, filename: req.file.filename });
});

// Запит на сканування (залишимо як заглушку)
app.post('/scan', (req, res) => {
    const { sha256, packageName } = req.body;
    console.log(`[SERVICE] Запит на сканування хешу: ${sha256}`);
    // lookup in DB (placeholder)
    res.json({ verdict: 'unknown' });
});

app.listen(PORT, () => console.log(`Backend running on port ${PORT}`));