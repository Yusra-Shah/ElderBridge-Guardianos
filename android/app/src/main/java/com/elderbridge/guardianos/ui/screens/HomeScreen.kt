package com.elderbridge.guardianos.ui.screens

import android.content.Intent
import android.os.Build
import android.provider.Settings
import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.elderbridge.guardianos.services.OverlayService
import com.elderbridge.guardianos.services.ScreenReaderService
import com.elderbridge.guardianos.ui.theme.ActiveGreen
import com.elderbridge.guardianos.ui.theme.ActiveGreenLight

@Composable
fun HomeScreen(onTryDemo: () -> Unit, onHistory: () -> Unit, onProfile: () -> Unit) {
    val context = LocalContext.current
    var isMonitoringEnabled by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(horizontal = 28.dp, vertical = 56.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.SpaceBetween
    ) {
        // App header
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                text = "ElderBridge",
                style = MaterialTheme.typography.headlineLarge,
                color = MaterialTheme.colorScheme.primary,
                textAlign = TextAlign.Center
            )
            Text(
                text = "Guardian Assistant",
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(top = 4.dp)
            )
        }

        // Status indicator + toggle
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(32.dp)
        ) {
            StatusCircle(isActive = isMonitoringEnabled)

            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(20.dp),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(24.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(modifier = Modifier.weight(1f).padding(end = 16.dp)) {
                        Text(
                            text = "Assistant Monitoring",
                            style = MaterialTheme.typography.titleLarge,
                            color = MaterialTheme.colorScheme.onBackground
                        )
                        Text(
                            text = if (isMonitoringEnabled)
                                "Active — I am watching over your apps"
                            else
                                "Tap the switch to turn me on",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(top = 6.dp)
                        )
                    }
                    Switch(
                        checked = isMonitoringEnabled,
                        onCheckedChange = { enabled ->
                            if (enabled) {
                                if (!Settings.canDrawOverlays(context)) {
                                    Toast.makeText(
                                        context,
                                        "Please grant Display Over Apps permission first",
                                        Toast.LENGTH_LONG
                                    ).show()
                                } else {
                                    val enabledServices = Settings.Secure.getString(
                                        context.contentResolver,
                                        Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
                                    ) ?: ""
                                    val component =
                                        "${context.packageName}/${ScreenReaderService::class.java.name}"
                                    if (!enabledServices.contains(component, ignoreCase = true)) {
                                        Toast.makeText(
                                            context,
                                            "Please enable ElderBridge in Accessibility Settings first",
                                            Toast.LENGTH_LONG
                                        ).show()
                                    } else {
                                        val intent = Intent(context, OverlayService::class.java)
                                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                                            context.startForegroundService(intent)
                                        } else {
                                            context.startService(intent)
                                        }
                                        isMonitoringEnabled = true
                                    }
                                }
                            } else {
                                context.stopService(Intent(context, OverlayService::class.java))
                                isMonitoringEnabled = false
                            }
                        },
                        colors = SwitchDefaults.colors(
                            checkedTrackColor = ActiveGreen,
                            checkedThumbColor = MaterialTheme.colorScheme.onPrimary,
                        )
                    )
                }
            }
        }

        // Demo entry point
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Button(
                onClick = onTryDemo,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(64.dp),
                shape = RoundedCornerShape(16.dp)
            ) {
                Text(text = "Try a Demo", style = MaterialTheme.typography.labelLarge)
            }
            Spacer(modifier = Modifier.height(12.dp))
            Text(
                text = "See how the assistant explains forms",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center
            )
            Spacer(modifier = Modifier.height(16.dp))
            OutlinedButton(
                onClick = onHistory,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp),
                shape = RoundedCornerShape(16.dp)
            ) {
                Text(text = "View History", style = MaterialTheme.typography.labelLarge)
            }
            Spacer(modifier = Modifier.height(8.dp))
            OutlinedButton(
                onClick = onProfile,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp),
                shape = RoundedCornerShape(16.dp)
            ) {
                Text(text = "My Profile", style = MaterialTheme.typography.labelLarge)
            }
        }
    }
}

@Composable
private fun StatusCircle(isActive: Boolean) {
    val bgColor = if (isActive) ActiveGreenLight else MaterialTheme.colorScheme.surfaceVariant
    val textColor = if (isActive) ActiveGreen else MaterialTheme.colorScheme.onSurfaceVariant

    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Box(
            contentAlignment = Alignment.Center,
            modifier = Modifier
                .size(120.dp)
                .clip(CircleShape)
                .background(bgColor)
        ) {
            Text(
                text = if (isActive) "ON" else "OFF",
                style = MaterialTheme.typography.headlineMedium,
                color = textColor
            )
        }
        Text(
            text = if (isActive) "Assistant is Active" else "Assistant is Off",
            style = MaterialTheme.typography.bodyLarge,
            color = textColor
        )
    }
}
