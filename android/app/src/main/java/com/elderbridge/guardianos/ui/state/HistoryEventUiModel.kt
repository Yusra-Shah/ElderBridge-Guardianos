package com.elderbridge.guardianos.ui.state

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector

/**
 * UI-ready representation of a history event
 */
data class HistoryEventUiModel(
    val id: String,
    val response: String,
    val screenText: String,
    val relativeTime: String,
    val riskColor: Color,
    val riskLabel: String,
    val riskIcon: ImageVector,
    val isExpanded: Boolean = false
)
