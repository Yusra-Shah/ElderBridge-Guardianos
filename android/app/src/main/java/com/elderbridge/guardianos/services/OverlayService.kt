package com.elderbridge.guardianos.services

import android.app.Service
import android.content.Intent
import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.drawable.GradientDrawable
import android.os.IBinder
import android.util.Log
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ScrollView
import android.speech.tts.TextToSpeech
import android.widget.TextView
import com.elderbridge.guardianos.network.ApiClient
import com.elderbridge.guardianos.network.FinalDecision
import com.elderbridge.guardianos.network.IncomingEvent
import com.elderbridge.guardianos.redaction.ScreenContentHolder
import kotlinx.coroutines.cancel
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.Locale

class OverlayService : Service() {

    private lateinit var windowManager: WindowManager
    private var bubbleView: View? = null
    private var expandedCard: View? = null
    private var isBubbleExpanded = false

    // Coroutine scope tied to this service's lifetime; cancelled in onDestroy
    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private var analyzeJob: Job? = null

    // Kept so the API response can update in-place without rebuilding the card
    private var cardHeaderView: TextView? = null
    private var cardBodyView: TextView? = null
    private var readAloudBtn: Button? = null

    private var tts: TextToSpeech? = null
    private var ttsReady = false

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        windowManager = getSystemService(WINDOW_SERVICE) as WindowManager
        tts = TextToSpeech(this) { status ->
            ttsReady = (status == TextToSpeech.SUCCESS)
            if (ttsReady) tts?.language = Locale.getDefault()
        }
        addBubble()
    }

    // ── Bubble ────────────────────────────────────────────────────────────────

    private fun addBubble() {
        val dp = resources.displayMetrics.density
        val bubblePx = (64 * dp).toInt()

        val params = WindowManager.LayoutParams(
            bubblePx,
            bubblePx,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = 0
            y = 200
        }

        val frame = FrameLayout(this)
        frame.background = circleDrawable(Color.parseColor("#1565C0"))

        val label = TextView(this).apply {
            text = "EB"
            textSize = 16f
            setTextColor(Color.WHITE)
            gravity = Gravity.CENTER
        }
        frame.addView(label, FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.MATCH_PARENT
        ))

        var initX = 0
        var initY = 0
        var touchX = 0f
        var touchY = 0f
        var dragged = false

        frame.setOnTouchListener { _, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    initX = params.x; initY = params.y
                    touchX = event.rawX; touchY = event.rawY
                    dragged = false
                    true
                }
                MotionEvent.ACTION_MOVE -> {
                    val dx = (event.rawX - touchX).toInt()
                    val dy = (event.rawY - touchY).toInt()
                    if (kotlin.math.abs(dx) > 8 || kotlin.math.abs(dy) > 8) dragged = true
                    params.x = initX + dx
                    params.y = initY + dy
                    windowManager.updateViewLayout(frame, params)
                    true
                }
                MotionEvent.ACTION_UP -> {
                    if (!dragged) toggleExpanded()
                    true
                }
                else -> false
            }
        }

        bubbleView = frame
        windowManager.addView(frame, params)
        Log.d(TAG, "Overlay bubble added")
    }

    // ── Card lifecycle ────────────────────────────────────────────────────────

    private fun toggleExpanded() {
        if (isBubbleExpanded) collapseCard() else expandCard()
        isBubbleExpanded = !isBubbleExpanded
    }

    private fun expandCard() {
        val dp = resources.displayMetrics.density
        val cardParams = WindowManager.LayoutParams(
            (300 * dp).toInt(),
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = (16 * dp).toInt()
            y = (280 * dp).toInt()
        }

        val pad = (20 * dp).toInt()
        val card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(pad, pad, pad, pad)
            background = roundedDrawable(Color.parseColor("#003C8F"), 16 * dp)
        }

        val snapshot = ScreenContentHolder.get()
        val hasContent = snapshot != null && snapshot.redactedText.isNotBlank()

        // Header label — updated in-place by showResponse / showError
        val headerTv = TextView(this).apply {
            text = if (hasContent) THINKING_MESSAGES[0] else "Not ready yet"
            textSize = 13f
            setTextColor(Color.parseColor("#5E92F3"))
            setPadding(0, 0, 0, (10 * dp).toInt())
        }
        cardHeaderView = headerTv

        // Body — updated in-place when the API responds
        val bodyTv = TextView(this).apply {
            text = if (hasContent) "" else "Open a form or message, then tap me again."
            textSize = 17f
            setTextColor(Color.WHITE)
            setPadding(0, 0, 0, (20 * dp).toInt())
            setLineSpacing(0f, 1.4f)
        }
        cardBodyView = bodyTv

        // Cap body height so long responses scroll rather than pushing Close off screen
        val maxBodyHeightPx = (400 * dp).toInt()
        val bodyScroll = object : ScrollView(this) {
            override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
                super.onMeasure(
                    widthMeasureSpec,
                    View.MeasureSpec.makeMeasureSpec(maxBodyHeightPx, View.MeasureSpec.AT_MOST)
                )
            }
        }.apply {
            addView(bodyTv, LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ))
        }

        val readAloudBtnView = Button(this).apply {
            text = "Read Aloud"
            setTextColor(Color.WHITE)
            background = roundedDrawable(Color.parseColor("#1565C0"), 10 * dp)
            visibility = View.GONE
        }
        readAloudBtn = readAloudBtnView

        val closeBtn = Button(this).apply {
            text = "Close"
            setTextColor(Color.WHITE)
            background = roundedDrawable(Color.parseColor("#1565C0"), 10 * dp)
            setOnClickListener { collapseCard(); isBubbleExpanded = false }
        }

        card.addView(headerTv)
        card.addView(bodyScroll)
        card.addView(readAloudBtnView, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        ).apply { bottomMargin = (8 * dp).toInt() })
        card.addView(closeBtn)

        expandedCard = card
        windowManager.addView(card, cardParams)
        Log.d(TAG, "Overlay card expanded")

        if (hasContent) {
            startAnalysis(snapshot!!)
        }
    }

    private fun collapseCard() {
        // Cancel any in-flight API call so a late response can't touch removed views
        analyzeJob?.cancel()
        analyzeJob = null
        tts?.stop()
        cardHeaderView = null
        cardBodyView = null
        readAloudBtn = null
        expandedCard?.let { windowManager.removeView(it) }
        expandedCard = null
        Log.d(TAG, "Overlay card collapsed")
    }

    // ── API call ──────────────────────────────────────────────────────────────

    private fun startAnalysis(snapshot: ScreenContentHolder.ScreenSnapshot) {
        analyzeJob?.cancel()
        analyzeJob = serviceScope.launch {
            val rotationJob = launch {
                var i = 0
                while (isActive) {
                    cardHeaderView?.text = THINKING_MESSAGES[i % THINKING_MESSAGES.size]
                    i++
                    delay(8_000)
                }
            }
            try {
                // SECURITY: snapshot.redactedText originates from ScreenContentHolder,
                // which ScreenReaderService writes only after RedactionEngine.redact().
                // No raw screen text ever reaches this payload.
                val isoTimestamp = java.time.Instant.ofEpochMilli(snapshot.capturedAtMs).toString()
                val event = IncomingEvent(
                    eventType = "FORM_SCREEN",
                    sourceApp = snapshot.sourcePackage,
                    redactedText = snapshot.redactedText,
                    timestamp = isoTimestamp,
                    userId = PLACEHOLDER_USER_ID
                )

                val decision: FinalDecision = withContext(Dispatchers.IO) {
                    ApiClient.api.analyzeEvent(event)
                }
                Log.d(TAG, "analyzeEvent raw response: ${com.google.gson.Gson().toJson(decision)}")

                if (isActive) showResponse(decision)

            } catch (e: CancellationException) {
                throw e // always rethrow so coroutine framework cancels cleanly
            } catch (e: Exception) {
                Log.w(TAG, "analyzeEvent failed (${e.javaClass.simpleName}): ${e.message}")
                if (isActive) showError(e)
            } finally {
                rotationJob.cancel()
            }
        }
    }

    // Both run on Dispatchers.Main (the scope default), so direct View mutation is safe

    private fun showResponse(decision: FinalDecision) {
        cardHeaderView?.text = "ElderBridge says:"
        cardBodyView?.text = decision.responseText
        readAloudBtn?.apply {
            visibility = View.VISIBLE
            setOnClickListener {
                if (ttsReady) tts?.speak(decision.responseText, TextToSpeech.QUEUE_FLUSH, null, "eb_tts")
            }
        }
    }

    private fun showError(e: Exception) {
        cardHeaderView?.text = "Connection issue"
        cardBodyView?.text = e.message ?: "Request failed"
    }

    // ── Lifecycle ─────────────────────────────────────────────────────────────

    override fun onDestroy() {
        super.onDestroy()
        serviceScope.cancel()       // cancels analyzeJob and all child coroutines
        tts?.stop()
        tts?.shutdown()
        tts = null
        bubbleView?.let { windowManager.removeView(it) }
        collapseCard()
        Log.d(TAG, "OverlayService destroyed")
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private fun circleDrawable(color: Int) = GradientDrawable().apply {
        shape = GradientDrawable.OVAL
        setColor(color)
    }

    private fun roundedDrawable(color: Int, radiusPx: Float) = GradientDrawable().apply {
        shape = GradientDrawable.RECTANGLE
        cornerRadius = radiusPx
        setColor(color)
    }

    companion object {
        private const val TAG = "OverlayService"

        // TODO: Replace with a real authenticated user ID when the auth module lands
        private const val PLACEHOLDER_USER_ID = "00000000-0000-0000-0000-000000000001"

        private val THINKING_MESSAGES = listOf(
            "Checking official sources…",
            "Analysing your screen…",
            "Preparing your explanation…"
        )
    }
}
