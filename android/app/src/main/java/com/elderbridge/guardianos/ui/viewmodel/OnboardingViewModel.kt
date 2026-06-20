package com.elderbridge.guardianos.ui.viewmodel

import androidx.lifecycle.ViewModel
import com.elderbridge.guardianos.ui.state.OnboardingPageUiModel
import com.elderbridge.guardianos.ui.state.OnboardingUiState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

class OnboardingViewModel : ViewModel() {

    private val pages = listOf(
        OnboardingPageUiModel(
            emoji = "👋",
            title = "Welcome to ElderBridge",
            body = "We help you understand health forms, government letters, and benefits — right on your phone."
        ),
        OnboardingPageUiModel(
            emoji = "🔍",
            title = "We Explain Things",
            body = "When you open a confusing form or letter, we show a simple explanation in plain language."
        ),
        OnboardingPageUiModel(
            emoji = "🔒",
            title = "Your Privacy is Safe",
            body = "We never read your passwords or security codes. Your personal information never leaves your phone."
        ),
        OnboardingPageUiModel(
            emoji = "✅",
            title = "You're Always in Control",
            body = "You can turn off the assistant at any time with a single tap on your home screen."
        )
    )

    private val _uiState = MutableStateFlow(
        OnboardingUiState(
            pages = pages,
            currentPageIndex = 0,
            isLastPage = false,
            progress = 1f / pages.size
        )
    )
    val uiState: StateFlow<OnboardingUiState> = _uiState.asStateFlow()

    fun nextPage(onFinished: () -> Unit) {
        val nextIndex = _uiState.value.currentPageIndex + 1
        if (nextIndex < pages.size) {
            updateState(nextIndex)
        } else {
            onFinished()
        }
    }

    fun previousPage() {
        val prevIndex = _uiState.value.currentPageIndex - 1
        if (prevIndex >= 0) {
            updateState(prevIndex)
        }
    }

    private fun updateState(index: Int) {
        _uiState.update {
            it.copy(
                currentPageIndex = index,
                isLastPage = index == pages.size - 1,
                progress = (index + 1).toFloat() / pages.size
            )
        }
    }
}
