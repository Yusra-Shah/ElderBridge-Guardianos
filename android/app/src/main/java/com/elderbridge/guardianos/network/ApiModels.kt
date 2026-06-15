package com.elderbridge.guardianos.network

import com.google.gson.annotations.SerializedName

/**
 * Request payload sent to POST /analyze-event.
 *
 * redacted_text is always sourced from ScreenContentHolder, which only ever holds
 * text that has already passed through RedactionEngine — see ScreenReaderService.
 */
data class IncomingEvent(
    @SerializedName("event_type")   val eventType: String,
    @SerializedName("source_app")   val sourceApp: String,
    @SerializedName("redacted_text") val redactedText: String,
    @SerializedName("timestamp_ms") val timestampMs: Long,
    @SerializedName("user_id")      val userId: String
)

/**
 * Response returned by POST /analyze-event.
 *
 * next_steps may be absent from the response (older backend versions); default to empty.
 * confidence is informational only — the UI does not currently surface it.
 */
data class FinalDecision(
    @SerializedName("response_text") val responseText: String,
    @SerializedName("next_steps")    val nextSteps: List<String> = emptyList(),
    @SerializedName("confidence")    val confidence: Float? = null
)
