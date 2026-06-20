package com.elderbridge.guardianos.speech

import android.content.Context
import android.speech.tts.TextToSpeech
import android.util.Log
import java.util.Locale

/**
 * Global singleton manager for Text-To-Speech to ensure lifecycle safety,
 * avoid multiple instances, and provide reliable playback across the app.
 */
object SpeechManager : TextToSpeech.OnInitListener {
    private const val TAG = "SpeechManager"
    
    private var tts: TextToSpeech? = null
    private var isReady = false
    private var pendingText: String? = null

    /**
     * Initializes the TTS engine. Should be called once at app start or service start.
     */
    fun init(context: Context) {
        if (tts == null) {
            Log.d(TAG, "Initializing TTS Engine...")
            tts = TextToSpeech(context.applicationContext, this)
        }
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            val result = tts?.setLanguage(Locale.US)
            if (result == TextToSpeech.LANG_MISSING_DATA || result == TextToSpeech.LANG_NOT_SUPPORTED) {
                Log.e(TAG, "Language not supported or missing data")
            } else {
                isReady = true
                Log.d(TAG, "TTS Engine Ready")
                // Speak any text that was requested before initialization finished
                pendingText?.let {
                    speak(it)
                    pendingText = null
                }
            }
        } else {
            Log.e(TAG, "TTS Initialization failed with status: $status")
        }
    }

    /**
     * Speaks the provided [text]. If engine is not ready, it queues the text.
     */
    fun speak(text: String, queueMode: Int = TextToSpeech.QUEUE_FLUSH) {
        if (isReady) {
            Log.d(TAG, "Speaking: ${text.take(20)}...")
            tts?.speak(text, queueMode, null, "SpeechID_${System.currentTimeMillis()}")
        } else {
            Log.d(TAG, "TTS not ready, queuing text")
            pendingText = text
        }
    }

    /**
     * Stops any current speech.
     */
    fun stop() {
        if (isReady) {
            tts?.stop()
        }
    }

    /**
     * Releases resources. Call when the app or primary service is being destroyed.
     */
    fun shutdown() {
        Log.d(TAG, "Shutting down TTS Engine")
        tts?.stop()
        tts?.shutdown()
        tts = null
        isReady = false
    }
}
