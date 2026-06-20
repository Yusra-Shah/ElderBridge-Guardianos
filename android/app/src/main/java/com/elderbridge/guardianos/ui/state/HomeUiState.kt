package com.elderbridge.guardianos.ui.state

/**
 * Home screen UI state for ElderBridge GuardianOS
 */
data class HomeUiState(
    val isMonitoringEnabled: Boolean = false,

    // Permission handling
    val showPermissionError: Boolean = false,
    val permissionErrorMessage: String? = null,

    // 🔥 AI / system visual states (NEW)
    val systemStatus: SystemStatus = SystemStatus.OFF
)

/**
 * Represents what the assistant is currently doing visually
 */
enum class SystemStatus {
    OFF,
    ACTIVE,
    ANALYZING,
    SCAM_DETECTED
}