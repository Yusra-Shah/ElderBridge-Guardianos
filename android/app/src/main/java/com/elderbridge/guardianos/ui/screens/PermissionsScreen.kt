package com.elderbridge.guardianos.ui.screens

import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Shield
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.viewmodel.compose.viewModel
import com.elderbridge.guardianos.ui.state.PermissionActionType
import com.elderbridge.guardianos.ui.state.PermissionItemUiModel
import com.elderbridge.guardianos.ui.viewmodel.PermissionsViewModel
import com.elderbridge.guardianos.ui.theme.*

@Composable
fun PermissionsScreen(
    onContinue: () -> Unit,
    vm: PermissionsViewModel = viewModel()
) {
    val context = LocalContext.current
    val state by vm.uiState.collectAsState()
    val lifecycleOwner = LocalLifecycleOwner.current

    // Auto-refresh permissions when user returns from Settings
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                vm.refreshStatus(context)
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    // Initial check
    LaunchedEffect(Unit) {
        vm.checkPermissions(context)
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(BackgroundLight)
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 24.dp, vertical = 32.dp)
                .verticalScroll(rememberScrollState()),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // Header Section
            Text(
                text = "Setup Your Protection",
                style = MaterialTheme.typography.headlineLarge,
                color = ElderBlue,
                fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Center
            )
            Spacer(modifier = Modifier.height(12.dp))
            Text(
                text = "Follow these 3 steps to help ElderBridge protect you from scams.",
                style = MaterialTheme.typography.bodyLarge,
                color = TextSecondary,
                textAlign = TextAlign.Center,
                lineHeight = 30.sp
            )

            Spacer(modifier = Modifier.height(32.dp))

            // Progress Dashboard
            SetupProgressCard(state)

            Spacer(modifier = Modifier.height(32.dp))

            // Guided Cards
            state.permissionItems.forEachIndexed { index, item ->
                SetupStepCard(
                    item = item,
                    stepNumber = index + 1,
                    onAction = {
                        when (item.actionType) {
                            PermissionActionType.ACCESSIBILITY -> vm.openAccessibilitySettings(context)
                            PermissionActionType.NOTIFICATION -> vm.openNotificationSettings(context)
                            PermissionActionType.OVERLAY -> vm.openOverlaySettings(context)
                        }
                    }
                )
                Spacer(modifier = Modifier.height(20.dp))
            }

            Spacer(modifier = Modifier.weight(1f))
            Spacer(modifier = Modifier.height(32.dp))

            // Final Action Button
            val interactionSource = remember { androidx.compose.foundation.interaction.MutableInteractionSource() }
            val isPressed by interactionSource.collectIsPressedAsState()
            val buttonScale by animateFloatAsState(if (isPressed) 0.95f else 1f, label = "buttonScale")

            Button(
                onClick = onContinue,
                interactionSource = interactionSource,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(64.dp)
                    .scale(buttonScale),
                shape = RoundedCornerShape(20.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = if (state.allGranted) ActiveGreen else ElderBlue
                ),
                elevation = ButtonDefaults.buttonElevation(defaultElevation = 4.dp)
            ) {
                Text(
                    text = if (state.allGranted) "Complete Setup" else "Continue Anyway",
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.Bold,
                    fontSize = 20.sp
                )
            }
        }
    }
}

@Composable
private fun SetupProgressCard(state: com.elderbridge.guardianos.ui.state.PermissionsUiState) {
    val animatedProgress by animateFloatAsState(
        targetValue = state.progress,
        animationSpec = spring(stiffness = Spring.StiffnessLow),
        label = "progress"
    )

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceLight),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(modifier = Modifier.padding(20.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "Setup Progress",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = TextPrimary
                )
                Text(
                    text = "${state.completedSteps} of ${state.totalSteps} steps",
                    style = MaterialTheme.typography.bodyMedium,
                    color = ElderBlue,
                    fontWeight = FontWeight.Bold
                )
            }
            Spacer(modifier = Modifier.height(16.dp))
            LinearProgressIndicator(
                progress = { animatedProgress },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(12.dp)
                    .clip(CircleShape),
                color = if (state.allGranted) ActiveGreen else ElderBlue,
                trackColor = ElderBlueLight,
                strokeCap = StrokeCap.Round
            )
        }
    }
}

@Composable
private fun SetupStepCard(
    item: PermissionItemUiModel,
    stepNumber: Int,
    onAction: () -> Unit
) {
    val cardBgColor by animateColorAsState(
        targetValue = if (item.isGranted) ActiveGreenLight else SurfaceLight,
        label = "cardBg"
    )

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = cardBgColor),
        elevation = CardDefaults.cardElevation(defaultElevation = if (item.isGranted) 0.dp else 2.dp),
        border = if (item.isGranted) null else CardDefaults.outlinedCardBorder()
    ) {
        Column(modifier = Modifier.padding(20.dp)) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.fillMaxWidth()
            ) {
                // Step Badge
                Surface(
                    color = if (item.isGranted) ActiveGreen else ElderBlueLight,
                    shape = CircleShape,
                    modifier = Modifier.size(40.dp)
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        if (item.isGranted) {
                            Icon(Icons.Default.Check, "Done", tint = Color.White, modifier = Modifier.size(24.dp))
                        } else {
                            Text("$stepNumber", color = ElderBlue, fontWeight = FontWeight.Bold, fontSize = 20.sp)
                        }
                    }
                }
                
                Spacer(modifier = Modifier.width(16.dp))
                
                Text(
                    text = item.title,
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold,
                    color = TextPrimary,
                    modifier = Modifier.weight(1f)
                )
                
                // Status Chip
                StatusChip(isGranted = item.isGranted)
            }

            Spacer(modifier = Modifier.height(12.dp))
            
            Text(
                text = item.description,
                style = MaterialTheme.typography.bodyLarge,
                color = if (item.isGranted) ActiveGreen.copy(alpha = 0.8f) else TextSecondary,
                lineHeight = 28.sp
            )

            if (!item.isGranted) {
                Spacer(modifier = Modifier.height(20.dp))
                Button(
                    onClick = onAction,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(64.dp),
                    shape = RoundedCornerShape(16.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = ElderBlue)
                ) {
                    Text("Enable Protection Step $stepNumber", fontSize = 18.sp, fontWeight = FontWeight.Bold)
                    Spacer(modifier = Modifier.width(8.dp))
                    Icon(Icons.Default.ChevronRight, null)
                }
            }
        }
    }
}

@Composable
private fun StatusChip(isGranted: Boolean) {
    Surface(
        color = if (isGranted) ActiveGreenLight else Divider.copy(alpha = 0.3f),
        shape = RoundedCornerShape(50)
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(8.dp)
                    .background(if (isGranted) ActiveGreen else TextSecondary, CircleShape)
            )
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                text = if (isGranted) "Enabled" else "Pending",
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Bold,
                color = if (isGranted) ActiveGreen else TextSecondary
            )
        }
    }
}

