package com.elderbridge.guardianos.network

import com.elderbridge.guardianos.BuildConfig
import com.google.gson.GsonBuilder
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object ApiClient {

    // ─────────────────────────────────────────────────────────────────────────
    // TODO: Set this to your backend machine's LAN IP before testing.
    //
    //   1. On the backend machine run:
    //        Windows → ipconfig
    //        macOS   → ipconfig getifaddr en0
    //        Linux   → ip addr show | grep "inet "
    //   2. Replace the placeholder below with the result, keeping the port and
    //      trailing slash:  "http://192.168.1.42:8000/"
    //
    // File: android/app/src/main/java/com/elderbridge/guardianos/network/ApiClient.kt
    // ─────────────────────────────────────────────────────────────────────────
    const val BASE_URL = "http://192.168.100.94:8000/"

    private val gson = GsonBuilder()
        .serializeNulls()
        .create()

    private val okHttpClient: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(120, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .apply {
                // Body-level logging only in debug builds — never in release
                if (BuildConfig.DEBUG) {
                    addInterceptor(HttpLoggingInterceptor().apply {
                        level = HttpLoggingInterceptor.Level.BODY
                    })
                }
            }
            .build()
    }

    val api: ElderBridgeApi by lazy {
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(okHttpClient)
            .addConverterFactory(GsonConverterFactory.create(gson))
            .build()
            .create(ElderBridgeApi::class.java)
    }
}
