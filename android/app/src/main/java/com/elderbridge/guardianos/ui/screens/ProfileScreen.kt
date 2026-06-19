package com.elderbridge.guardianos.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import android.location.Geocoder
import android.os.Handler
import android.os.Looper
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.elderbridge.guardianos.data.UserProfile
import com.elderbridge.guardianos.data.UserProfileStore
import com.google.android.gms.location.LocationServices
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProfileScreen(onBack: () -> Unit) {
    val context = LocalContext.current
    val saved = remember { UserProfileStore.load(context) }

    var fullName by remember { mutableStateOf(saved.fullName) }
    var location by remember { mutableStateOf(saved.location) }
    var emergencyContact by remember { mutableStateOf(saved.emergencyContact) }
    var caregiverContact by remember { mutableStateOf(saved.caregiverContact) }
    var preferredLanguage by remember { mutableStateOf(saved.preferredLanguage) }
    var languageExpanded by remember { mutableStateOf(false) }
    var isLocating by remember { mutableStateOf(false) }

    val languages = listOf("English", "Urdu")

    // Geocode on a background thread and post result back to main
    fun fetchLocation() {
        isLocating = true
        val fusedClient = LocationServices.getFusedLocationProviderClient(context)
        try {
            fusedClient.lastLocation
                .addOnSuccessListener { loc ->
                    if (loc == null) {
                        isLocating = false
                        location = "No recent fix — open Maps first"
                        return@addOnSuccessListener
                    }
                    Thread {
                        val result = try {
                            @Suppress("DEPRECATION")
                            val addresses = Geocoder(context, Locale.getDefault())
                                .getFromLocation(loc.latitude, loc.longitude, 1)
                            if (!addresses.isNullOrEmpty()) {
                                val addr = addresses[0]
                                listOfNotNull(addr.locality, addr.subAdminArea, addr.adminArea)
                                    .firstOrNull()
                                    ?: "%.4f, %.4f".format(loc.latitude, loc.longitude)
                            } else {
                                "%.4f, %.4f".format(loc.latitude, loc.longitude)
                            }
                        } catch (e: Exception) {
                            "%.4f, %.4f".format(loc.latitude, loc.longitude)
                        }
                        Handler(Looper.getMainLooper()).post {
                            location = result
                            isLocating = false
                        }
                    }.start()
                }
                .addOnFailureListener {
                    isLocating = false
                    location = "Location unavailable"
                }
        } catch (e: SecurityException) {
            isLocating = false
        }
    }

    val locationPermLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) fetchLocation() else isLocating = false
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(horizontal = 24.dp, vertical = 48.dp)
            .verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text(
            text = "My Profile",
            style = MaterialTheme.typography.headlineMedium,
            color = MaterialTheme.colorScheme.primary
        )
        Spacer(modifier = Modifier.height(8.dp))

        OutlinedTextField(
            value = fullName,
            onValueChange = { fullName = it },
            label = { Text("Full Name") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true
        )

        OutlinedTextField(
            value = location,
            onValueChange = { location = it },
            label = { Text("Location (city/area)") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            trailingIcon = if (isLocating) {
                { CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp) }
            } else null
        )
        Button(
            onClick = {
                val hasPermission = ContextCompat.checkSelfPermission(
                    context, Manifest.permission.ACCESS_FINE_LOCATION
                ) == PackageManager.PERMISSION_GRANTED
                if (hasPermission) fetchLocation()
                else locationPermLauncher.launch(Manifest.permission.ACCESS_FINE_LOCATION)
            },
            enabled = !isLocating,
            modifier = Modifier.fillMaxWidth(),
            colors = ButtonDefaults.buttonColors(
                containerColor = MaterialTheme.colorScheme.secondaryContainer,
                contentColor = MaterialTheme.colorScheme.onSecondaryContainer
            )
        ) {
            Text(if (isLocating) "Getting location…" else "Get My Location")
        }

        OutlinedTextField(
            value = emergencyContact,
            onValueChange = { emergencyContact = it },
            label = { Text("Emergency Contact Number") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone)
        )
        OutlinedTextField(
            value = caregiverContact,
            onValueChange = { caregiverContact = it },
            label = { Text("Caregiver Contact Number (optional)") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone)
        )

        ExposedDropdownMenuBox(
            expanded = languageExpanded,
            onExpandedChange = { languageExpanded = !languageExpanded }
        ) {
            OutlinedTextField(
                value = preferredLanguage,
                onValueChange = {},
                readOnly = true,
                label = { Text("Preferred Language") },
                trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = languageExpanded) },
                modifier = Modifier
                    .menuAnchor()
                    .fillMaxWidth()
            )
            ExposedDropdownMenu(
                expanded = languageExpanded,
                onDismissRequest = { languageExpanded = false }
            ) {
                languages.forEach { lang ->
                    DropdownMenuItem(
                        text = { Text(lang) },
                        onClick = {
                            preferredLanguage = lang
                            languageExpanded = false
                        }
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(8.dp))

        Button(
            onClick = {
                UserProfileStore.save(
                    context,
                    UserProfile(
                        fullName = fullName.trim(),
                        location = location.trim(),
                        emergencyContact = emergencyContact.trim(),
                        caregiverContact = caregiverContact.trim(),
                        preferredLanguage = preferredLanguage
                    )
                )
                Toast.makeText(context, "Profile saved", Toast.LENGTH_SHORT).show()
                onBack()
            },
            modifier = Modifier
                .fillMaxWidth()
                .height(56.dp)
        ) {
            Text("Save", style = MaterialTheme.typography.labelLarge)
        }

        OutlinedButton(
            onClick = onBack,
            modifier = Modifier
                .fillMaxWidth()
                .height(56.dp)
        ) {
            Text("Cancel")
        }
    }
}
