package com.elderbridge.guardianos.ui.screens

import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.elderbridge.guardianos.ui.state.SystemStatus
import com.elderbridge.guardianos.ui.viewmodel.HomeViewModel
import com.elderbridge.guardianos.ui.theme.*

@Composable
fun HomeScreen(
    onTryDemo: () -> Unit,
    onHistory: () -> Unit,
    onProfile: () -> Unit,
    vm: HomeViewModel = viewModel()
) {
    val context = LocalContext.current
    val state by vm.uiState.collectAsState()

    LaunchedEffect(Unit) {
        vm.loadInitialState(context)
    }

    val pulseScale by animateFloatAsState(
        targetValue = when (state.systemStatus) {
            SystemStatus.ACTIVE -> 1.04f
            SystemStatus.ANALYZING -> 1.08f
            SystemStatus.SCAM_DETECTED -> 1.12f
            SystemStatus.OFF -> 1f
        },
        animationSpec = infiniteRepeatable(
            animation = tween(1500, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "pulse"
    )

    Scaffold(
        containerColor = BackgroundLight,
        bottomBar = {
            HomeBottomNavigation(onHistory = onHistory, onProfile = onProfile)
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 24.dp, vertical = 20.dp),
            verticalArrangement = Arrangement.spacedBy(28.dp)
        ) {
            // HEADER SECTION
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column {
                    Text(
                        text = "ElderBridge",
                        style = MaterialTheme.typography.displayMedium,
                        color = ElderBlue,
                        fontWeight = FontWeight.ExtraBold
                    )
                    Text(
                        text = "Guardian Assistant",
                        style = MaterialTheme.typography.titleMedium,
                        color = TextSecondary
                    )
                }
                
                Surface(
                    onClick = onProfile,
                    shape = CircleShape,
                    color = ElderBlueLight,
                    modifier = Modifier.size(56.dp)
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Icon(Icons.Default.Person, contentDescription = "Profile", tint = ElderBlue, modifier = Modifier.size(32.dp))
                    }
                }
            }

            // STATUS CORE CARD
            MainStatusCard(state.systemStatus, pulseScale)

            // ENABLE/DISABLE TOGGLE SECTION
            AssistantToggleCard(
                isEnabled = state.isMonitoringEnabled,
                onToggle = { vm.toggleAssistant(context, it) }
            )

            // CTA SECTION
            DemoActionCard(onTryDemo)
            
            Spacer(modifier = Modifier.weight(1f))
        }
    }
}

@Composable
private fun MainStatusCard(status: SystemStatus, pulseScale: Float) {
    val containerColor = when (status) {
        SystemStatus.ACTIVE -> ActiveGreenLight
        SystemStatus.ANALYZING -> ElderBlueLight
        SystemStatus.SCAM_DETECTED -> ErrorRedLight
        SystemStatus.OFF -> SurfaceLight
    }

    val iconColor = when (status) {
        SystemStatus.ACTIVE -> ActiveGreen
        SystemStatus.ANALYZING -> ElderBlue
        SystemStatus.SCAM_DETECTED -> ErrorRed
        SystemStatus.OFF -> TextSecondary
    }

    val statusText = when (status) {
        SystemStatus.ACTIVE -> "Assistant Active"
        SystemStatus.ANALYZING -> "Scanning Screen..."
        SystemStatus.SCAM_DETECTED -> "Potential Scam Detected!"
        SystemStatus.OFF -> "Protection is Disabled"
    }

    val statusIcon = when (status) {
        SystemStatus.ACTIVE -> Icons.Default.Shield
        SystemStatus.ANALYZING -> Icons.Default.Search
        SystemStatus.SCAM_DETECTED -> Icons.Default.ReportProblem
        SystemStatus.OFF -> Icons.Default.ShieldMoon
    }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .height(260.dp),
        shape = RoundedCornerShape(32.dp),
        colors = CardDefaults.cardColors(containerColor = containerColor),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(
            modifier = Modifier.fillMaxSize(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Box(
                contentAlignment = Alignment.Center,
                modifier = Modifier
                    .size(140.dp)
                    .scale(pulseScale)
                    .background(
                        brush = Brush.radialGradient(
                            colors = listOf(iconColor.copy(alpha = 0.2f), Color.Transparent)
                        ),
                        shape = CircleShape
                    )
            ) {
                Surface(
                    shape = CircleShape,
                    color = iconColor,
                    modifier = Modifier.size(100.dp),
                    shadowElevation = 6.dp
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Icon(
                            imageVector = statusIcon,
                            contentDescription = null,
                            tint = Color.White,
                            modifier = Modifier.size(48.dp)
                        )
                    }
                }
            }

            Spacer(Modifier.height(24.dp))

            Text(
                text = statusText,
                style = MaterialTheme.typography.headlineMedium,
                color = iconColor,
                fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Center
            )
        }
    }
}

