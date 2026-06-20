package com.elderbridge.guardianos.services

import android.accessibilityservice.AccessibilityService
import android.content.Intent
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import com.elderbridge.guardianos.redaction.RedactionEngine
import com.elderbridge.guardianos.redaction.ScreenContentHolder

class ScreenReaderService : AccessibilityService() {

    private val handler = Handler(Looper.getMainLooper())

    // Debounce rapid content-change events (e.g. per-keystroke updates) so we only
    // walk the node tree after 350 ms of inactivity on the current window.
    private val captureRunnable = Runnable { captureScreenContent() }

    override fun onAccessibilityEvent(event: AccessibilityEvent) {
        when (event.eventType) {
            AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED,
            AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED -> {
                handler.removeCallbacks(captureRunnable)
                handler.postDelayed(captureRunnable, DEBOUNCE_MS)
            }
            else -> {}
        }
    }

    override fun onInterrupt() {
        handler.removeCallbacks(captureRunnable)
    }

    override fun onUnbind(intent: Intent?): Boolean {
        handler.removeCallbacks(captureRunnable)
        ScreenContentHolder.clear()
        Log.d(TAG, "ScreenReaderService unbound — ScreenContentHolder cleared")
        return super.onUnbind(intent)
    }

    private fun captureScreenContent() {
        val root = rootInActiveWindow ?: return
        try {
            val sourcePkg = root.packageName?.toString() ?: ""

            if (sourcePkg in BLOCKED_PACKAGES) return

            val rawText = extractText(root)
            if (rawText.isBlank()) return

            // SECURITY: RedactionEngine.redact() is called here, on the raw extracted text,
            // before it touches ScreenContentHolder or any log statement.
            // Per SECURITY_MODEL.md: OTPs, phone numbers, and email addresses must never
            // leave this call site in plaintext. rawText is a local variable and is
            // never passed to any logger or storage before this line.
            val redacted = RedactionEngine.redact(rawText)

            ScreenContentHolder.update(redacted, sourcePkg)

            // Log only metadata — never content, even after redaction
            Log.d(TAG, "Captured screen from $sourcePkg: ${redacted.length} chars (redacted)")
        } finally {
            @Suppress("DEPRECATION")
            root.recycle()
        }
    }

    /**
     * Recursively walk the AccessibilityNodeInfo tree and collect visible text.
     *
     * Includes .text, .hintText, and .contentDescription from each visible node.
     * Stops descending beyond [MAX_DEPTH] levels and stops collecting after [MAX_CHARS]
     * characters to bound memory and CPU on complex screens.
     *
     * Every node obtained via getChild() is recycled in a finally block to avoid
     * leaking the node pool on API 26–32.
     */
    private fun extractText(root: AccessibilityNodeInfo): String {
        val sb = StringBuilder()
        walkNode(root, sb, depth = 0)
        return sb.toString().trim()
    }

    private fun walkNode(node: AccessibilityNodeInfo, sb: StringBuilder, depth: Int) {
        if ((depth > MAX_DEPTH) || (sb.length > MAX_CHARS)) return
        if (!node.isVisibleToUser) return

        node.text?.toString()?.takeIf { it.isNotBlank() }?.let {
            sb.append(it).append(' ')
        }
        node.hintText?.toString()?.takeIf { it.isNotBlank() }?.let {
            sb.append(it).append(' ')
        }
        // contentDescription is used by accessibility labels on icon buttons, images, etc.
        node.contentDescription?.toString()?.takeIf { it.isNotBlank() }?.let {
            sb.append(it).append(' ')
        }

        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            try {
                walkNode(child, sb, depth + 1)
            } finally {
                @Suppress("DEPRECATION")
                child.recycle()
            }
        }
    }

    companion object {
        private const val TAG = "ScreenReaderService"
        private const val DEBOUNCE_MS = 350L
        private const val MAX_DEPTH = 30
        private const val MAX_CHARS = 4_000

        val BLOCKED_PACKAGES = setOf(
            "com.android.settings",
            "com.android.systemui",
            "com.coloros.wirelesssettings",
            "com.oppo.launcher",
            "com.elderbridge.guardianos"
        )
    }
}
