package com.elderbridge.guardianos.ui.screens

import android.content.Intent
import android.os.Build
import android.provider.Settings
import android.widget.Toast
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.spring
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.elderbridge.guardianos.R
import com.elderbridge.guardianos.data.UserProfileStore
import com.elderbridge.guardianos.services.OverlayService
import com.elderbridge.guardianos.services.ScreenReaderService
import com.elderbridge.guardianos.ui.theme.EbClay
import com.elderbridge.guardianos.ui.theme.EbInkSoft
import com.elderbridge.guardianos.ui.theme.EbNavy
import com.elderbridge.guardianos.ui.theme.EbSage
import com.elderbridge.guardianos.ui.theme.EbSurface
import com.elderbridge.guardianos.ui.theme.EbSurfaceAlt
import com.elderbridge.guardianos.ui.theme.NunitoFamily

@Composable
fun HomeScreen(onTryDemo: () -> Unit, onHistory: () -> Unit, onProfile: () -> Unit) {
    val context = LocalContext.current
    var isMonitoringEnabled by remember { mutableStateOf(UserProfileStore.isAssistantEnabled(context)) }
    val userName = remember { UserProfileStore.load(context).fullName.ifBlank { "friend" } }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 24.dp)
    ) {
        Spacer(modifier = Modifier.height(56.dp))

        // Top row: wordmark + settings
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Image(
                    painter = painterResource(R.drawable.ic_elderbridge_logo),
                    contentDescription = "ElderBridge logo",
                    modifier = Modifier.size(36.dp)
                )
                Spacer(modifier = Modifier.width(10.dp))
                Text(
                    text = "ElderBridge",
                    fontFamily = NunitoFamily,
                    fontWeight = FontWeight.ExtraBold,
                    fontSize = 24.sp,
                    color = MaterialTheme.colorScheme.onBackground
                )
            }
            IconButton(
                onClick = onProfile,
                modifier = Modifier.size(56.dp)
            ) {
                Icon(
                    painter = painterResource(android.R.drawable.ic_menu_preferences),
                    contentDescription = "Settings",
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.size(24.dp)
                )
            }
        }

        Spacer(modifier = Modifier.height(32.dp))

        // Greeting
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                contentAlignment = Alignment.Center,
                modifier = Modifier
                    .size(52.dp)
                    .clip(CircleShape)
                    .background(MaterialTheme.colorScheme.surfaceVariant)
            ) {
                Text(
                    text = userName.first().uppercase(),
                    fontFamily = NunitoFamily,
                    fontWeight = FontWeight.Bold,
                    fontSize = 22.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            Spacer(modifier = Modifier.width(16.dp))
            Column {
                Text(
                    text = "Hello, $userName",
                    style = MaterialTheme.typography.headlineLarge,
                    color = MaterialTheme.colorScheme.onBackground
                )
                Text(
                    text = "I am watching out for you.",
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 4.dp)
                )
            }
        }

        Spacer(modifier = Modifier.height(32.dp))

        // Main status card with toggle
        Card(
            modifier = Modifier
                .fillMaxWidth()
                .shadow(
                    elevation = 8.dp,
                    shape = RoundedCornerShape(24.dp),
                    ambientColor = EbSage.copy(alpha = 0.15f),
                    spotColor = EbSage.copy(alpha = 0.1f)
                ),
            shape = RoundedCornerShape(24.dp),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        ) {
            Column(
                modifier = Modifier.padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column(modifier = Modifier.weight(1f).padding(end = 16.dp)) {
                        Text(
                            text = if (isMonitoringEnabled)
                                "Assistant is watching"
                            else
                                "Assistant is resting",
                            style = MaterialTheme.typography.titleLarge,
                            color = MaterialTheme.colorScheme.onSurface
                        )
                        Text(
                            text = if (isMonitoringEnabled)
                                "Your screens are being looked after."
                            else
                                "Tap the switch to turn me on.",
                            style = MaterialTheme.typography.bodyLarge,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(top = 8.dp)
                        )
                    }
                    ElderBridgeToggle(
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
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Reassurance
        Text(
            text = "You are protected on every screen.",
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(horizontal = 8.dp)
        )

        Spacer(modifier = Modifier.height(32.dp))

        // Navigation buttons
        LargeNavButton(
            label = "History",
            iconResId = android.R.drawable.ic_menu_recent_history,
            color = EbNavy,
            onClick = onHistory
        )
        Spacer(modifier = Modifier.height(12.dp))
        LargeNavButton(
            label = "Profile",
            iconResId = android.R.drawable.ic_menu_my_calendar,
            color = EbClay,
            onClick = onProfile
        )

        Spacer(modifier = Modifier.height(24.dp))

        // Footer
        Text(
            text = "ElderBridge GuardianOS",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.align(Alignment.CenterHorizontally)
        )
        Spacer(modifier = Modifier.height(24.dp))
    }
}

@Composable
private fun ElderBridgeToggle(checked: Boolean, onCheckedChange: (Boolean) -> Unit) {
    val trackColor by animateColorAsState(
        targetValue = if (checked) EbSage else EbSurfaceAlt,
        animationSpec = spring(),
        label = "track"
    )
    val thumbColor by animateColorAsState(
        targetValue = if (checked) EbSurface else EbInkSoft,
        animationSpec = spring(),
        label = "thumb"
    )

    Box(
        modifier = Modifier
            .width(96.dp)
            .height(56.dp)
            .clip(RoundedCornerShape(28.dp))
            .background(trackColor)
            .clickable(
                interactionSource = remember { MutableInteractionSource() },
                indication = null
            ) { onCheckedChange(!checked) },
        contentAlignment = Alignment.CenterStart
    ) {
        Box(
            modifier = Modifier
                .offset(x = if (checked) 44.dp else 4.dp)
                .size(48.dp)
                .clip(CircleShape)
                .background(thumbColor)
        )
    }
}

@Composable
private fun LargeNavButton(label: String, iconResId: Int, color: Color, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .height(64.dp)
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
    ) {
        Row(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 20.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                painter = painterResource(iconResId),
                contentDescription = null,
                tint = color,
                modifier = Modifier.size(24.dp)
            )
            Spacer(modifier = Modifier.width(16.dp))
            Text(
                text = label,
                style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.onSurface
            )
        }
    }
}
