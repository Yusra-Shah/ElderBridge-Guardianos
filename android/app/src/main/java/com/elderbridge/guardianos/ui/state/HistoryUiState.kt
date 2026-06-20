package com.elderbridge.guardianos.ui.state

/**
 * State container for the History Screen
 */
data class HistoryUiState(
    val isLoading: Boolean = false,
    val items: List<HistoryEventUiModel> = emptyList(),
    val stats: HistoryStats = HistoryStats(),
    val currentFilter: HistoryFilter = HistoryFilter.ALL,
    val searchQuery: String = ""
)
