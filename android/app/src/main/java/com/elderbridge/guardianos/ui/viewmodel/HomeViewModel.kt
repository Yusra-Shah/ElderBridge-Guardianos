package com.elderbridge.guardianos.ui.viewmodel

import android.content.Context
import android.content.Intent
import android.os.Build
import android.provider.Settings
import androidx.lifecycle.ViewModel
import com.elderbridge.guardianos.services.OverlayService
import com.elderbridge.guardianos.ui.state.HomeUiState
import com.elderbridge.guardianos.ui.state.SystemStatus
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

class HomeViewModel : ViewModel() {

    private val _uiState = MutableStateFlow(HomeUiState())
    val uiState: StateFlow<HomeUiState> = _uiState.asStateFlow()

    fun loadInitialState(context: Context) {
        // Here you would check if service is already running or preferences
        // For now, initializing to default using the provided context
        val isEnabled = com.elderbridge.guardianos.data.UserProfileStore.isAssistantEnabled(context)
        _uiState.update { 
            it.copy(
                isMonitoringEnabled = isEnabled,
                systemStatus = if (isEnabled) SystemStatus.ACTIVE else SystemStatus.OFF
            )
        }
    }

    fun toggleAssistant(context: Context, enabled: Boolean) {
        if (enabled) {
            // 1. Check for Overlay Permission first
            if (!Settings.canDrawOverlays(context)) {
                onPermissionDenied("ElderBridge needs 'Display over other apps' permission to show the helper bubble.")
                return
            }

            // 2. Start the service
            val intent = Intent(context, OverlayService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        } else {
            // 3. Stop the service
            context.stopService(Intent(context, OverlayService::class.java))
        }

        // 4. Update UI State & Persistence
        com.elderbridge.guardianos.data.UserProfileStore.setAssistantEnabled(context, enabled)
        _uiState.update { 
            it.copy(
                isMonitoringEnabled = enabled,
                systemStatus = if (enabled) SystemStatus.ACTIVE else SystemStatus.OFF
            ) 
        }
    }

    fun onPermissionDenied(message: String) {
        _uiState.update {
            it.copy(
                showPermissionError = true,
                permissionErrorMessage = message
            )
        }
    }

    fun dismissPermissionError() {
        _uiState.update {
            it.copy(
                showPermissionError = false,
                permissionErrorMessage = null
            )
        }
    }
}
