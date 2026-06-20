package com.elderbridge.guardianos.ui.state

/**
 * Visual summary statistics of user activity
 */
data class HistoryStats(
    val totalScans: Int = 0,
    val safeCount: Int = 0,
    val cautionCount: Int = 0,
    val scamCount: Int = 0
)
