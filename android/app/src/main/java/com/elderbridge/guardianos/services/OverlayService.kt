package com.elderbridge.guardianos.services

import android.Manifest
import android.animation.ObjectAnimator
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.os.Build
import androidx.core.app.NotificationCompat
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.drawable.GradientDrawable
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.util.Log
import android.widget.Toast
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.EditText
import android.widget.ScrollView
import android.speech.tts.TextToSpeech
import android.widget.TextView
import com.elderbridge.guardianos.data.HistoryStore
import com.elderbridge.guardianos.data.UserProfileStore
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
    private var bubbleLabel: TextView? = null
    private var bubblePulseAnim: ObjectAnimator? = null
    private var expandedCard: View? = null
    private var expandedCardParams: WindowManager.LayoutParams? = null
    private var menuView: View? = null
    private var bubbleParams: WindowManager.LayoutParams? = null

    // Coroutine scope tied to this service's lifetime; cancelled in onDestroy
    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private var analyzeJob: Job? = null

    // Kept so the API response can update in-place without rebuilding the card
    private var cardHeaderView: TextView? = null
    private var cardBodyView: TextView? = null
    private var cardBodyScroll: ScrollView? = null
    private var actionRow: LinearLayout? = null
    private var readAloudBtn: Button? = null

    private data class SavedResponse(
        val headerText: String,
        val bodyText: String,
        val riskFlag: String
    )
    private var savedResponse: SavedResponse? = null

    // Chat mode state
    private var chatArea: LinearLayout? = null
    private var chatScrollView: ScrollView? = null
    private var chatMessagesContainer: LinearLayout? = null
    private var chatEditText: EditText? = null
    private var isChatMode = false
    private var currentAiResponse: String = ""

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

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startAsForeground()
        return START_STICKY
    }

    private fun startAsForeground() {
        val channelId = "elderbridge_overlay"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                channelId,
                "ElderBridge Assistant",
                NotificationManager.IMPORTANCE_LOW
            )
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
        val notification = NotificationCompat.Builder(this, channelId)
            .setContentTitle("ElderBridge is active")
            .setContentText("Helping you stay safe")
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
        startForeground(1, notification)
    }

    // ── Bubble ────────────────────────────────────────────────────────────────

    private fun addBubble() {
        val dp = resources.displayMetrics.density
        val bubblePx = (64 * dp).toInt()
        val xBtnPx = (20 * dp).toInt()

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
        bubbleParams = params

        val frame = FrameLayout(this)
        frame.background = circleDrawable(Color.parseColor("#1565C0"))

        val label = TextView(this).apply {
            text = "EB"
            textSize = 16f
            setTextColor(Color.WHITE)
            gravity = Gravity.CENTER
        }
        bubbleLabel = label
        frame.addView(label, FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.MATCH_PARENT
        ))

        // X button is a separate clickable child — Android dispatches its tap before
        // the parent frame's onTouchListener, so no coordinate detection is needed.
        val xBtn = TextView(this).apply {
            text = "✕"
            textSize = 10f
            setTextColor(Color.WHITE)
            gravity = Gravity.CENTER
            background = circleDrawable(Color.parseColor("#C62828"))
            isFocusable = false
            isClickable = true
            setOnClickListener {
                UserProfileStore.setAssistantEnabled(this@OverlayService, false)
                stopSelf()
            }
        }
        frame.addView(xBtn, FrameLayout.LayoutParams(xBtnPx, xBtnPx).apply {
            gravity = Gravity.TOP or Gravity.END
        })

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
        try {
            windowManager.addView(frame, params)
        } catch (e: Exception) {
            Log.e(TAG, "addView failed: ${e.message}")
        }
        Log.d(TAG, "Overlay bubble added")
    }

    // ── Card lifecycle ────────────────────────────────────────────────────────

    private fun toggleExpanded() {
        if (menuView != null) hideMenu() else showMenu()
    }

    // ── Quick-action menu ─────────────────────────────────────────────────────

    private fun showMenu() {
        if (bubbleParams == null) return
        if (menuView != null) { hideMenu(); return }
        val dp = resources.displayMetrics.density
        val bx = bubbleParams?.x ?: 0
        val by = bubbleParams?.y ?: 200

        val menuParams = WindowManager.LayoutParams(
            (170 * dp).toInt(),
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = bx + (70 * dp).toInt()
            y = by
        }

        val pad = (10 * dp).toInt()
        val gap = (6 * dp).toInt()
        val menu = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(pad, pad, pad, pad)
            background = roundedDrawable(Color.parseColor("#1A237E"), 12 * dp)
        }

        fun addBtn(label: String, color: String, last: Boolean = false, onClick: () -> Unit) {
            val btn = Button(this).apply {
                text = label
                textSize = 13f
                isAllCaps = false
                setTextColor(Color.WHITE)
                background = roundedDrawable(Color.parseColor(color), 8 * dp)
                setOnClickListener { onClick() }
            }
            menu.addView(btn, LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply { if (!last) bottomMargin = gap })
        }

        addBtn("Search Screen",  "#1565C0") { hideMenu(); expandCard() }
        addBtn("Ask a Question", "#1565C0") { hideMenu(); expandCard(startInChatMode = true) }
        addBtn("Emergency 1122", "#C62828") { hideMenu(); doEmergencyCall() }
        addBtn("Alert Family",   "#E65100") { hideMenu(); doAlertFamily() }
        addBtn("Close Menu",     "#37474F", last = true) { hideMenu() }

        menuView = menu
        try {
            windowManager.addView(menu, menuParams)
        } catch (e: Exception) {
            Log.e(TAG, "showMenu addView failed: ${e.message}")
        }
        Log.d(TAG, "Menu shown")
    }

    private fun hideMenu() {
        menuView?.let {
            try { windowManager.removeView(it) } catch (e: Exception) { Log.w(TAG, "hideMenu removeView: ${e.message}") }
        }
        menuView = null
        Log.d(TAG, "Menu hidden")
    }

    private fun doEmergencyCall() {
        startActivity(
            Intent(Intent.ACTION_DIAL, Uri.parse("tel:1122")).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
        )
    }

    private fun doAlertFamily() {
        val number = UserProfileStore.getEmergencyContact(this)
        if (number.isBlank()) {
            Toast.makeText(this, "Save an emergency contact number in My Profile first", Toast.LENGTH_LONG).show()
        } else {
            val callUri = Uri.parse("tel:$number")
            val hasPermission = checkSelfPermission(Manifest.permission.CALL_PHONE) ==
                    PackageManager.PERMISSION_GRANTED
            startActivity(
                Intent(if (hasPermission) Intent.ACTION_CALL else Intent.ACTION_DIAL, callUri).apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                }
            )
        }
    }

    // ── Card lifecycle ────────────────────────────────────────────────────────

    private fun expandCard(startInChatMode: Boolean = false) {
        if (expandedCard != null) {
            try { windowManager.removeView(expandedCard) } catch (e: Exception) {}
            expandedCard = null
        }
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
        expandedCardParams = cardParams

        val pad = (20 * dp).toInt()
        val card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(pad, pad, pad, pad)
            background = roundedDrawable(Color.parseColor("#003C8F"), 16 * dp)
        }

        val snapshot = ScreenContentHolder.get()
        Log.d(TAG, "expandCard: snapshot=${snapshot?.redactedText?.length} chars")
        val hasContent = snapshot != null && snapshot.redactedText.isNotBlank()
        val hasEnoughContent = snapshot != null && snapshot.redactedText.length >= 50

        // Header row: status label on the left, minimize ▼ on the right
        val headerRow = FrameLayout(this)

        val headerTv = TextView(this).apply {
            text = when {
                hasEnoughContent -> THINKING_MESSAGES[0]
                hasContent       -> "Not enough content to analyse"
                else             -> "Not ready yet"
            }
            textSize = 13f
            setTextColor(Color.parseColor("#5E92F3"))
            setPadding(0, 0, 0, (10 * dp).toInt())
        }
        cardHeaderView = headerTv

        val minimizeBtn = TextView(this).apply {
            text = "▼"
            textSize = 14f
            setTextColor(Color.parseColor("#5E92F3"))
            setPadding(0, 0, 0, (10 * dp).toInt())
            setOnClickListener { minimizeCard() }
        }

        headerRow.addView(headerTv, FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.WRAP_CONTENT,
            FrameLayout.LayoutParams.WRAP_CONTENT
        ).apply { gravity = Gravity.START or Gravity.CENTER_VERTICAL })

        headerRow.addView(minimizeBtn, FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.WRAP_CONTENT,
            FrameLayout.LayoutParams.WRAP_CONTENT
        ).apply { gravity = Gravity.END or Gravity.CENTER_VERTICAL })

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
        cardBodyScroll = bodyScroll

        // Action buttons
        val readAloudBtnView = Button(this).apply {
            text = "Read Aloud"
            textSize = 11f
            isAllCaps = false
            setTextColor(Color.WHITE)
            background = roundedDrawable(Color.parseColor("#1565C0"), 8 * dp)
        }
        readAloudBtn = readAloudBtnView

        val askBtnView = Button(this).apply {
            text = "Ask a Question"
            textSize = 11f
            isAllCaps = false
            setTextColor(Color.WHITE)
            background = roundedDrawable(Color.parseColor("#1565C0"), 8 * dp)
            setOnClickListener { enterChatMode() }
        }

        val emergencyBtnView = Button(this).apply {
            text = "Emergency"
            textSize = 11f
            isAllCaps = false
            setTextColor(Color.WHITE)
            background = roundedDrawable(Color.parseColor("#C62828"), 8 * dp)
            setOnClickListener { doEmergencyCall() }
        }

        val alertFamilyBtnView = Button(this).apply {
            text = "Alert Family"
            textSize = 11f
            isAllCaps = false
            setTextColor(Color.WHITE)
            background = roundedDrawable(Color.parseColor("#E65100"), 8 * dp)
            setOnClickListener { doAlertFamily() }
        }

        val actionRowView = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            weightSum = 4f
            visibility = View.GONE
        }
        val gap = (4 * dp).toInt()
        actionRowView.addView(readAloudBtnView,
            LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
                .apply { marginEnd = gap })
        actionRowView.addView(askBtnView,
            LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
                .apply { marginEnd = gap })
        actionRowView.addView(emergencyBtnView,
            LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
                .apply { marginEnd = gap })
        actionRowView.addView(alertFamilyBtnView,
            LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
        actionRow = actionRowView

        // Chat area (hidden until "Ask a Question" is tapped)
        val chatMsgsContainer = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(0, (8 * dp).toInt(), 0, (8 * dp).toInt())
        }
        chatMessagesContainer = chatMsgsContainer

        val maxChatHeightPx = (300 * dp).toInt()
        val chatScroll = object : ScrollView(this) {
            override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
                super.onMeasure(
                    widthMeasureSpec,
                    View.MeasureSpec.makeMeasureSpec(maxChatHeightPx, View.MeasureSpec.AT_MOST)
                )
            }
        }.apply {
            addView(chatMsgsContainer, LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ))
        }
        chatScrollView = chatScroll

        val chatInput = EditText(this).apply {
            hint = "Type your question…"
            textSize = 14f
            setTextColor(Color.WHITE)
            setHintTextColor(Color.parseColor("#90CAF9"))
            background = roundedDrawable(Color.parseColor("#1A4A8A"), 8 * dp)
            setPadding((12 * dp).toInt(), (8 * dp).toInt(), (12 * dp).toInt(), (8 * dp).toInt())
        }
        chatEditText = chatInput

        val sendBtn = Button(this).apply {
            text = "Send"
            textSize = 12f
            isAllCaps = false
            setTextColor(Color.WHITE)
            background = roundedDrawable(Color.parseColor("#1565C0"), 8 * dp)
            setOnClickListener {
                val q = chatInput.text.toString().trim()
                if (q.isNotEmpty()) {
                    chatInput.setText("")
                    appendBubble(q, isUser = true)
                    sendQuestion(q)
                }
            }
        }

        val chatInputRow = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(0, (8 * dp).toInt(), 0, 0)
            weightSum = 1f
        }
        chatInputRow.addView(chatInput,
            LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 0.75f)
                .apply { marginEnd = gap })
        chatInputRow.addView(sendBtn,
            LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 0.25f))

        val chatAreaView = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            visibility = View.GONE
        }
        chatAreaView.addView(chatScroll, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT))
        chatAreaView.addView(chatInputRow, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT))
        chatArea = chatAreaView

        val closeBtn = Button(this).apply {
            text = "Close"
            setTextColor(Color.WHITE)
            background = roundedDrawable(Color.parseColor("#1565C0"), 10 * dp)
            setOnClickListener { collapseCard() }
        }

        card.addView(headerRow, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        ))
        card.addView(bodyScroll)
        card.addView(chatAreaView, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        ))
        card.addView(actionRowView, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        ).apply { bottomMargin = (8 * dp).toInt() })
        card.addView(closeBtn)

        var cardInitX = 0; var cardInitY = 0
        var cardTouchX = 0f; var cardTouchY = 0f
        card.setOnTouchListener { v, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    cardInitX = cardParams.x; cardInitY = cardParams.y
                    cardTouchX = event.rawX; cardTouchY = event.rawY
                    true
                }
                MotionEvent.ACTION_MOVE -> {
                    cardParams.x = cardInitX + (event.rawX - cardTouchX).toInt()
                    cardParams.y = cardInitY + (event.rawY - cardTouchY).toInt()
                    windowManager.updateViewLayout(v, cardParams)
                    true
                }
                MotionEvent.ACTION_UP -> true
                else -> false
            }
        }

        expandedCard = card
        try {
            windowManager.addView(card, cardParams)
        } catch (e: Exception) {
            Log.e(TAG, "addView failed: ${e.message}")
        }
        Log.d(TAG, "Overlay card expanded")

        if (startInChatMode) {
            enterChatMode()
        } else {
            val saved = savedResponse
            if (saved != null) {
                savedResponse = null
                currentAiResponse = saved.bodyText
                cardHeaderView?.text = saved.headerText
                cardBodyView?.text = saved.bodyText
                readAloudBtn?.setOnClickListener {
                    if (ttsReady) tts?.speak(saved.bodyText, TextToSpeech.QUEUE_FLUSH, null, "eb_tts")
                }
                actionRow?.visibility = View.VISIBLE
            } else if (hasEnoughContent) {
                startAnalysis(snapshot!!)
            }
        }
    }

    private fun collapseCard() {
        // Cancel any in-flight API call so a late response can't touch removed views
        analyzeJob?.cancel()
        analyzeJob = null
        savedResponse = null
        stopBubblePulse()
        tts?.stop()
        isChatMode = false
        currentAiResponse = ""
        cardHeaderView = null
        cardBodyView = null
        cardBodyScroll = null
        actionRow = null
        readAloudBtn = null
        chatArea = null
        chatScrollView = null
        chatMessagesContainer = null
        chatEditText = null
        expandedCard?.let {
            try { windowManager.removeView(it) } catch (e: Exception) { Log.w(TAG, "removeView card: ${e.message}") }
        }
        expandedCard = null
        expandedCardParams = null
        Log.d(TAG, "Overlay card collapsed")
    }

    // Hides the card but lets any in-flight analysis complete and save to history.
    // The bubble continues pulsing while the job is active.
    private fun minimizeCard() {
        tts?.stop()
        isChatMode = false
        currentAiResponse = ""
        cardHeaderView = null
        cardBodyView = null
        cardBodyScroll = null
        actionRow = null
        readAloudBtn = null
        chatArea = null
        chatScrollView = null
        chatMessagesContainer = null
        chatEditText = null
        expandedCard?.let {
            try { windowManager.removeView(it) } catch (e: Exception) { Log.w(TAG, "removeView card: ${e.message}") }
        }
        expandedCard = null
        expandedCardParams = null
        Log.d(TAG, "Overlay card minimized")
    }

    // ── API call ──────────────────────────────────────────────────────────────

    private fun startAnalysis(snapshot: ScreenContentHolder.ScreenSnapshot) {
        analyzeJob?.cancel()
        analyzeJob = serviceScope.launch {
            startBubblePulse()
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
                val event = IncomingEvent(
                    eventType = "FORM_SCREEN",
                    sourceApp = snapshot.sourcePackage,
                    redactedText = snapshot.redactedText,
                    timestamp = java.time.Instant.now().toString(),
                    userId = PLACEHOLDER_USER_ID
                )

                val decision: FinalDecision = withContext(Dispatchers.IO) {
                    ApiClient.api.analyzeEvent(event)
                }
                Log.d(TAG, "analyzeEvent raw response: ${com.google.gson.Gson().toJson(decision)}")

                if (isActive) {
                    Handler(Looper.getMainLooper()).post {
                        showResponse(decision)
                    }
                    HistoryStore.addEntry(
                        screenText = snapshot.redactedText,
                        response = decision.responseText,
                        riskLevel = decision.riskFlag ?: "none"
                    )
                }

            } catch (e: CancellationException) {
                throw e // always rethrow so coroutine framework cancels cleanly
            } catch (e: Exception) {
                Log.w(TAG, "analyzeEvent failed (${e.javaClass.simpleName}): ${e.message}")
                if (isActive) Handler(Looper.getMainLooper()).post { showError(e) }
            } finally {
                rotationJob.cancel()
                stopBubblePulse()
            }
        }
    }

    // Both run on Dispatchers.Main (the scope default), so direct View mutation is safe

    private fun showResponse(decision: FinalDecision) {
        currentAiResponse = decision.responseText
        savedResponse = SavedResponse(
            headerText = "ElderBridge says:",
            bodyText = decision.responseText,
            riskFlag = decision.riskFlag ?: "none"
        )
        cardHeaderView?.text = "ElderBridge says:"
        cardBodyView?.text = decision.responseText
        readAloudBtn?.setOnClickListener {
            if (ttsReady) tts?.speak(decision.responseText, TextToSpeech.QUEUE_FLUSH, null, "eb_tts")
        }
        actionRow?.visibility = View.VISIBLE
    }

    private fun showError(e: Exception) {
        cardHeaderView?.text = "Connection issue"
        cardBodyView?.text = e.message ?: "Request failed"
    }

    // ── Chat mode ─────────────────────────────────────────────────────────────

    private fun enterChatMode() {
        isChatMode = true
        cardBodyScroll?.visibility = View.GONE
        actionRow?.visibility = View.GONE
        chatArea?.visibility = View.VISIBLE

        // Allow the soft keyboard to focus the EditText
        expandedCard?.let { card ->
            val params = expandedCardParams ?: return@let
            params.flags = params.flags and WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE.inv()
            windowManager.updateViewLayout(card, params)
        }

        chatMessagesContainer?.removeAllViews()
        if (currentAiResponse.isNotEmpty()) {
            appendBubble(currentAiResponse, isUser = false)
        }

        chatEditText?.requestFocus()
        cardHeaderView?.text = "Chat with ElderBridge"
    }

    private fun appendBubble(text: String, isUser: Boolean) {
        val dp = resources.displayMetrics.density
        val container = chatMessagesContainer ?: return

        val bubble = TextView(this).apply {
            this.text = text
            textSize = 14f
            setTextColor(Color.WHITE)
            background = roundedDrawable(
                if (isUser) Color.parseColor("#37474F") else Color.parseColor("#1565C0"),
                10 * dp
            )
            val hPad = (12 * dp).toInt()
            val vPad = (8 * dp).toInt()
            setPadding(hPad, vPad, hPad, vPad)
        }

        val lp = LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.WRAP_CONTENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        ).apply {
            bottomMargin = (6 * dp).toInt()
            gravity = if (isUser) Gravity.END else Gravity.START
            if (isUser) marginStart = (40 * dp).toInt()
            else marginEnd = (40 * dp).toInt()
        }

        container.addView(bubble, lp)
        chatScrollView?.post { chatScrollView?.fullScroll(View.FOCUS_DOWN) }
    }

    private fun sendQuestion(question: String) {
        val snapshot = ScreenContentHolder.get()
        val screenText = snapshot?.redactedText.orEmpty()
        val combined = if (screenText.isNotBlank()) "$screenText\n\nUser question: $question" else question
        analyzeJob?.cancel()
        analyzeJob = serviceScope.launch {
            val dp = resources.displayMetrics.density
            val thinkingBubble = TextView(this@OverlayService).apply {
                text = CHAT_THINKING_MESSAGES[0]
                textSize = 14f
                setTextColor(Color.parseColor("#90CAF9"))
                setPadding((12 * dp).toInt(), (8 * dp).toInt(), (12 * dp).toInt(), (8 * dp).toInt())
            }
            val thinkingLp = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply {
                bottomMargin = (6 * dp).toInt()
                gravity = Gravity.START
            }
            chatMessagesContainer?.addView(thinkingBubble, thinkingLp)
            chatScrollView?.post { chatScrollView?.fullScroll(View.FOCUS_DOWN) }

            // Rotate through friendly placeholder messages every 2 s while waiting
            val thinkingRotateJob = launch {
                var idx = 1
                while (isActive) {
                    delay(2_000)
                    thinkingBubble.text = CHAT_THINKING_MESSAGES[idx % CHAT_THINKING_MESSAGES.size]
                    idx++
                }
            }

            try {
                val event = IncomingEvent(
                    eventType = "FORM_SCREEN",
                    sourceApp = snapshot?.sourcePackage ?: "unknown",
                    redactedText = combined,
                    timestamp = java.time.Instant.now().toString(),
                    userId = PLACEHOLDER_USER_ID
                )
                val decision: FinalDecision = withContext(Dispatchers.IO) {
                    ApiClient.api.analyzeEvent(event)
                }
                Log.d(TAG, "sendQuestion response: ${com.google.gson.Gson().toJson(decision)}")
                if (isActive) {
                    Handler(Looper.getMainLooper()).post {
                        chatMessagesContainer?.removeView(thinkingBubble)
                        appendBubble(decision.responseText, isUser = false)
                    }
                    HistoryStore.addEntry(
                        screenText = combined,
                        response = decision.responseText,
                        riskLevel = decision.riskFlag ?: "none"
                    )
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                Log.w(TAG, "sendQuestion failed (${e.javaClass.simpleName}): ${e.message}")
                if (isActive) {
                    Handler(Looper.getMainLooper()).post {
                        chatMessagesContainer?.removeView(thinkingBubble)
                        appendBubble("Error: ${e.message ?: "Request failed"}", isUser = false)
                    }
                }
            } finally {
                thinkingRotateJob.cancel()
            }
        }
    }

    // ── Bubble pulse animation ─────────────────────────────────────────────────

    private fun startBubblePulse() {
        val label = bubbleLabel ?: return
        bubblePulseAnim?.cancel()
        bubblePulseAnim = ObjectAnimator.ofFloat(label, "alpha", 1f, 0.3f, 1f).apply {
            duration = 1200
            repeatCount = ObjectAnimator.INFINITE
            start()
        }
    }

    private fun stopBubblePulse() {
        bubblePulseAnim?.cancel()
        bubblePulseAnim = null
        bubbleLabel?.alpha = 1f
    }

    // ── Lifecycle ─────────────────────────────────────────────────────────────

    override fun onDestroy() {
        super.onDestroy()
        serviceScope.cancel()       // cancels analyzeJob and all child coroutines
        stopBubblePulse()
        tts?.stop()
        tts?.shutdown()
        tts = null
        hideMenu()
        bubbleView?.let {
            try { windowManager.removeView(it) } catch (e: Exception) { Log.w(TAG, "removeView bubble: ${e.message}") }
        }
        bubbleView = null
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

        private val CHAT_THINKING_MESSAGES = listOf(
            "Thinking about your question...",
            "Looking into this for you...",
            "One moment..."
        )
    }
}
