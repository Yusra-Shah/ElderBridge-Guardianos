package com.elderbridge.guardianos.ui.state

/**
 * Immutable UI state for the Profile screen.
 */
data class ProfileState(
    val fullName: String = "",
    val location: String = "",
    val emergencyContact: String = "",
    val caregiverContact: String = "",
    val preferredLanguage: String = "English",
    val isLocating: Boolean = false,
    val languageExpanded: Boolean = false,
    
    // Calculated UI properties
    val completedFieldsCount: Int = 0,
    val totalFieldsCount: Int = 4,
    val progress: Float = 0f,
    val hasEmergencyContact: Boolean = false
)
