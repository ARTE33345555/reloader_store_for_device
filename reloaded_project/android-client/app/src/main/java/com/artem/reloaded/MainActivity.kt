package com.artem.reloaded

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.FileProvider
import androidx.room.*
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import com.google.gson.annotations.SerializedName
import kotlinx.coroutines.*
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.*
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.net.URL
import java.security.MessageDigest
import java.util.concurrent.TimeUnit
import java.lang.Exception

// =========================================================================
// КОНСТАНТИ (ОНОВІТЬ ВАШІ КЛЮЧІ!)
// =========================================================================

private const val TAG = "ReloadedMarket"
// !!! ВАШ АДРЕС HTTPS-СЕРВЕРА !!!
private const val BASE_URL = "https://your-reloaded-server.com/" 
// !!! ВАШ КЛЮЧ API VIRUSTOTAL !!! (Отримайте Public API Key)
private const val VIRUSTOTAL_API_KEY = "YOUR_VIRUSTOTAL_API_KEY_HERE"
private const val VIRUSTOTAL_BASE_URL = "https://www.virustotal.com/api/v3/"

// =========================================================================
// МОДЕЛІ ДАНИХ (AppMetadata, ScanResult, VtReportResponse)
// =========================================================================

/** Модель каталогу для Retrofit */
data class AppMetadata(
    @SerializedName("package_name") val packageName: String,
    @SerializedName("title") val title: String,
    @SerializedName("version_name") val versionName: String,
    @SerializedName("download_url") val downloadUrl: String,
    @SerializedName("sha256") val sha256: String,
    @SerializedName("min_sdk") val minSdk: Int,
    @SerializedName("permissions_summary") val permissionsSummary: String
)

/** Результат сканування (для Room DB) */
@Entity(tableName = "scan_results")
data class ScanResult(
    @PrimaryKey val sha256: String,
    val packageName: String?,
    val versionName: String?,
    val verdict: String, // 'safe', 'unknown', 'suspicious', 'MALWARE'
    val riskScore: Int, // Локальна оцінка ризику
    val vtVerdict: String?, // Вердикт VT (Clean, Malware, Unknown)
    val vtDetections: Int, // Кількість виявлень
    val checkedAt: Long
)

/** Модель для відповіді VirusTotal API */
data class VtReportResponse(val data: VtData?)
data class VtData(val attributes: VtAttributes?)
data class VtAttributes(@SerializedName("last_analysis_stats") val lastAnalysisStats: VtAnalysisStats?)
data class VtAnalysisStats(val harmless: Int, val malicious: Int, val suspicious: Int, val undetected: Int)

/** Інформація про APK (для ApkInspector) */
data class ApkInfo(val packageName: String?, val versionName: String?, val permissions: List<String>, val signatureFingerprint: String?)

// =========================================================================
// СЕРВІСИ API
// =========================================================================

interface ApiService {
    @GET("api/v1/apps/details/{packageName}")
    suspend fun getAppDetails(@Path("packageName") packageName: String, @Query("sdk_version") sdkVersion: Int): AppMetadata
}

interface VtApiService {
    @Headers("x-apikey: $VIRUSTOTAL_API_KEY")
    @GET("files/{hash}")
    suspend fun getFileReport(@Path("hash") hash: String): VtReportResponse
}

// =========================================================================
// ЛОГІКА БЕЗПЕКИ ТА СКАРНУВАННЯ (DAO та Хелпери)
// =========================================================================

/** Інтерфейс DAO для Room */
@Dao
interface ScanDao {
    @Query("SELECT * FROM scan_results WHERE sha256 = :hash LIMIT 1")
    suspend fun getByHash(hash: String): ScanResult?
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(result: ScanResult)
}

/** Вирахування хешу SHA-256 файлу */
fun sha256OfFile(file: File): String {
    val digest = MessageDigest.getInstance("SHA-256")
    FileInputStream(file).use { fis ->
        val buffer = ByteArray(32 * 1024)
        var read: Int
        while (fis.read(buffer).also { read = it } > 0) {
            digest.update(buffer, 0, read)
        }
    }
    return digest.digest().joinToString("") { "%02x".format(it) }
}

