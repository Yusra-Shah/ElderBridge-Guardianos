package com.elderbridge.guardianos.data

import android.content.Context

data class UserProfile(
    val fullName: String = "",
    val location: String = "",
    val emergencyContact: String = "",
    val caregiverContact: String = "",
    val preferredLanguage: String = "English",
)

object UserProfileStore {
    private const val PREFS_NAME = "user_profile"

    fun save(context: Context, profile: UserProfile) {
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE).edit()
            .putString("full_name", profile.fullName)
            .putString("location", profile.location)
            .putString("emergency_contact", profile.emergencyContact)
            .putString("caregiver_contact", profile.caregiverContact)
            .putString("preferred_language", profile.preferredLanguage)
            .apply()
    }

    fun load(context: Context): UserProfile {
        val p = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        return UserProfile(
            fullName = p.getString("full_name", "") ?: "",
            location = p.getString("location", "") ?: "",
            emergencyContact = p.getString("emergency_contact", "") ?: "",
            caregiverContact = p.getString("caregiver_contact", "") ?: "",
            preferredLanguage = p.getString("preferred_language", "English") ?: "English"
        )
    }

    fun getCaregiverContact(context: Context): String =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .getString("caregiver_contact", "") ?: ""

    fun getEmergencyContact(context: Context): String =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .getString("emergency_contact", "") ?: ""

    fun setAssistantEnabled(context: Context, enabled: Boolean) {
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE).edit()
            .putBoolean("assistant_enabled", enabled)
            .apply()
    }

    fun isAssistantEnabled(context: Context): Boolean =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .getBoolean("assistant_enabled", false)
}
