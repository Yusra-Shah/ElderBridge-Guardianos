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
import android.widget.TextView

class OverlayService : Service() {

    private lateinit var windowManager: WindowManager
    private var bubbleView: View? = null
    private var expandedCard: View? = null
    private var isBubbleExpanded = false

    // Hardcoded mock response — real AI response will replace this in a later milestone
    private val mockResponse =
        "This form is asking for your monthly income from Social Security or any pension. " +
        "Enter the total amount you receive each month before any deductions."

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        windowManager = getSystemService(WINDOW_SERVICE) as WindowManager
        addBubble()
    }

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

        card.addView(TextView(this).apply {
            text = "ElderBridge says:"
            textSize = 13f
            setTextColor(Color.parseColor("#5E92F3"))
            setPadding(0, 0, 0, (10 * dp).toInt())
        })
        card.addView(TextView(this).apply {
            text = mockResponse
            textSize = 17f
            setTextColor(Color.WHITE)
            setPadding(0, 0, 0, (20 * dp).toInt())
            lineSpacingMultiplier = 1.4f
        })
        card.addView(Button(this).apply {
            text = "Close"
            setTextColor(Color.WHITE)
            background = roundedDrawable(Color.parseColor("#1565C0"), 10 * dp)
            setOnClickListener { collapseCard(); isBubbleExpanded = false }
        })

        expandedCard = card
        windowManager.addView(card, cardParams)
        Log.d(TAG, "Overlay card expanded")
    }

    private fun collapseCard() {
        expandedCard?.let { windowManager.removeView(it) }
        expandedCard = null
        Log.d(TAG, "Overlay card collapsed")
    }

    override fun onDestroy() {
        super.onDestroy()
        bubbleView?.let { windowManager.removeView(it) }
        collapseCard()
        Log.d(TAG, "OverlayService destroyed")
    }

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
    }
}
