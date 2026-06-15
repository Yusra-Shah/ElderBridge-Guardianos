package com.elderbridge.guardianos.services

import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log
import com.elderbridge.guardianos.redaction.RedactionEngine

class NotificationListener : NotificationListenerService() {

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        val packageName = sbn.packageName
        val extras = sbn.notification?.extras ?: return

        val title = extras.getString("android.title").orEmpty()
        val text = extras.getCharSequence("android.text")?.toString().orEmpty()

        // Redact on-device before any logging — OTPs and phone numbers must never appear in logs
        val redactedTitle = RedactionEngine.redact(title)
        val redactedText = RedactionEngine.redact(text)

        Log.d(TAG, "Notification from: $packageName")
        Log.d(TAG, "  title (redacted): $redactedTitle")
        Log.d(TAG, "  text  (redacted): $redactedText")

        // No backend forwarding in this milestone — all processing stays on-device
    }

    override fun onNotificationRemoved(sbn: StatusBarNotification) {
        Log.d(TAG, "Notification removed from: ${sbn.packageName}")
    }

    companion object {
        private const val TAG = "NotificationListener"
    }
}