/** Аналіз APK-файлу для отримання дозволів */
fun inspectApk(context: Context, apkPath: String): ApkInfo {
    val pm = context.packageManager
    val flags = PackageManager.GET_PERMISSIONS or PackageManager.GET_SIGNING_CERTIFICATES
    val pi = pm.getPackageArchiveInfo(apkPath, flags) ?: return ApkInfo(null, null, emptyList(), null)
    pi.applicationInfo.sourceDir = apkPath
    pi.applicationInfo.publicSourceDir = apkPath

    val perms = pi.requestedPermissions?.toList() ?: emptyList()
    val signingInfo = pi.signingInfo
    val fingerprint = signingInfo?.apkContentsSigners?.firstOrNull()?.let { cert ->
        val md = MessageDigest.getInstance("SHA-256")
        md.update(cert.toByteArray())
        md.digest().joinToString("") { "%02x".format(it) }
    }
    return ApkInfo(pi.packageName, pi.versionName, perms, fingerprint)
}

/** Оцінка ризику дозволів */
fun permissionRiskScore(permissions: List<String>): Int {
    val heavy = setOf(
        "android.permission.SEND_SMS", "android.permission.CALL_PHONE", "android.permission.RECORD_AUDIO",
        "android.permission.READ_SMS", "android.permission.WRITE_EXTERNAL_STORAGE",
        "android.permission.REQUEST_INSTALL_PACKAGES"
    )
    var score = 0
    for (p in permissions) {
        when {
            p in heavy -> score += 40
            p.contains("LOCATION") -> score += 20
            p.contains("CONTACT") -> score += 25
            else -> score += 5
        }
    }
    return score.coerceIn(0, 100)
}

/** Основна функція сканування (Локальна та VT) */
suspend fun preInstallScan(context: Context, apkFile: File, dao: ScanDao, vtService: VtApiService): ScanResult = withContext(Dispatchers.IO) {
    val hash = sha256OfFile(apkFile)
    dao.getByHash(hash)?.let { return@withContext it }

    val info = inspectApk(context, apkFile.absolutePath)
    val score = permissionRiskScore(info.permissions)

    // --- Запит до VirusTotal ---
    val vtResult = try {
        vtService.getFileReport(hash)
    } catch (e: Exception) {
        Log.e(TAG, "Помилка VT: ${e.message}")
        null
    }
    
    val vtDetections = vtResult?.data?.attributes?.lastAnalysisStats?.malicious ?: 0
    val vtVerdict = when {
        vtDetections > 0 -> "Malware"
        vtResult?.data != null -> "Clean"
        else -> "Unknown"
    }
    
    val finalVerdict = when {
        vtDetections > 2 -> "MALWARE" 
        score >= 60 -> "suspicious"
        score >= 20 -> "unknown"
        else -> "safe"
    }

    val result = ScanResult(
        hash, info.packageName, info.versionName, finalVerdict, score, 
        vtVerdict, vtDetections, System.currentTimeMillis()
    )
    dao.upsert(result)
    
    // Заглушка для фонової синхронізації
    val work = OneTimeWorkRequestBuilder<androidx.work.PeriodicWorkRequest>()
        .setInitialDelay(1, TimeUnit.HOURS).build()
    WorkManager.getInstance(context).enqueue(work)

    return@withContext result
}

// =========================================================================
// ГОЛОВНА АКТИВНІСТЬ (MAIN ACTIVITY)
// =========================================================================

class MainActivity : AppCompatActivity() {
    
    private lateinit var apiService: ApiService
    private lateinit var vtApiService: VtApiService
    
    // --- Заглушка для Room DAO (ви маєте налаштувати реальну базу даних) ---
    private val scanDao: ScanDao = object : ScanDao {
        override suspend fun getByHash(hash: String): ScanResult? = null
        override suspend fun upsert(result: ScanResult) { /* do nothing */ }
    }
    // -----------------------------------------------------------------------

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        setupThemedUI()

        // 1. Ініціалізація Retrofit для Reloaded API
        val retrofitReloaded = Retrofit.Builder()
            .baseUrl(BASE_URL)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
        apiService = retrofitReloaded.create(ApiService::class.java)
        
        // 2. Ініціалізація Retrofit для VirusTotal API
        val vtClient = okhttp3.OkHttpClient.Builder()
            .addInterceptor { chain ->
                // Додаємо API Key в заголовок запиту
                val request = chain.request().newBuilder()
                    .addHeader("x-apikey", VIRUSTOTAL_API_KEY)
                    .build()
                chain.proceed(request)
            }.build()

        val retrofitVt = Retrofit.Builder()
            .baseUrl(VIRUSTOTAL_BASE_URL)
            .addConverterFactory(GsonConverterFactory.create())
            .client(vtClient) 
            .build()
        vtApiService = retrofitVt.create(VtApiService::class.java)
        