@Composable
private fun AssistantToggleCard(isEnabled: Boolean, onToggle: (Boolean) -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceLight),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        border = if (!isEnabled) CardDefaults.outlinedCardBorder() else null
    ) {
        Row(
            modifier = Modifier
                .padding(24.dp)
                .fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(48.dp)
                    .background(if (isEnabled) ActiveGreenLight else BackgroundLight, CircleShape),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = if (isEnabled) Icons.Default.LockOpen else Icons.Default.Lock,
                    contentDescription = null,
                    tint = if (isEnabled) ActiveGreen else TextSecondary
                )
            }

            Spacer(modifier = Modifier.width(16.dp))

            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = "Shield Protection",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    text = if (isEnabled) "You are protected" else "Tap to turn on",
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextSecondary
                )
            }

            Switch(
                checked = isEnabled,
                onCheckedChange = onToggle,
                colors = SwitchDefaults.colors(
                    checkedThumbColor = Color.White,
                    checkedTrackColor = ActiveGreen,
                    uncheckedThumbColor = TextSecondary,
                    uncheckedTrackColor = BackgroundLight
                )
            )
        }
    }
}

@Composable
private fun DemoActionCard(onTryDemo: () -> Unit) {
    Surface(
        onClick = onTryDemo,
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(24.dp),
        color = ElderBlue,
        shadowElevation = 4.dp
    ) {
        Row(
            modifier = Modifier.padding(24.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(Icons.Default.Lightbulb, contentDescription = null, tint = Color.White, modifier = Modifier.size(32.dp))
            Spacer(Modifier.width(16.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = "Learn with Demo",
                    style = MaterialTheme.typography.titleLarge,
                    color = Color.White,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    text = "Practice recognizing scams",
                    style = MaterialTheme.typography.bodyMedium,
                    color = Color.White.copy(alpha = 0.8f)
                )
            }
            Icon(
                imageVector = Icons.AutoMirrored.Filled.ArrowForward,
                contentDescription = null,
                tint = Color.White
            )
        }
    }
}

@Composable
private fun HomeBottomNavigation(onHistory: () -> Unit, onProfile: () -> Unit) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .height(100.dp)
            .clip(RoundedCornerShape(topStart = 32.dp, topEnd = 32.dp)),
        color = SurfaceLight,
        shadowElevation = 16.dp
    ) {
        Row(
            modifier = Modifier.fillMaxSize(),
            horizontalArrangement = Arrangement.SpaceEvenly,
            verticalAlignment = Alignment.CenterVertically
        ) {
            NavigationItem(icon = Icons.Default.Home, label = "Home", isSelected = true, onClick = {})
            NavigationItem(icon = Icons.Default.History, label = "History", isSelected = false, onClick = onHistory)
            NavigationItem(icon = Icons.Default.ManageAccounts, label = "Profile", isSelected = false, onClick = onProfile)
        }
    }
}

@Composable
private fun NavigationItem(icon: ImageVector, label: String, isSelected: Boolean, onClick: () -> Unit) {
    val tint = if (isSelected) ElderBlue else TextSecondary
    
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier
            .clip(RoundedCornerShape(12.dp))
            .clickable(onClick = onClick)
            .padding(8.dp)
    ) {
        Icon(icon, contentDescription = label, tint = tint, modifier = Modifier.size(32.dp))
        Text(text = label, color = tint, style = MaterialTheme.typography.labelLarge, fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal)
    }
}
