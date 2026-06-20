package com.elderbridge.guardianos.network

import com.google.gson.annotations.SerializedName
import retrofit2.http.Body
import retrofit2.http.POST

data class ChatMessage(
    @SerializedName("role")    val role: String,
    @SerializedName("content") val content: String
)

data class ChatRequest(
    @SerializedName("user_id")        val userId: String,
    @SerializedName("messages")       val messages: List<ChatMessage>,
    @SerializedName("screen_context") val screenContext: String = ""
)

interface ElderBridgeApi {

    /**
     * Send a redacted screen event and receive an on-device-displayable explanation.
     * Declared as `suspend` so callers must run it on Dispatchers.IO via a coroutine.
     */
    @POST("analyze-event")
    suspend fun analyzeEvent(@Body event: IncomingEvent): FinalDecision

    /**
     * Multi-turn chat: send the full conversation history and receive a
     * conversational answer.  Does NOT run the full scam-detection pipeline.
     */
    @POST("ask-question")
    suspend fun askQuestion(@Body request: ChatRequest): FinalDecision
}
