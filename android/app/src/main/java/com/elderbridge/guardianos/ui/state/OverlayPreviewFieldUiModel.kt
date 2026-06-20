package com.elderbridge.guardianos.ui.state

/**
 * UI model representing a single field in the interactive demo.
 */
data class OverlayPreviewFieldUiModel(
    val id: Int,
    val label: String,
    val explanation: String,
    val isExpanded: Boolean = false,
    val isHighlighted: Boolean = false
)
