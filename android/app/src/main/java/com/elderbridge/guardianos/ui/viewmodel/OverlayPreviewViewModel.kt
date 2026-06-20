package com.elderbridge.guardianos.ui.viewmodel

import androidx.lifecycle.ViewModel
import com.elderbridge.guardianos.ui.state.OverlayPreviewFieldUiModel
import com.elderbridge.guardianos.ui.state.OverlayPreviewUiState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

class OverlayPreviewViewModel : ViewModel() {

    private val initialFields = listOf(
        OverlayPreviewFieldUiModel(
            id = 0,
            label = "Monthly Income",
            explanation = "This field is asking for your total monthly income — the money you receive each month from all sources, such as Social Security, a pension, or part-time work."
        ),
        OverlayPreviewFieldUiModel(
            id = 1,
            label = "Medicare Number",
            explanation = "This is your unique Medicare ID. You can find it printed on your red, white, and blue Medicare card — it is usually 11 characters long."
        ),
        OverlayPreviewFieldUiModel(
            id = 2,
            label = "Proof of Residence",
            explanation = "This means they need a document that shows where you live, such as a utility bill, a bank statement, or a lease agreement with your address on it."
        )
    )

    private val _uiState = MutableStateFlow(
        OverlayPreviewUiState(
            fields = initialFields.mapIndexed { index, field ->
                field.copy(isHighlighted = index == 0)
            },
            totalSteps = initialFields.size,
            progress = 1f / initialFields.size
        )
    )
    val uiState: StateFlow<OverlayPreviewUiState> = _uiState.asStateFlow()

    fun onFieldTapped(index: Int) {
        _uiState.update { currentState ->
            val newExpandedIndex = if (currentState.expandedIndex == index) -1 else index
            
            currentState.copy(
                expandedIndex = newExpandedIndex,
                fields = currentState.fields.mapIndexed { i, field ->
                    field.copy(
                        isExpanded = i == newExpandedIndex,
                        isHighlighted = i == currentState.currentStep - 1
                    )
                }
            )
        }
    }

    fun nextStep() {
        _uiState.update { currentState ->
            val nextStep = currentState.currentStep + 1
            if (nextStep <= currentState.totalSteps) {
                currentState.copy(
                    currentStep = nextStep,
                    expandedIndex = -1,
                    progress = nextStep.toFloat() / currentState.totalSteps,
                    fields = currentState.fields.mapIndexed { i, field ->
                        field.copy(
                            isExpanded = false,
                            isHighlighted = i == nextStep - 1
                        )
                    }
                )
            } else {
                currentState.copy(isDemoComplete = true)
            }
        }
    }

    fun resetDemo() {
        _uiState.value = OverlayPreviewUiState(
            fields = initialFields.mapIndexed { index, field ->
                field.copy(isHighlighted = index == 0)
            },
            totalSteps = initialFields.size,
            progress = 1f / initialFields.size
        )
    }
}
