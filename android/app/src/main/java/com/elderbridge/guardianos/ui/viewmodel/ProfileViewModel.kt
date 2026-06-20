package com.elderbridge.guardianos.ui.viewmodel

import android.content.Context
import android.location.Geocoder
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.elderbridge.guardianos.data.UserProfile
import com.elderbridge.guardianos.data.UserProfileStore
import com.elderbridge.guardianos.ui.state.ProfileState
import com.google.android.gms.location.LocationServices
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.Locale

class ProfileViewModel : ViewModel() {

    private val _state = MutableStateFlow(ProfileState())
    val state: StateFlow<ProfileState> = _state.asStateFlow()

    fun init(context: Context) {
        val saved = UserProfileStore.load(context)
        updateFields(
            fullName = saved.fullName,
            location = saved.location,
            emergencyContact = saved.emergencyContact,
            caregiverContact = saved.caregiverContact,
            preferredLanguage = saved.preferredLanguage
        )
    }

    fun onFullNameChange(value: String) {
        _state.update { it.copy(fullName = value) }
        calculateProgress()
    }

    fun onLocationChange(value: String) {
        _state.update { it.copy(location = value) }
        calculateProgress()
    }

    fun onEmergencyContactChange(value: String) {
        _state.update { it.copy(emergencyContact = value) }
        calculateProgress()
    }

    fun onCaregiverContactChange(value: String) {
        _state.update { it.copy(caregiverContact = value) }
    }

    fun onLanguageChange(value: String) {
        _state.update { it.copy(preferredLanguage = value, languageExpanded = false) }
        calculateProgress()
    }

    fun setLanguageExpanded(expanded: Boolean) {
        _state.update { it.copy(languageExpanded = expanded) }
    }

    private fun updateFields(
        fullName: String,
        location: String,
        emergencyContact: String,
        caregiverContact: String,
        preferredLanguage: String
    ) {
        _state.update {
            it.copy(
                fullName = fullName,
                location = location,
                emergencyContact = emergencyContact,
                caregiverContact = caregiverContact,
                preferredLanguage = preferredLanguage
            )
        }
        calculateProgress()
    }

    private fun calculateProgress() {
        _state.update { s ->
            val fields = listOf(s.fullName, s.location, s.emergencyContact, s.preferredLanguage)
            val completed = fields.count { it.isNotBlank() }
            s.copy(
                completedFieldsCount = completed,
                progress = completed.toFloat() / fields.size,
                hasEmergencyContact = s.emergencyContact.isNotBlank()
            )
        }
    }

    fun fetchLocation(context: Context) {
        _state.update { it.copy(isLocating = true) }
        val fusedClient = LocationServices.getFusedLocationProviderClient(context)
        
        try {
            fusedClient.lastLocation.addOnSuccessListener { loc ->
                if (loc == null) {
                    _state.update { it.copy(isLocating = false, location = "Location not found") }
                    return@addOnSuccessListener
                }

                viewModelScope.launch {
                    val result = withContext(Dispatchers.IO) {
                        try {
                            @Suppress("DEPRECATION")
                            val addresses = Geocoder(context, Locale.getDefault())
                                .getFromLocation(loc.latitude, loc.longitude, 1)
                            
                            if (!addresses.isNullOrEmpty()) {
                                val addr = addresses[0]
                                listOfNotNull(addr.locality, addr.subAdminArea, addr.adminArea)
                                    .firstOrNull() ?: "%.4f, %.4f".format(loc.latitude, loc.longitude)
                            } else {
                                "%.4f, %.4f".format(loc.latitude, loc.longitude)
                            }
                        } catch (e: Exception) {
                            "%.4f, %.4f".format(loc.latitude, loc.longitude)
                        }
                    }
                    
                    _state.update { it.copy(isLocating = false, location = result) }
                    calculateProgress()
                }
            }.addOnFailureListener {
                _state.update { it.copy(isLocating = false, location = "Location unavailable") }
            }
        } catch (e: SecurityException) {
            _state.update { it.copy(isLocating = false) }
        }
    }

    fun saveProfile(context: Context, onSaved: () -> Unit) {
        val s = _state.value
        UserProfileStore.save(
            context,
            UserProfile(
                fullName = s.fullName.trim(),
                location = s.location.trim(),
                emergencyContact = s.emergencyContact.trim(),
                caregiverContact = s.caregiverContact.trim(),
                preferredLanguage = s.preferredLanguage
            )
        )
        onSaved()
    }
}
