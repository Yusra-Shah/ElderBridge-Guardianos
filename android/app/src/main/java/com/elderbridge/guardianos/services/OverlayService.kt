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
import android.content.res.Configuration
import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.LayerDrawable
import android.net.Uri
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
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.EditText
import android.widget.ScrollView
import android.speech.tts.TextToSpeech
import android.widget.TextView
import androidx.core.content.res.ResourcesCompat
import com.elderbridge.guardianos.R
import com.elderbridge.guardianos.data.HistoryStore
import com.elderbridge.guardianos.data.UserProfileStore
import com.elderbridge.guardianos.network.ApiClient
import com.elderbridge.guardianos.network.ChatMessage
import com.elderbridge.guardianos.network.ChatRequest
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

    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private var analyzeJob: Job? = null

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

    private var chatArea: LinearLayout? = null
    private var chatScrollView: ScrollView? = null
    private var chatMessagesContainer: LinearLayout? = null
    private var chatEditText: EditText? = null
    private var isChatMode = false
    private var currentAiResponse: String = ""

    private val chatHistory = mutableListOf<ChatMessage>()
    private var chatFirstTurnSent = false

    private var tts: TextToSpeech? = null
    private var ttsReady = false

    // ── Overlay palette ──────────────────────────────────────────────────────

    private data class Palette(
        val ground: Int,
        val surface: Int,
        val surfaceAlt: Int,
        val ink: Int,
        val inkSoft: Int,
        val sage: Int,
        val clay: Int,
        val ochre: Int,
        val navy: Int,
        val line: Int,
        val clayStrong: Int,
    )

    private val lightPalette = Palette(
        ground = Color.parseColor("#F3EDE3"),
        surface = Color.parseColor("#FBF7F0"),
        surfaceAlt = Color.parseColor("#ECE3D6"),
        ink = Color.parseColor("#3A352F"),
        inkSoft = Color.parseColor("#6F665B"),
        sage = Color.parseColor("#7C8A6B"),
        clay = Color.parseColor("#C2724B"),
        ochre = Color.parseColor("#D8A24A"),
        navy = Color.parseColor("#3F4A63"),
        line = Color.parseColor("#E0D6C8"),
        clayStrong = Color.parseColor("#B5532C"),
    )

    private val darkPalette = Palette(
        ground = Color.parseColor("#211E1A"),
        surface = Color.parseColor("#2B2722"),
        surfaceAlt = Color.parseColor("#35302A"),
        ink = Color.parseColor("#F0E9DD"),
        inkSoft = Color.parseColor("#B7AC9D"),
        sage = Color.parseColor("#9DB082"),
        clay = Color.parseColor("#D98C63"),
        ochre = Color.parseColor("#E6B65F"),
        navy = Color.parseColor("#8593B3"),
        line = Color.parseColor("#413A32"),
        clayStrong = Color.parseColor("#D98C63"),
    )

    private fun palette(): Palette {
        return if (UserProfileStore.isDarkModeEnabled(this)) darkPalette else lightPalette
    }

    private fun nunitoTypeface(): Typeface {
        return try {
            ResourcesCompat.getFont(this, R.font.nunito_semibold) ?: Typeface.DEFAULT
        } catch (e: Exception) {
            Typeface.DEFAULT
        }
    }

    private fun nunitoRegularTypeface(): Typeface {
        return try {
            ResourcesCompat.getFont(this, R.font.nunito_regular) ?: Typeface.DEFAULT
        } catch (e: Exception) {
            Typeface.DEFAULT
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        windowManager = getSystemService(WINDOW_SERVICE) as WindowManager
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startAsForeground()
        if (bubbleView == null) {
            tts = TextToSpeech(this) { status ->
                ttsReady = (status == TextToSpeech.SUCCESS)
                if (ttsReady) tts?.language = Locale.getDefault()
            }
            addBubble()
        }
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
        val p = palette()
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

        // Soft sage ring + surface fill
        val ring = circleDrawable(p.sage)
        val inner = circleDrawable(p.surface)
        val layered = LayerDrawable(arrayOf(ring, inner))
        val inset = (3 * dp).toInt()
        layered.setLayerInset(1, inset, inset, inset, inset)
        frame.background = layered

        // Bridge mark icon in centre
        val markView = ImageView(this).apply {
            setImageResource(R.drawable.ic_elderbridge_mark)
            contentDescription = "ElderBridge assistant, double tap to open"
        }
        frame.addView(markView, FrameLayout.LayoutParams(
            (36 * dp).toInt(),
            (36 * dp).toInt()
        ).apply { gravity = Gravity.CENTER })

        // Hidden text label kept for pulse animation compatibility
        val label = TextView(this).apply {
            text = ""
            visibility = View.GONE
        }
        bubbleLabel = label
        frame.addView(label, FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.MATCH_PARENT
        ))

        // Close button as a separate tappable child
        val xBtn = TextView(this).apply {
            text = "x"
            textSize = 10f
            setTextColor(p.surface)
            gravity = Gravity.CENTER
            background = circleDrawable(p.clayStrong)
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
        val p = palette()
        val bx = bubbleParams?.x ?: 0
        val by = bubbleParams?.y ?: 200
        val tf = nunitoTypeface()

        val menuParams = WindowManager.LayoutParams(
            (180 * dp).toInt(),
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = bx + (70 * dp).toInt()
            y = by
        }

        val pad = (12 * dp).toInt()
        val gap = (8 * dp).toInt()
        val menu = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(pad, pad, pad, pad)
            background = roundedDrawable(p.surface, 24 * dp)
            elevation = 8 * dp
        }

        fun addMenuBtn(label: String, color: Int, last: Boolean = false, onClick: () -> Unit) {
            val btn = Button(this).apply {
                text = label
                textSize = 14f
                isAllCaps = false
                typeface = tf
                setTextColor(p.surface)
                background = roundedDrawable(color, 16 * dp)
                minimumHeight = (56 * dp).toInt()
                setOnClickListener { onClick() }
            }
            menu.addView(btn, LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply { if (!last) bottomMargin = gap })
        }

        addMenuBtn("Search Screen", p.sage) { hideMenu(); expandCard() }
        addMenuBtn("Ask a Question", p.navy) { hideMenu(); expandCard(startInChatMode = true) }
        addMenuBtn("Emergency 1122", p.clayStrong) { hideMenu(); doEmergencyCall() }
        addMenuBtn("Alert Family", p.ochre) { hideMenu(); doAlertFamily() }
        addMenuBtn("Close Menu", p.inkSoft, last = true) { hideMenu() }

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
        val p = palette()
        val tf = nunitoTypeface()
        val tfBody = nunitoRegularTypeface()

        val cardParams = WindowManager.LayoutParams(
            (320 * dp).toInt(),
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = (12 * dp).toInt()
            y = (200 * dp).toInt()
        }
        expandedCardParams = cardParams

        val pad = (20 * dp).toInt()
        val card = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(pad, pad, pad, pad)
            background = roundedDrawable(p.surface, 28 * dp)
            elevation = 12 * dp
        }

        val snapshot = ScreenContentHolder.get()
        Log.d(TAG, "expandCard: snapshot=${snapshot?.redactedText?.length} chars")
        val hasContent = snapshot != null && snapshot.redactedText.isNotBlank()
        val hasEnoughContent = snapshot != null && snapshot.redactedText.length >= 50

        // Grab handle
        val handle = View(this).apply {
            background = roundedDrawable(p.line, 3 * dp)
        }
        card.addView(handle, LinearLayout.LayoutParams(
            (40 * dp).toInt(), (4 * dp).toInt()
        ).apply {
            gravity = Gravity.CENTER_HORIZONTAL
            bottomMargin = (12 * dp).toInt()
        })

        // Header row
        val headerRow = FrameLayout(this)

        val headerTv = TextView(this).apply {
            text = when {
                hasEnoughContent -> THINKING_MESSAGES[0]
                hasContent       -> "Not enough content to analyse"
                else             -> "Not ready yet"
            }
            textSize = 14f
            typeface = tf
            setTextColor(p.inkSoft)
            setPadding(0, 0, 0, (10 * dp).toInt())
        }
        cardHeaderView = headerTv

        val minimizeBtn = TextView(this).apply {
            text = "v"
            textSize = 16f
            typeface = tf
            setTextColor(p.inkSoft)
            setPadding(0, 0, 0, (10 * dp).toInt())
            minimumWidth = (56 * dp).toInt()
            minimumHeight = (56 * dp).toInt()
            gravity = Gravity.CENTER
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

        // Body text
        val bodyTv = TextView(this).apply {
            text = if (hasContent) "" else "Open a form or message, then tap me again."
            textSize = 18f
            typeface = tfBody
            setTextColor(p.ink)
            setPadding(0, 0, 0, (20 * dp).toInt())
            setLineSpacing(0f, 1.6f)
        }
        cardBodyView = bodyTv

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

        // Action buttons with spec colours
        val btnRadius = 16 * dp
        val btnHeight = (48 * dp).toInt()

        val readAloudBtnView = Button(this).apply {
            text = "Read Aloud"
            textSize = 14f
            isAllCaps = false
            typeface = tf
            setTextColor(p.surface)
            background = roundedDrawable(p.sage, btnRadius)
            minimumHeight = btnHeight
        }
        readAloudBtn = readAloudBtnView

        val askBtnView = Button(this).apply {
            text = "Ask a Question"
            textSize = 14f
            isAllCaps = false
            typeface = tf
            setTextColor(p.surface)
            background = roundedDrawable(p.navy, btnRadius)
            minimumHeight = btnHeight
            setOnClickListener { enterChatMode() }
        }

        val emergencyBtnView = Button(this).apply {
            text = "Emergency"
            textSize = 14f
            isAllCaps = false
            typeface = tf
            setTextColor(p.surface)
            background = roundedDrawable(p.clayStrong, btnRadius)
            minimumHeight = btnHeight
            setOnClickListener { doEmergencyCall() }
        }

        val alertFamilyBtnView = Button(this).apply {
            text = "Alert Family"
            textSize = 14f
            isAllCaps = false
            typeface = tf
            setTextColor(p.surface)
            background = roundedDrawable(p.ochre, btnRadius)
            minimumHeight = btnHeight
            setOnClickListener { doAlertFamily() }
        }

        val actionRowView = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            weightSum = 4f
            visibility = View.GONE
        }
        val gap = (6 * dp).toInt()
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

        // Chat area (hidden until "Ask a Question")
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
            hint = "Type your question..."
            textSize = 16f
            typeface = tfBody
            setTextColor(p.ink)
            setHintTextColor(p.inkSoft)
            background = roundedDrawable(p.surfaceAlt, 14 * dp)
            setPadding((12 * dp).toInt(), (10 * dp).toInt(), (12 * dp).toInt(), (10 * dp).toInt())
        }
        chatEditText = chatInput

        val sendBtn = Button(this).apply {
            text = "Send"
            textSize = 14f
            isAllCaps = false
            typeface = tf
            setTextColor(p.surface)
            background = roundedDrawable(p.navy, 14 * dp)
            minimumHeight = (48 * dp).toInt()
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
            textSize = 16f
            isAllCaps = false
            typeface = tf
            setTextColor(p.inkSoft)
            background = roundedDrawable(p.surfaceAlt, 16 * dp)
            minimumHeight = (56 * dp).toInt()
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
        card.addView(closeBtn, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        ))

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
        analyzeJob?.cancel()
        analyzeJob = null
        savedResponse = null
        stopBubblePulse()
        tts?.stop()
        isChatMode = false
        currentAiResponse = ""
        chatHistory.clear()
        chatFirstTurnSent = false
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

    private fun minimizeCard() {
        tts?.stop()
        isChatMode = false
        currentAiResponse = ""
        chatHistory.clear()
        chatFirstTurnSent = false
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
                throw e
            } catch (e: Exception) {
                Log.w(TAG, "analyzeEvent failed (${e.javaClass.simpleName}): ${e.message}")
                if (isActive) Handler(Looper.getMainLooper()).post { showError(e) }
            } finally {
                rotationJob.cancel()
                stopBubblePulse()
            }
        }
    }

    private fun showResponse(decision: FinalDecision) {
        currentAiResponse = decision.responseText
        val riskFlag = decision.riskFlag ?: "none"
        savedResponse = SavedResponse(
            headerText = riskHeaderText(riskFlag),
            bodyText = decision.responseText,
            riskFlag = riskFlag
        )
        cardHeaderView?.text = riskHeaderText(riskFlag)
        cardBodyView?.text = decision.responseText
        readAloudBtn?.setOnClickListener {
            if (ttsReady) tts?.speak(decision.responseText, TextToSpeech.QUEUE_FLUSH, null, "eb_tts")
        }
        actionRow?.visibility = View.VISIBLE
    }

    private fun riskHeaderText(riskFlag: String): String {
        return when (riskFlag.lowercase()) {
            "stop_and_verify", "verify_first" -> "ElderBridge says: Stop and check"
            "caution", "soft_help" -> "ElderBridge says: Take a moment"
            else -> "ElderBridge says: Looks fine"
        }
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
        val p = palette()
        val container = chatMessagesContainer ?: return

        val bubble = TextView(this).apply {
            this.text = text
            textSize = 16f
            typeface = nunitoRegularTypeface()
            setTextColor(p.ink)
            background = roundedDrawable(
                if (isUser) p.surfaceAlt else alphaBlend(p.sage, p.surface, 0.15f),
                16 * dp
            )
            val hPad = (14 * dp).toInt()
            val vPad = (10 * dp).toInt()
            setPadding(hPad, vPad, hPad, vPad)
        }

        val lp = LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.WRAP_CONTENT,
            LinearLayout.LayoutParams.WRAP_CONTENT
        ).apply {
            bottomMargin = (8 * dp).toInt()
            gravity = if (isUser) Gravity.END else Gravity.START
            if (isUser) marginStart = (40 * dp).toInt()
            else marginEnd = (40 * dp).toInt()
        }

        container.addView(bubble, lp)
        chatScrollView?.post { chatScrollView?.fullScroll(View.FOCUS_DOWN) }
    }

    private fun sendQuestion(question: String) {
        val snapshot = ScreenContentHolder.get()
        val screenContext = if (!chatFirstTurnSent) {
            chatFirstTurnSent = true
            snapshot?.redactedText.orEmpty()
        } else {
            ""
        }

        chatHistory.add(ChatMessage(role = "user", content = question))

        analyzeJob?.cancel()
        analyzeJob = serviceScope.launch {
            val dp = resources.displayMetrics.density
            val p = palette()
            val thinkingBubble = TextView(this@OverlayService).apply {
                text = "..."
                textSize = 16f
                typeface = nunitoRegularTypeface()
                setTextColor(p.sage)
                setPadding((14 * dp).toInt(), (10 * dp).toInt(), (14 * dp).toInt(), (10 * dp).toInt())
            }
            val thinkingLp = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply {
                bottomMargin = (8 * dp).toInt()
                gravity = Gravity.START
            }
            chatMessagesContainer?.addView(thinkingBubble, thinkingLp)
            chatScrollView?.post { chatScrollView?.fullScroll(View.FOCUS_DOWN) }

            val thinkingRotateJob = launch {
                var idx = 0
                while (isActive) {
                    delay(600)
                    val dots = when (idx % 3) { 0 -> "."; 1 -> ".."; else -> "..." }
                    thinkingBubble.text = dots
                    idx++
                }
            }

            try {
                val chatRequest = ChatRequest(
                    userId = PLACEHOLDER_USER_ID,
                    messages = chatHistory.toList(),
                    screenContext = screenContext
                )
                val decision: FinalDecision = withContext(Dispatchers.IO) {
                    ApiClient.api.askQuestion(chatRequest)
                }
                Log.d(TAG, "askQuestion response: ${com.google.gson.Gson().toJson(decision)}")

                chatHistory.add(ChatMessage(role = "assistant", content = decision.responseText))

                if (isActive) {
                    Handler(Looper.getMainLooper()).post {
                        chatMessagesContainer?.removeView(thinkingBubble)
                        appendBubble(decision.responseText, isUser = false)
                    }
                    HistoryStore.addEntry(
                        screenText = question,
                        response = decision.responseText,
                        riskLevel = decision.riskFlag ?: "none"
                    )
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                Log.w(TAG, "askQuestion failed (${e.javaClass.simpleName}): ${e.message}")
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
        val view = bubbleView ?: return
        bubblePulseAnim?.cancel()
        bubblePulseAnim = ObjectAnimator.ofFloat(view, "scaleX", 1f, 1.04f, 1f).apply {
            duration = 2400
            repeatCount = ObjectAnimator.INFINITE
            start()
        }
        ObjectAnimator.ofFloat(view, "scaleY", 1f, 1.04f, 1f).apply {
            duration = 2400
            repeatCount = ObjectAnimator.INFINITE
            start()
        }
    }

    private fun stopBubblePulse() {
        bubblePulseAnim?.cancel()
        bubblePulseAnim = null
        bubbleView?.scaleX = 1f
        bubbleView?.scaleY = 1f
    }

    // ── Lifecycle ─────────────────────────────────────────────────────────────

    override fun onDestroy() {
        super.onDestroy()
        serviceScope.cancel()
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

    private fun alphaBlend(fg: Int, bg: Int, ratio: Float): Int {
        val r = (Color.red(fg) * ratio + Color.red(bg) * (1 - ratio)).toInt()
        val g = (Color.green(fg) * ratio + Color.green(bg) * (1 - ratio)).toInt()
        val b = (Color.blue(fg) * ratio + Color.blue(bg) * (1 - ratio)).toInt()
        return Color.rgb(r, g, b)
    }

    companion object {
        private const val TAG = "OverlayService"

        private const val PLACEHOLDER_USER_ID = "00000000-0000-0000-0000-000000000001"

        private val THINKING_MESSAGES = listOf(
            "Checking official sources...",
            "Analysing your screen...",
            "Preparing your explanation..."
        )
    }
}
