package com.example.data.api

import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import com.example.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.Request
import org.json.JSONObject
import java.util.concurrent.TimeUnit

object ApiClient {
    // Default emulator host address
    var baseUrl: String = "http://10.0.2.2:8000/"
        set(value) {
            field = if (value.endsWith("/")) value else "$value/"
            retrofitInstance = null
            apiServiceInstance = null
        }

    /** True once the user typed a URL in Settings; then live discovery never overrides it. */
    var userOverride: Boolean = false

    var authToken: String? = null

    private val moshi: Moshi by lazy {
        Moshi.Builder()
            .addLast(KotlinJsonAdapterFactory())
            .build()
    }

    private val okHttpClient: OkHttpClient by lazy {
        val logging = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BODY
        }
        OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(15, TimeUnit.SECONDS)
            .writeTimeout(15, TimeUnit.SECONDS)
            .addInterceptor(logging)
            .build()
    }

    private var retrofitInstance: Retrofit? = null
    private var apiServiceInstance: SafetyApiService? = null

    fun getService(): SafetyApiService {
        if (apiServiceInstance == null) {
            val retrofit = Retrofit.Builder()
                .baseUrl(baseUrl)
                .client(okHttpClient)
                .addConverterFactory(MoshiConverterFactory.create(moshi))
                .build()
            retrofitInstance = retrofit
            apiServiceInstance = retrofit.create(SafetyApiService::class.java)
        }
        return apiServiceInstance!!
    }

    fun getAuthHeader(): String {
        return if (!authToken.isNullOrEmpty()) "Bearer $authToken" else ""
    }

    /**
     * Reads the current demo backend URL from the hosted live.json (the same file the web demo uses).
     * Falls back to the emulator address when the phone is offline or no tunnel is open.
     */
    suspend fun resolveLiveBaseUrl() {
        if (userOverride) return
        val url = withContext(Dispatchers.IO) {
            runCatching {
                okHttpClient.newCall(Request.Builder().url(BuildConfig.LIVE_CONFIG_URL).build()).execute().use { res ->
                    if (!res.isSuccessful) null else JSONObject(res.body?.string() ?: "{}").optString("apiUrl")
                }
            }.getOrNull()
        }
        if (!url.isNullOrBlank() && url.startsWith("https://")) baseUrl = url
    }
}
