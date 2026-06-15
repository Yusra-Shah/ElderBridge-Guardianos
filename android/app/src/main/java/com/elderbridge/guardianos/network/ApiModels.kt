package com.elderbridge.guardianos.network

import com.google.gson.annotations.SerializedName

/**
 * Request payload sent to POST /analyze-event.
 *
 * redacted_text is always sourced from ScreenContentHolder, which only ever holds
 * text that has already passed through RedactionEngine — see ScreenReaderService.
 *
 * timestamp must be an ISO-8601 UTC string (e.g. "2026-06-15T14:30:00Z").
 * Callers must convert epoch-ms via Instant.ofEpochMilli(...).toString() before
 * constructing this object.
 */
data class IncomingEvent(
    @SerializedName("event_type")    val eventType: String,
    @SerializedName("source_app")    val sourceApp: String,
    @SerializedName("redacted_text") val redactedText: String,
    @SerializedName("timestamp")     val timestamp: String,
    @SerializedName("user_id")       val userId: String
)

/**
 * Response returned by POST /analyze-event.
 *
 * next_steps and source_citations default to emptyList() for compatibility with
 * backends that omit those fields. confidence and risk_flag are informational;
 * the UI does not currently surface them but they are parsed correctly so future
 * code can use them without a model change.
 */
data class FinalDecision(
    @SerializedName("response_text")    val responseText: String,
    @SerializedName("next_steps")       val nextSteps: List<String> = emptyList(),
    @SerializedName("confidence")       val confidence: Float? = null,
    @SerializedName("risk_flag")        val riskFlag: String? = null,
    @SerializedName("source_citations") val sourceCitations: List<EvidenceItem> = emptyList()
)

/**
 * A single supporting evidence item returned inside FinalDecision.source_citations.
 * Mirrors the backend's EvidenceItem Pydantic schema.
 */
data class EvidenceItem(
    @SerializedName("source_id")       val sourceId: String,
    @SerializedName("title")           val title: String,
    @SerializedName("tier")            val tier: Int,
    @SerializedName("snippet")         val snippet: String,
    @SerializedName("relevance_score") val relevanceScore: Float
)
