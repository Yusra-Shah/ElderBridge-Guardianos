package com.elderbridge.guardianos.data

import java.time.Instant
import java.util.UUID

object HistoryStore {
    private const val MAX_ENTRIES = 20
    private val entries = mutableListOf<HistoryEntry>()

    fun addEntry(screenText: String, response: String, riskLevel: String) {
        val entry = HistoryEntry(
            id = UUID.randomUUID().toString(),
            timestamp = Instant.now().toString(),
            screenText = screenText,
            response = response,
            riskLevel = riskLevel
        )
        synchronized(entries) {
            entries.add(0, entry)
            if (entries.size > MAX_ENTRIES) entries.removeAt(entries.lastIndex)
        }
    }

    fun getEntries(): List<HistoryEntry> = synchronized(entries) { entries.toList() }
}
