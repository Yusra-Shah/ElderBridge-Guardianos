package com.elderbridge.guardianos.network

import retrofit2.http.Body
import retrofit2.http.POST

interface ElderBridgeApi {

    /**
     * Send a redacted screen event and receive an on-device-displayable explanation.
     * Declared as `suspend` so callers must run it on Dispatchers.IO via a coroutine.
     */
    @POST("analyze-event")
    suspend fun analyzeEvent(@Body event: IncomingEvent): FinalDecision
}
