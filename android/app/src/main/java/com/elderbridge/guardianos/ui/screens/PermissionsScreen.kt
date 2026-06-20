package com.elderbridge.guardianos.ui.screens

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.elderbridge.guardianos.ui.components.PremiumButton
import com.elderbridge.guardianos.ui.components.PremiumCard
import com.elderbridge.guardianos.ui.components.PremiumSectionHeader
import com.elderbridge.guardianos.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PermissionsScreen(onContinue: () -> Unit) {
    val context = LocalContext.current
    var refreshKey by remember { mutableIntStateOf(0) }

    val hasAccessibility = remember(refreshKey) { isScreenReaderEnabled(context) }
    val hasNotificationAccess = remember(refreshKey) { isNotificationAccessEnabled(context) }
    val hasOverlay = remember(refreshKey) { Settings.canDrawOverlays(context) }

    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = { 
                    Text(
                        "Permissions",
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.Bold
                    ) 
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
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(24.dp)
        ) {
            PremiumSectionHeader(
                title = "Allow Permissions",
                subtitle = "These let ElderBridge help you stay safe online"
            )

            PermissionStepCard(
                title = "Accessibility Service",
                description = "Lets us see what is on your screen so we can explain it to you.",
                isGranted = hasAccessibility,
                onEnable = {
                    context.startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
                }
            )

            PermissionStepCard(
                title = "Notification Access",
                description = "Lets us explain notifications from health and government apps.",
                isGranted = hasNotificationAccess,
                onEnable = {
                    context.startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
                }
            )

            PermissionStepCard(
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

            Spacer(modifier = Modifier.height(8.dp))

            TextButton(
                onClick = { refreshKey++ },
                modifier = Modifier.height(56.dp)
            ) {
                Icon(Icons.Default.Refresh, null)
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "Check status again",
                    style = MaterialTheme.typography.bodyMedium,
                    color = ElderBlue,
                    fontWeight = FontWeight.Bold
                )
            }

            PremiumButton(
                text = if (hasAccessibility && hasNotificationAccess && hasOverlay)
                    "Continue" else "Continue Anyway",
                onClick = onContinue,
                modifier = Modifier.fillMaxWidth()
            )
            
            Spacer(modifier = Modifier.height(24.dp))
        }
    }
}

@Composable
private fun PermissionStepCard(
    title: String,
    description: String,
    isGranted: Boolean,
    onEnable: () -> Unit
) {
    PremiumCard(modifier = Modifier.fillMaxWidth()) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
            modifier = Modifier.fillMaxWidth()
        ) {
            Text(
                text = title,
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = TextPrimary,
                modifier = Modifier.weight(1f)
            )
            Spacer(modifier = Modifier.width(12.dp))
            GrantedStatusChip(isGranted = isGranted)
        }
        Spacer(modifier = Modifier.height(12.dp))
        Text(
            text = description,
            style = MaterialTheme.typography.bodyLarge,
            color = TextSecondary,
            lineHeight = 28.sp
        )
        if (!isGranted) {
            Spacer(modifier = Modifier.height(20.dp))
            Button(
                onClick = onEnable,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(64.dp),
                shape = RoundedCornerShape(16.dp),
                colors = ButtonDefaults.buttonColors(containerColor = ElderBlue)
            ) {
                Text("Enable in Settings", fontSize = 18.sp, fontWeight = FontWeight.Bold)
            }
        }
    }
}

@Composable
private fun GrantedStatusChip(isGranted: Boolean) {
    Surface(
        color = if (isGranted) ActiveGreenLight else ErrorRed.copy(alpha = 0.1f),
        shape = RoundedCornerShape(50)
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(8.dp)
                    .background(if (isGranted) ActiveGreen else ErrorRed, androidx.compose.foundation.shape.CircleShape)
            )
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                text = if (isGranted) "Enabled" else "Pending",
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Bold,
                color = if (isGranted) ActiveGreen else ErrorRed
            )
        }
    }
}

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
