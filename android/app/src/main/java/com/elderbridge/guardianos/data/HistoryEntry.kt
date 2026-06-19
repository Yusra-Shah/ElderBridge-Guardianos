package com.elderbridge.guardianos.data

data class HistoryEntry(
    val id: String,
    val timestamp: String,
    val screenText: String,
    val response: String,
    val riskLevel: String
)
