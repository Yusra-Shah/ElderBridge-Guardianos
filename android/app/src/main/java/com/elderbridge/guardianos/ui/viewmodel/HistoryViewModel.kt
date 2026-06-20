package com.elderbridge.guardianos.ui.viewmodel

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Dangerous
import androidx.compose.material.icons.filled.Info
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.elderbridge.guardianos.data.HistoryEntry
import com.elderbridge.guardianos.data.HistoryStore
import com.elderbridge.guardianos.ui.state.HistoryEventUiModel
import com.elderbridge.guardianos.ui.state.HistoryFilter
import com.elderbridge.guardianos.ui.state.HistoryStats
import com.elderbridge.guardianos.ui.state.HistoryUiState
import com.elderbridge.guardianos.ui.theme.ActiveGreen
import com.elderbridge.guardianos.ui.theme.ErrorRed
import com.elderbridge.guardianos.ui.theme.WarningAmber
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import java.time.Duration
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

class HistoryViewModel : ViewModel() {

    private val _searchQuery = MutableStateFlow("")
    private val _currentFilter = MutableStateFlow(HistoryFilter.ALL)
    private val _expandedItems = MutableStateFlow<Set<String>>(emptySet())

    // Combine underlying data with UI search/filter/expansion logic
    val uiState: StateFlow<HistoryUiState> = combine(
        _searchQuery,
        _currentFilter,
        _expandedItems
    ) { query, filter, expanded ->
        val rawEntries = HistoryStore.getEntries()
        
        val filtered = rawEntries.filter { entry ->
            val matchesFilter = when (filter) {
                HistoryFilter.ALL -> true
                HistoryFilter.SAFE -> entry.riskLevel.lowercase() == "ok"
                HistoryFilter.CAUTION -> entry.riskLevel.lowercase() == "caution"
                HistoryFilter.SCAM_ALERTS -> entry.riskLevel.lowercase() == "stop_and_verify"
            }
            val matchesSearch = query.isBlank() || 
                entry.response.contains(query, ignoreCase = true) ||
                entry.screenText.contains(query, ignoreCase = true)
            
            matchesFilter && matchesSearch
        }

        HistoryUiState(
            items = filtered.map { it.toUiModel(expanded.contains(it.id)) },
            stats = calculateStats(rawEntries),
            currentFilter = filter,
            searchQuery = query
        )
    }.stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(5000),
        initialValue = HistoryUiState(isLoading = true)
    )

    fun onSearchQueryChanged(query: String) {
        _searchQuery.value = query
    }

    fun onFilterChanged(filter: HistoryFilter) {
        _currentFilter.value = filter
    }

    fun toggleItemExpansion(id: String) {
        _expandedItems.update { current ->
            if (current.contains(id)) current - id else current + id
        }
    }

    private fun calculateStats(entries: List<HistoryEntry>) = HistoryStats(
        totalScans = entries.size,
        safeCount = entries.count { it.riskLevel.lowercase() == "ok" },
        cautionCount = entries.count { it.riskLevel.lowercase() == "caution" },
        scamCount = entries.count { it.riskLevel.lowercase() == "stop_and_verify" }
    )

    private fun HistoryEntry.toUiModel(isExpanded: Boolean): HistoryEventUiModel {
        val (color, label, icon) = when (riskLevel.lowercase()) {
            "stop_and_verify" -> Triple(ErrorRed, "SCAM ALERT", Icons.Default.Dangerous)
            "caution" -> Triple(WarningAmber, "CAUTION", Icons.Default.Info)
            else -> Triple(ActiveGreen, "SAFE", Icons.Default.CheckCircle)
        }

        return HistoryEventUiModel(
            id = id,
            response = response,
            screenText = screenText,
            relativeTime = formatRelativeTime(timestamp),
            riskColor = color,
            riskLabel = label,
            riskIcon = icon,
            isExpanded = isExpanded
        )
    }

    private fun formatRelativeTime(iso: String): String = runCatching {
        val instant = Instant.parse(iso)
        val diff = Duration.between(instant, Instant.now())
        when {
            diff.isNegative -> "Just now"
            diff.toMinutes() < 1 -> "Just now"
            diff.toMinutes() < 60 -> "${diff.toMinutes()} mins ago"
            diff.toHours() < 24 -> "${diff.toHours()} hours ago"
            diff.toDays() == 1L -> "Yesterday"
            else -> DateTimeFormatter.ofPattern("MMM d, yyyy").withZone(ZoneId.systemDefault()).format(instant)
        }
    }.getOrDefault(iso)
}
