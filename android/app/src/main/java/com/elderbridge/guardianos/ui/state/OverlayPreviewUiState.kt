package com.elderbridge.guardianos.ui.state

/**
 * State container for the Overlay Preview interactive demo.
 */
data class OverlayPreviewUiState(
    val fields: List<OverlayPreviewFieldUiModel> = emptyList(),
    val expandedIndex: Int = -1,
    val currentStep: Int = 1,
    val totalSteps: Int = 3,
    val progress: Float = 0f,
    val isDemoComplete: Boolean = false
)
