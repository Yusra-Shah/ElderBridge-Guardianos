package com.elderbridge.guardianos.ui.screens

import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Info
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.elderbridge.guardianos.ui.state.OverlayPreviewFieldUiModel
import com.elderbridge.guardianos.ui.state.OverlayPreviewUiState
import com.elderbridge.guardianos.ui.viewmodel.OverlayPreviewViewModel
import com.elderbridge.guardianos.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OverlayPreviewScreen(
    onBack: () -> Unit,
    vm: OverlayPreviewViewModel = viewModel()
) {
    val state by vm.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("How It Works", fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = ElderBlue,
                    titleContentColor = Color.White,
                    navigationIconContentColor = Color.White
                )
            )
        },
        containerColor = BackgroundLight
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .background(BackgroundLight)
                .verticalScroll(rememberScrollState())
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // Guided Progress Header
            ProgressHeader(state)

            Spacer(modifier = Modifier.height(32.dp))

            // Assistant Preview (Floating Bubble Section)
            AssistantPreviewSection()

            Spacer(modifier = Modifier.height(32.dp))

            // Step Indicator
            Text(
                text = "STEP ${state.currentStep}: ${if (state.expandedIndex != -1) "Reading Explanation" else "Tap the field"}",
                style = MaterialTheme.typography.labelLarge,
                color = ElderBlue,
                fontWeight = FontWeight.ExtraBold,
                letterSpacing = 2.sp
            )

            Spacer(modifier = Modifier.height(16.dp))

            // Main Interactive Content
            Box(modifier = Modifier.fillMaxWidth()) {
                if (state.isDemoComplete) {
                    DemoCompleteView(onReset = { vm.resetDemo() }, onExit = onBack)
                } else {
                    Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
                        state.fields.forEachIndexed { index, field ->
                            InteractiveFieldCard(
                                field = field,
                                isVisible = index < state.currentStep,
                                onClick = { vm.onFieldTapped(index) }
                            )
                        }
                    }
                }
            }

            // CTA for Next Step
            AnimatedVisibility(
                visible = state.expandedIndex != -1 && !state.isDemoComplete,
                enter = slideInVertically { it } + fadeIn(),
                exit = slideOutVertically { it } + fadeOut()
            ) {
                Spacer(modifier = Modifier.height(32.dp))
                Button(
                    onClick = { vm.nextStep() },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(64.dp),
                    shape = RoundedCornerShape(16.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = ActiveGreen)
                ) {
                    Text(
                        text = if (state.currentStep == state.totalSteps) "Finish Demo" else "Try Next Step",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold
                    )
                }
            }

            Spacer(modifier = Modifier.height(40.dp))
        }
    }
}

@Composable
private fun ProgressHeader(state: OverlayPreviewUiState) {
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
                    "Tutorial Progress",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    "${state.currentStep}/${state.totalSteps}",
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextSecondary
                )
            }
            Spacer(modifier = Modifier.height(12.dp))
            LinearProgressIndicator(
                progress = { state.progress },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(10.dp)
                    .clip(CircleShape),
                color = ElderBlue,
                trackColor = ElderBlueLight,
                strokeCap = StrokeCap.Round
            )
        }
    }
}

@Composable
private fun AssistantPreviewSection() {
    val infiniteTransition = rememberInfiniteTransition(label = "bubble")
    val scale by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 1.15f,
        animationSpec = infiniteRepeatable(
            animation = tween(1200, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "scale"
    )
    val glowAlpha by infiniteTransition.animateFloat(
        initialValue = 0.2f,
        targetValue = 0.6f,
        animationSpec = infiniteRepeatable(
            animation = tween(1200),
            repeatMode = RepeatMode.Reverse
        ),
        label = "glow"
    )

    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(20.dp),
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 8.dp)
    ) {
        Box(contentAlignment = Alignment.Center) {
            // Outer Glow
            Box(
                modifier = Modifier
                    .size(80.dp)
                    .scale(scale)
                    .background(ElderBlue.copy(alpha = glowAlpha), CircleShape)
            )
            // Bubble
            Box(
                modifier = Modifier
                    .size(64.dp)
                    .shadow(8.dp, CircleShape)
                    .background(ElderBlue, CircleShape),
                contentAlignment = Alignment.Center
            ) {
                Text("EB", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 20.sp)
            }
        }

        Column {
            Text(
                "Meet Your Assistant",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = TextPrimary
            )
            Text(
                "I float over any screen to help you read and understand forms.",
                style = MaterialTheme.typography.bodyMedium,
                color = TextSecondary,
                lineHeight = 22.sp
            )
        }
    }
}