        handleIncomingIntent(intent)
    }

    private fun setupThemedUI() {
        // Логіка вибору UI-стилю для маскування
        when {
            Build.VERSION.SDK_INT <= Build.VERSION_CODES.JELLY_BEAN_MR2 -> {
                setContentView(R.layout.activity_main_old) // Android Market Style
            }
            Build.VERSION.SDK_INT <= Build.VERSION_CODES.M -> {
                setContentView(R.layout.activity_main_mid) // Early Google Play Style
            }
            else -> {
                setContentView(R.layout.activity_main_modern) 
            }
        }
        // Маскування назви в заголовку вікна
        title = getString(R.string.app_name_market_mask) 
    }

    private fun handleIncomingIntent(intent: Intent?) {
        if (intent == null) return

        if (Intent.ACTION_VIEW == intent.action) {
            val data: Uri? = intent.data
            var packageName: String? = null

            if (data != null) {
                if (data.scheme == "market" || data.host == "play.google.com") {
                    packageName = data.getQueryParameter("id")
                }

                if (packageName != null) {
                    searchInCatalog(packageName) 
                }
            }
        } else {
            showCatalogList()
        }
    }
    
    private fun showCatalogList() {
        findViewById<TextView>(R.id.status_text)?.text = "Перехоплення не відбулося. Ласкаво просимо до Reloaded Market!"
    }

    private fun searchInCatalog(packageName: String) {
        findViewById<TextView>(R.id.status_text)?.text = "Шукаємо сумісну версію '$packageName' у нашому архіві..."
        
        CoroutineScope(Dispatchers.Main).launch {
            try {
                val metadata = apiService.getAppDetails(packageName, Build.VERSION.SDK_INT)
                showAppDetailsUI(metadata)

            } catch (e: Exception) {
                Log.e(TAG, "Помилка при пошуку $packageName: ${e.message}")
                findViewById<TextView>(R.id.status_text)?.text = 
                    "Помилка: Додаток '$packageName' не знайдено для вашої версії Android або сервер недоступний."
            }
        }
    }

    private fun showAppDetailsUI(metadata: AppMetadata) {
        val statusText = findViewById<TextView>(R.id.status_text) ?: return
        val installButton = findViewById<Button>(R.id.install_button) 

        statusText.text = "Знайдено: ${metadata.title} v${metadata.versionName}\nДозволи: ${metadata.permissionsSummary}"
        installButton?.apply {
            visibility = android.view.View.VISIBLE
            setOnClickListener { 
                CoroutineScope(Dispatchers.Main).launch {
                    installButton.isEnabled = false
                    downloadAndInstall(metadata)
                    installButton.isEnabled = true
                }
            }
        }
    }

    private suspend fun downloadAndInstall(metadata: AppMetadata) {
        val downloadUrl = BASE_URL.trimEnd('/') + metadata.downloadUrl
        val targetFile = File(externalCacheDir, metadata.packageName + "-" + metadata.versionName + ".apk")
        val statusText = findViewById<TextView>(R.id.status_text) ?: return

        try {
            statusText.text = "Скачування ${metadata.title}..."
            
            withContext(Dispatchers.IO) {
                URL(downloadUrl).openStream().use { input ->
                    FileOutputStream(targetFile).use { output ->
                        input.copyTo(output)
                    }
                }
            }

            statusText.text = "Скачування завершено. Запускаємо сканер (Локально + VT)..."
            val scanResult = preInstallScan(this, targetFile, scanDao, vtApiService)
            
            statusText.text = "Сканування завершено.\nРизик (Локальний): ${scanResult.riskScore}%.\nVT (Виявлено): ${scanResult.vtDetections}.\nФІНАЛЬНИЙ ВЕРДИКТ: ${scanResult.verdict}"

            if (scanResult.verdict == "MALWARE") {
                statusText.text = "ВСТАНОВЛЕННЯ ЗАБЛОКОВАНО! Обнаружена загроза (VT: ${scanResult.vtDetections} виявлень)."
                return
            }

            statusText.text = "Перевірка пройдена. Запускаємо системний установник..."
            startInstaller(targetFile)

        } catch (e: Exception) {
            statusText.text = "Помилка скачування/сканування: ${e.message}"
            Log.e(TAG, "Помилка: ${e.message}", e)
        }
    }
    
    private fun startInstaller(apkFile: File) {
        val installIntent = Intent(Intent.ACTION_VIEW)

        if (Build.VERSION.SDK_INT <= Build.VERSION_CODES.M) { 
            installIntent.setDataAndType(
                Uri.fromFile(apkFile),
                "application/vnd.android.package-archive"
            )
        } else {
            val fileUri = FileProvider.getUriForFile(
                this,
                packageName + ".provider", 
                apkFile
            )
            installIntent.setDataAndType(
                fileUri,
                "application/vnd.android.package-archive"
            )
            installIntent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }

        installIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        startActivity(installIntent)
    }
}