package com.elderbridge.guardianos.ui.state

/**
 * State container for the Permissions setup screen
 */
data class PermissionsUiState(
    val accessibilityGranted: Boolean = false,
    val notificationGranted: Boolean = false,
    val overlayGranted: Boolean = false,
    val allGranted: Boolean = false,
    val progress: Float = 0f,
    val completedSteps: Int = 0,
    val totalSteps: Int = 3,
    val permissionItems: List<PermissionItemUiModel> = emptyList()
)
