package com.elderbridge.guardianos.ui.state

/**
 * State container for the Onboarding Screen.
 */
data class OnboardingUiState(
    val currentPageIndex: Int = 0,
    val pages: List<OnboardingPageUiModel> = emptyList(),
    val isLastPage: Boolean = false,
    val progress: Float = 0f
)
