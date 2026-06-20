package com.elderbridge.guardianos.ui.viewmodel

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.lifecycle.ViewModel
import com.elderbridge.guardianos.ui.state.PermissionActionType
import com.elderbridge.guardianos.ui.state.PermissionItemUiModel
import com.elderbridge.guardianos.ui.state.PermissionsUiState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

class PermissionsViewModel : ViewModel() {

    private val _uiState = MutableStateFlow(PermissionsUiState())
    val uiState: StateFlow<PermissionsUiState> = _uiState.asStateFlow()

    fun checkPermissions(context: Context) {
        val hasAccessibility = isAccessibilityEnabled(context)
        val hasNotification = isNotificationAccessEnabled(context)
        val hasOverlay = Settings.canDrawOverlays(context)

        val items = listOf(
            PermissionItemUiModel(
                title = "Accessibility Service",
                description = "Lets us see what is on your screen so we can explain it to you.",
                isGranted = hasAccessibility,
                actionType = PermissionActionType.ACCESSIBILITY
            ),
            PermissionItemUiModel(
                title = "Notification Access",
                description = "Lets us explain notifications from health and government apps.",
                isGranted = hasNotification,
                actionType = PermissionActionType.NOTIFICATION
            ),
            PermissionItemUiModel(
                title = "Display Over Apps",
                description = "Lets us show a small helper bubble while you use other apps.",
                isGranted = hasOverlay,
                actionType = PermissionActionType.OVERLAY
            )
        )

        val completed = listOf(hasAccessibility, hasNotification, hasOverlay).count { it }
        
        _uiState.update {
            it.copy(
                accessibilityGranted = hasAccessibility,
                notificationGranted = hasNotification,
                overlayGranted = hasOverlay,
                allGranted = completed == 3,
                progress = completed.toFloat() / 3f,
                completedSteps = completed,
                permissionItems = items
            )
        }
    }

    fun openAccessibilitySettings(context: Context) {
        context.startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
    }

    fun openNotificationSettings(context: Context) {
        context.startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
    }

    fun openOverlaySettings(context: Context) {
        val intent = Intent(
            Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
            Uri.parse("package:${context.packageName}")
        )
        context.startActivity(intent)
    }

    /**
     * Re-check system settings (manual refresh or onResume)
     */
    fun refreshStatus(context: Context) {
        checkPermissions(context)
    }

    private fun isAccessibilityEnabled(context: Context): Boolean {
        val enabled = Settings.Secure.getString(
            context.contentResolver,
            Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
        ) ?: return false
        return enabled.split(':').any { entry ->
            val parts = entry.trim().split('/')
            parts.size == 2 &&
                parts[0].equals(context.packageName, ignoreCase = true) &&
                parts[1].contains("ScreenReaderService", ignoreCase = true)
        }
    }

    private fun isNotificationAccessEnabled(context: Context): Boolean {
        val enabled = Settings.Secure.getString(
            context.contentResolver,
            "enabled_notification_listeners"
        ) ?: return false
        return enabled.contains(context.packageName, ignoreCase = true)
    }
}