@Composable
private fun InteractiveFieldCard(
    field: OverlayPreviewFieldUiModel,
    isVisible: Boolean,
    onClick: () -> Unit
) {
    val animatedScale by animateFloatAsState(if (field.isHighlighted) 1.02f else 1f, label = "scale")
    val borderAlpha by animateFloatAsState(if (field.isHighlighted) 1f else 0f, label = "border")

    AnimatedVisibility(
        visible = isVisible,
        enter = expandVertically() + fadeIn(),
        exit = shrinkVertically() + fadeOut()
    ) {
        Column {
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .scale(animatedScale)
                    .border(
                        width = 3.dp,
                        brush = Brush.linearGradient(
                            listOf(ElderBlue.copy(alpha = borderAlpha), Color.Transparent)
                        ),
                        shape = RoundedCornerShape(20.dp)
                    )
                    .clickable(onClick = onClick),
                shape = RoundedCornerShape(20.dp),
                colors = CardDefaults.cardColors(
                    containerColor = if (field.isExpanded) ElderBlueLight.copy(alpha = 0.4f) else SurfaceLight
                ),
                elevation = CardDefaults.cardElevation(if (field.isHighlighted) 4.dp else 1.dp)
            ) {
                Row(
                    modifier = Modifier.padding(20.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(
                        text = field.label,
                        style = MaterialTheme.typography.bodyLarge,
                        fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.weight(1f)
                    )
                    Icon(
                        imageVector = if (field.isExpanded) Icons.Default.Check else Icons.Default.Info,
                        contentDescription = null,
                        tint = if (field.isExpanded) ActiveGreen else ElderBlue,
                        modifier = Modifier.size(28.dp)
                    )
                }
            }

            AnimatedContent(
                targetState = field.isExpanded,
                transitionSpec = {
                    expandVertically(expandFrom = Alignment.Top) + fadeIn() togetherWith
                            shrinkVertically(shrinkTowards = Alignment.Top) + fadeOut()
                },
                label = "explanation"
            ) { isExpanded ->
                if (isExpanded) {
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(top = 8.dp),
                        shape = RoundedCornerShape(20.dp),
                        colors = CardDefaults.cardColors(containerColor = ElderBlueDark)
                    ) {
                        Column(modifier = Modifier.padding(20.dp)) {
                            Text(
                                "ElderBridge Explanation:",
                                style = MaterialTheme.typography.labelMedium,
                                color = ElderBlueLight,
                                fontWeight = FontWeight.Bold
                            )
                            Spacer(modifier = Modifier.height(8.dp))
                            Text(
                                text = field.explanation,
                                style = MaterialTheme.typography.bodyLarge,
                                color = Color.White,
                                lineHeight = 28.sp
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun DemoCompleteView(onReset: () -> Unit, onExit: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 32.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Box(
            modifier = Modifier
                .size(100.dp)
                .background(ActiveGreenLight, CircleShape),
            contentAlignment = Alignment.Center
        ) {
            Icon(Icons.Default.Check, contentDescription = null, tint = ActiveGreen, modifier = Modifier.size(60.dp))
        }
        Spacer(modifier = Modifier.height(24.dp))
        Text(
            "Demo Complete!",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold,
            color = TextPrimary
        )
        Text(
            "You are now ready to use the Guardian Assistant.",
            style = MaterialTheme.typography.bodyLarge,
            color = TextSecondary,
            textAlign = TextAlign.Center,
            modifier = Modifier.padding(top = 8.dp)
        )
        Spacer(modifier = Modifier.height(32.dp))
        Button(
            onClick = onExit,
            modifier = Modifier.fillMaxWidth().height(64.dp),
            shape = RoundedCornerShape(16.dp)
        ) {
            Text("Back to Home")
        }
        TextButton(onClick = onReset) {
            Text("Restart Tutorial")
        }
    }
}
