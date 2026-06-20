package com.elderbridge.guardianos.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import android.location.Geocoder
import android.os.Handler
import android.os.Looper
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.elderbridge.guardianos.data.UserProfile
import com.elderbridge.guardianos.data.UserProfileStore
import com.elderbridge.guardianos.ui.components.PremiumButton
import com.elderbridge.guardianos.ui.components.PremiumCard
import com.elderbridge.guardianos.ui.components.PremiumSectionHeader
import com.elderbridge.guardianos.ui.theme.*
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
    var isLocating by remember { mutableStateOf(false) }

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
                                    .firstOrNull() ?: "%.4f, %.4f".format(loc.latitude, loc.longitude)
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

    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = { 
                    Text(
                        "My Profile",
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.Bold
                    ) 
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back", tint = ElderBlue)
                    }
                },
                colors = TopAppBarDefaults.centerAlignedTopAppBarColors(
                    containerColor = Color.Transparent
                )
            )
        },
        containerColor = BackgroundLight
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 24.dp, vertical = 24.dp),
            verticalArrangement = Arrangement.spacedBy(24.dp)
        ) {
            // About Me Section
            PremiumSectionHeader(
                title = "About Me",
                subtitle = "Help us personalize your experience"
            )

            PremiumCard {
                Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
                    ProfileTextField(
                        value = fullName,
                        onValueChange = { fullName = it },
                        label = "Full Name"
                    )

                    Row(verticalAlignment = Alignment.CenterVertically) {
                        ProfileTextField(
                            value = location,
                            onValueChange = { location = it },
                            label = "Location (city/area)",
                            modifier = Modifier.weight(1f),
                            trailingIcon = if (isLocating) {
                                { CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp) }
                            } else null
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Button(
                            onClick = {
                                val hasPermission = ContextCompat.checkSelfPermission(
                                    context, Manifest.permission.ACCESS_FINE_LOCATION
                                ) == PackageManager.PERMISSION_GRANTED
                                if (hasPermission) fetchLocation()
                                else locationPermLauncher.launch(Manifest.permission.ACCESS_FINE_LOCATION)
                            },
                            enabled = !isLocating,
                            modifier = Modifier.height(56.dp),
                            shape = RoundedCornerShape(12.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = ElderBluePale, contentColor = ElderBlue)
                        ) {
                            Text("GPS")
                        }
                    }
                }
            }

            // Contacts Section
            PremiumSectionHeader(
                title = "Safety Contacts",
                subtitle = "Who to reach in case of an alert"
            )

            PremiumCard {
                Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
                    ProfileTextField(
                        value = emergencyContact,
                        onValueChange = { emergencyContact = it },
                        label = "Emergency Contact Number",
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone)
                    )
                    ProfileTextField(
                        value = caregiverContact,
                        onValueChange = { caregiverContact = it },
                        label = "Caregiver Number (optional)",
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone)
                    )
                }
            }

            Spacer(modifier = Modifier.weight(1f))

            // Action Buttons
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                PremiumButton(
                    text = "Save Profile",
                    onClick = {
                        UserProfileStore.save(
                            context,
                            UserProfile(
                                fullName = fullName.trim(),
                                location = location.trim(),
                                emergencyContact = emergencyContact.trim(),
                                caregiverContact = caregiverContact.trim()
                            )
                        )
                        Toast.makeText(context, "Profile saved", Toast.LENGTH_SHORT).show()
                        onBack()
                    },
                    modifier = Modifier.fillMaxWidth(),
                    containerColor = Brush.verticalGradient(listOf(ActiveGreen, Color(0xFF1B5E20)))
                )

                OutlinedButton(
                    onClick = onBack,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(64.dp),
                    shape = RoundedCornerShape(20.dp),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = TextSecondary),
                    border = ButtonDefaults.outlinedButtonBorder.copy(width = 1.dp)
                ) {
                    Text("Cancel", fontSize = 18.sp, fontWeight = FontWeight.Bold)
                }
            }
            
            Spacer(modifier = Modifier.height(24.dp))
        }
    }
}

@Composable
fun ProfileTextField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    modifier: Modifier = Modifier,
    keyboardOptions: KeyboardOptions = KeyboardOptions.Default,
    trailingIcon: @Composable (() -> Unit)? = null
) {
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        label = { Text(label) },
        modifier = modifier.fillMaxWidth(),
        singleLine = true,
        colors = OutlinedTextFieldDefaults.colors(
            focusedBorderColor = ElderBlue,
            unfocusedBorderColor = Divider,
            focusedLabelColor = ElderBlue,
            cursorColor = ElderBlue,
            focusedContainerColor = SurfaceLight,
            unfocusedContainerColor = SurfaceLight
        ),
        shape = RoundedCornerShape(12.dp),
        keyboardOptions = keyboardOptions,
        trailingIcon = trailingIcon
    )
}
