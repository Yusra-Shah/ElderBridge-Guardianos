package com.elderbridge.guardianos.ui.screens

import android.content.Intent
import android.os.Build
import android.provider.Settings
import android.widget.Toast
import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.elderbridge.guardianos.data.UserProfileStore
import com.elderbridge.guardianos.services.OverlayService
import com.elderbridge.guardianos.services.ScreenReaderService
import com.elderbridge.guardianos.ui.components.PremiumCard
import com.elderbridge.guardianos.ui.components.PremiumSwitch
import com.elderbridge.guardianos.ui.components.StatusHeroCard
import com.elderbridge.guardianos.ui.state.SystemStatus
import com.elderbridge.guardianos.ui.theme.*

@Composable
fun HomeScreen(onTryDemo: () -> Unit, onHistory: () -> Unit, onProfile: () -> Unit) {
    val context = LocalContext.current
    var isMonitoringEnabled by remember { mutableStateOf(UserProfileStore.isAssistantEnabled(context)) }

    val status = if (isMonitoringEnabled) SystemStatus.ACTIVE else SystemStatus.OFF

    Scaffold(
        containerColor = BackgroundLight,
        bottomBar = {
            PremiumBottomNav(onHistory = onHistory, onProfile = onProfile)
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 24.dp, vertical = 32.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(28.dp)
        ) {
            // App header
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    text = "ElderBridge",
                    style = MaterialTheme.typography.displayLarge,
                    color = ElderBlue,
                    textAlign = TextAlign.Center,
                    fontWeight = FontWeight.Black
                )
                Text(
                    text = "Guardian Assistant",
                    style = MaterialTheme.typography.titleMedium,
                    color = TextSecondary,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.padding(top = 4.dp)
                )
            }

            // Status indicator + toggle (Premium version)
            StatusHeroCard(status = status)

            PremiumCard {
                Row(
                    modifier = Modifier
                        .fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(modifier = Modifier.weight(1f).padding(end = 16.dp)) {
                        Text(
                            text = "Assistant Monitoring",
                            style = MaterialTheme.typography.titleLarge,
                            color = TextPrimary,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = if (isMonitoringEnabled)
                                "Active — I am watching over your apps"
                            else
                                "Tap the switch to turn me on",
                            style = MaterialTheme.typography.bodyMedium,
                            color = if (isMonitoringEnabled) ActiveGreen else TextSecondary,
                            modifier = Modifier.padding(top = 6.dp)
                        )
                    }
                    PremiumSwitch(
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
                                        UserProfileStore.setAssistantEnabled(context, true)
                                        isMonitoringEnabled = true
                                    }
                                }
                            } else {
                                context.stopService(Intent(context, OverlayService::class.java))
                                UserProfileStore.setAssistantEnabled(context, false)
                                isMonitoringEnabled = false
                            }
                        }
                    )
                }
            }

            // Demo entry point
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                PremiumCard(onClick = onTryDemo) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            modifier = Modifier
                                .size(56.dp)
                                .background(ElderBluePale, CircleShape),
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(Icons.Default.Lightbulb, null, tint = ElderBlue)
                        }
                        Spacer(Modifier.width(16.dp))
                        Column(modifier = Modifier.weight(1f)) {
                            Text("Try a Demo", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                            Text("See how the assistant explains forms", style = MaterialTheme.typography.bodyMedium, color = TextSecondary)
                        }
                        Icon(Icons.Default.ChevronRight, null, tint = TextSecondary)
                    }
                }
            }
        }
    }
}

@Composable
private fun PremiumBottomNav(onHistory: () -> Unit, onProfile: () -> Unit) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .height(90.dp)
            .clip(RoundedCornerShape(topStart = 32.dp, topEnd = 32.dp)),
        color = SurfaceLight,
        shadowElevation = 24.dp
    ) {
        Row(
            modifier = Modifier.fillMaxSize(),
            horizontalArrangement = Arrangement.SpaceEvenly,
            verticalAlignment = Alignment.CenterVertically
        ) {
            IconButton(onClick = {}, modifier = Modifier.weight(1f)) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(Icons.Default.Home, null, tint = ElderBlue)
                    Text("Home", style = MaterialTheme.typography.labelSmall, color = ElderBlue)
                }
            }
            IconButton(onClick = onHistory, modifier = Modifier.weight(1f)) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(Icons.Default.History, null, tint = TextSecondary)
                    Text("History", style = MaterialTheme.typography.labelSmall, color = TextSecondary)
                }
            }
            IconButton(onClick = onProfile, modifier = Modifier.weight(1f)) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(Icons.Default.Person, null, tint = TextSecondary)
                    Text("Profile", style = MaterialTheme.typography.labelSmall, color = TextSecondary)
                }
            }
        }
    }
}
