package com.elderbridge.guardianos.ui.state

/**
 * UI model representing a single onboarding slide.
 * Reconciled with original field names for merge compatibility.
 */
data class OnboardingPageUiModel(
    val emoji: String,
    val title: String,
    val body: String
)
