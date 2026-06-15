package com.elderbridge.guardianos.ui.screens

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.elderbridge.guardianos.ui.theme.ActiveGreen
import com.elderbridge.guardianos.ui.theme.ActiveGreenLight

@Composable
fun PermissionsScreen(onContinue: () -> Unit) {
    val context = LocalContext.current
    // refreshKey increments when user taps "Check again" after returning from Settings
    var refreshKey by remember { mutableIntStateOf(0) }

    val hasAccessibility = remember(refreshKey) { isScreenReaderEnabled(context) }
    val hasNotificationAccess = remember(refreshKey) { isNotificationAccessEnabled(context) }
    val hasOverlay = remember(refreshKey) { Settings.canDrawOverlays(context) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 24.dp, vertical = 48.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            text = "Allow Permissions",
            style = MaterialTheme.typography.headlineLarge,
            color = MaterialTheme.colorScheme.onBackground,
            textAlign = TextAlign.Center,
            modifier = Modifier.padding(bottom = 12.dp)
        )
        Text(
            text = "These let ElderBridge help you.",
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
            modifier = Modifier.padding(bottom = 40.dp)
        )

        PermissionCard(
            title = "Accessibility Service",
            description = "Lets us see what is on your screen so we can explain it to you.",
            isGranted = hasAccessibility,
            onEnable = {
                context.startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
            }
        )
        Spacer(modifier = Modifier.height(20.dp))

        PermissionCard(
            title = "Notification Access",
            description = "Lets us explain notifications from health and government apps.",
            isGranted = hasNotificationAccess,
            onEnable = {
                context.startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
            }
        )
        Spacer(modifier = Modifier.height(20.dp))

        PermissionCard(
            title = "Display Over Apps",
            description = "Lets us show a small helper bubble while you use other apps.",
            isGranted = hasOverlay,
            onEnable = {
                context.startActivity(
                    Intent(
                        Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                        Uri.parse("package:${context.packageName}")
                    )
                )
            }
        )

        Spacer(modifier = Modifier.height(32.dp))

        // After returning from system Settings, user taps this to re-check grant status
        TextButton(
            onClick = { refreshKey++ },
            modifier = Modifier.height(56.dp)
        ) {
            Text(
                text = "Check status again",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.primary
            )
        }

        Spacer(modifier = Modifier.height(16.dp))

        Button(
            onClick = onContinue,
            modifier = Modifier
                .fillMaxWidth()
                .height(64.dp),
            shape = RoundedCornerShape(16.dp)
        ) {
            Text(
                text = if (hasAccessibility && hasNotificationAccess && hasOverlay)
                    "Continue" else "Continue Anyway",
                style = MaterialTheme.typography.labelLarge
            )
        }
    }
}

@Composable
private fun PermissionCard(
    title: String,
    description: String,
    isGranted: Boolean,
    onEnable: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(modifier = Modifier.padding(20.dp)) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleLarge,
                    color = MaterialTheme.colorScheme.onBackground,
                    modifier = Modifier.weight(1f)
                )
                Spacer(modifier = Modifier.width(12.dp))
                GrantedChip(isGranted = isGranted)
            }
            Spacer(modifier = Modifier.height(10.dp))
            Text(
                text = description,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            if (!isGranted) {
                Spacer(modifier = Modifier.height(16.dp))
                OutlinedButton(
                    onClick = onEnable,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(56.dp),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Text(
                        text = "Enable in Settings",
                        style = MaterialTheme.typography.labelLarge
                    )
                }
            }
        }
    }
}

@Composable
private fun GrantedChip(isGranted: Boolean) {
    Surface(
        color = if (isGranted) ActiveGreenLight else MaterialTheme.colorScheme.errorContainer,
        shape = RoundedCornerShape(50)
    ) {
        Text(
            text = if (isGranted) "✓ Granted" else "Not granted",
            style = MaterialTheme.typography.bodyMedium,
            color = if (isGranted) ActiveGreen else MaterialTheme.colorScheme.error,
            modifier = Modifier.padding(horizontal = 14.dp, vertical = 6.dp)
        )
    }
}

/**
 * Returns true only when ScreenReaderService specifically is listed in the enabled
 * accessibility services setting. Checking the full component name avoids false
 * positives from other accessibility services the user may have enabled from this package.
 *
 * The setting stores entries as "pkg/ComponentClass" separated by ":", in either
 * short (pkg/.ClassName) or long (pkg/pkg.ClassName) form.
 */
private fun isScreenReaderEnabled(context: Context): Boolean {
    val enabled = Settings.Secure.getString(
        context.contentResolver,
        Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
    ) ?: return false
    return enabled.split(':').any { entry ->
        val parts = entry.trim().split('/')
        parts.size == 2 &&
            parts[0].equals(context.packageName, ignoreCase = true) &&
            parts[1].contains("ScreenReaderService", ignoreCase = true)
    }
}

private fun isNotificationAccessEnabled(context: Context): Boolean {
    val enabled = Settings.Secure.getString(
        context.contentResolver,
        "enabled_notification_listeners"
    ) ?: return false
    return enabled.contains(context.packageName, ignoreCase = true)
}
