package com.elderbridge.guardianos.ui.state

/**
 * Action types for different system permissions
 */
enum class PermissionActionType {
    ACCESSIBILITY,
    NOTIFICATION,
    OVERLAY
}

/**
 * UI representation of a single permission setup step
 */
data class PermissionItemUiModel(
    val title: String,
    val description: String,
    val isGranted: Boolean,
    val actionType: PermissionActionType
)
