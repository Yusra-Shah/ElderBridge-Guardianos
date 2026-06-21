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
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.elderbridge.guardianos.data.UserProfile
import com.elderbridge.guardianos.data.UserProfileStore
import com.elderbridge.guardianos.ui.theme.EbSage
import com.elderbridge.guardianos.ui.theme.EbSurface
import com.google.android.gms.location.LocationServices
import java.util.Locale

@Composable
fun ProfileScreen(
    onBack: () -> Unit,
    isDarkMode: Boolean = false,
    onDarkModeChanged: (Boolean) -> Unit = {}
) {
    val context = LocalContext.current
    val saved = remember { UserProfileStore.load(context) }

    var fullName by remember { mutableStateOf(saved.fullName) }
    var location by remember { mutableStateOf(saved.location) }
    var emergencyContact by remember { mutableStateOf(saved.emergencyContact) }
    var caregiverContact by remember { mutableStateOf(saved.caregiverContact) }
    var isLocating by remember { mutableStateOf(false) }
    var soundEnabled by remember { mutableStateOf(UserProfileStore.isSoundEnabled(context)) }

    fun fetchLocation() {
        isLocating = true
        val fusedClient = LocationServices.getFusedLocationProviderClient(context)
        try {
            fusedClient.lastLocation
                .addOnSuccessListener { loc ->
                    if (loc == null) {
                        isLocating = false
                        location = "No recent fix. Open Maps first."
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
            text = "Profile",
            style = MaterialTheme.typography.headlineLarge,
            color = MaterialTheme.colorScheme.onBackground
        )
        Spacer(modifier = Modifier.height(8.dp))

        ProfileField(label = "Name", value = fullName, onValueChange = { fullName = it })

        ProfileField(
            label = "Emergency contact number",
            value = emergencyContact,
            onValueChange = { emergencyContact = it },
            keyboardType = KeyboardType.Phone
        )

        ProfileField(
            label = "Caregiver contact number",
            value = caregiverContact,
            onValueChange = { caregiverContact = it },
            keyboardType = KeyboardType.Phone
        )

        ProfileField(
            label = "Location",
            value = location,
            onValueChange = { location = it },
            trailingContent = if (isLocating) {
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
            modifier = Modifier.fillMaxWidth().height(56.dp),
            shape = RoundedCornerShape(16.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = MaterialTheme.colorScheme.surfaceVariant,
                contentColor = MaterialTheme.colorScheme.onSurfaceVariant
            )
        ) {
            Text(
                if (isLocating) "Getting location..." else "Get My Location",
                style = MaterialTheme.typography.labelLarge
            )
        }

        Spacer(modifier = Modifier.height(8.dp))

        // Settings toggles
        SettingToggle(
            label = "Dark mode",
            checked = isDarkMode,
            onCheckedChange = onDarkModeChanged
        )

        SettingToggle(
            label = "Sound effects",
            checked = soundEnabled,
            onCheckedChange = { enabled ->
                UserProfileStore.setSoundEnabled(context, enabled)
                soundEnabled = enabled
            }
        )

        Spacer(modifier = Modifier.height(8.dp))

        Button(
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
            modifier = Modifier.fillMaxWidth().height(56.dp),
            shape = RoundedCornerShape(16.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = EbSage,
                contentColor = EbSurface
            )
        ) {
            Text("Save", style = MaterialTheme.typography.labelLarge)
        }

        OutlinedButton(
            onClick = onBack,
            modifier = Modifier.fillMaxWidth().height(56.dp),
            shape = RoundedCornerShape(16.dp)
        ) {
            Text("Cancel", style = MaterialTheme.typography.labelLarge)
        }
    }
}

@Composable
private fun ProfileField(
    label: String,
    value: String,
    onValueChange: (String) -> Unit,
    keyboardType: KeyboardType = KeyboardType.Text,
    trailingContent: @Composable (() -> Unit)? = null
) {
    Column {
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(bottom = 6.dp)
        )
        TextField(
            value = value,
            onValueChange = onValueChange,
            modifier = Modifier
                .fillMaxWidth()
                .border(
                    width = 1.dp,
                    color = MaterialTheme.colorScheme.outline,
                    shape = RoundedCornerShape(14.dp)
                ),
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = keyboardType),
            trailingIcon = trailingContent,
            shape = RoundedCornerShape(14.dp),
            colors = TextFieldDefaults.colors(
                focusedContainerColor = MaterialTheme.colorScheme.surface,
                unfocusedContainerColor = MaterialTheme.colorScheme.surface,
                focusedIndicatorColor = Color.Transparent,
                unfocusedIndicatorColor = Color.Transparent,
                cursorColor = EbSage
            ),
            textStyle = MaterialTheme.typography.bodyLarge
        )
    }
}

@Composable
private fun SettingToggle(label: String, checked: Boolean, onCheckedChange: (Boolean) -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp, vertical = 16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = label,
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurface
            )
            Switch(
                checked = checked,
                onCheckedChange = onCheckedChange,
                colors = SwitchDefaults.colors(
                    checkedTrackColor = EbSage,
                    checkedThumbColor = EbSurface,
                    uncheckedTrackColor = MaterialTheme.colorScheme.surfaceVariant,
                    uncheckedThumbColor = MaterialTheme.colorScheme.onSurfaceVariant
                )
            )
        }
    }
}
