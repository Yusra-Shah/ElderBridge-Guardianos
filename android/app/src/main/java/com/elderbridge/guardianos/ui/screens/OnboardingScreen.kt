package com.elderbridge.guardianos.ui.screens

import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.elderbridge.guardianos.speech.SpeechManager
import com.elderbridge.guardianos.ui.components.PremiumButton
import com.elderbridge.guardianos.ui.components.PremiumCard
import com.elderbridge.guardianos.ui.state.OnboardingPageUiModel
import com.elderbridge.guardianos.ui.viewmodel.OnboardingViewModel
import com.elderbridge.guardianos.ui.theme.*

@Composable
fun OnboardingScreen(
    onFinished: () -> Unit,
    vm: OnboardingViewModel = viewModel()
) {
    val state by vm.uiState.collectAsState()
    val currentPage = state.pages.getOrNull(state.currentPageIndex)

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    colors = listOf(ElderBluePale, BackgroundLight)
                )
            )
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 24.dp, vertical = 32.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // Top Progress Dots (Reconciled with original design)
            Row(
                horizontalArrangement = Arrangement.spacedBy(10.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                state.pages.indices.forEach { i ->
                    val isSelected = i == state.currentPageIndex
                    val size by animateDpAsState(if (isSelected) 14.dp else 8.dp, label = "dotSize")
                    val color = if (isSelected) ElderBlue else TextSecondary.copy(alpha = 0.3f)
                    
                    Box(
                        modifier = Modifier
                            .size(size)
                            .background(color, CircleShape)
                    )
                }
            }

            Spacer(modifier = Modifier.height(24.dp))

            // Accessibility: Read Aloud
            Surface(
                onClick = { 
                    currentPage?.let { 
                        SpeechManager.speak("${it.title}. ${it.body}") 
                    }
                },
                shape = RoundedCornerShape(16.dp),
                color = ElderBlue.copy(alpha = 0.08f),
                modifier = Modifier.align(Alignment.Start)
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 14.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(Icons.Default.VolumeUp, null, tint = ElderBlue, modifier = Modifier.size(20.dp))
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Read Aloud", style = MaterialTheme.typography.labelMedium, color = ElderBlue)
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Animated Paging Content
            Box(modifier = Modifier.weight(1f)) {
                AnimatedContent(
                    targetState = state.currentPageIndex,
                    transitionSpec = {
                        if (targetState > initialState) {
                            (slideInHorizontally { width -> width / 2 } + fadeIn()).togetherWith(slideOutHorizontally { width -> -width / 2 } + fadeOut())
                        } else {
                            (slideInHorizontally { width -> -width / 2 } + fadeIn()).togetherWith(slideOutHorizontally { width -> width / 2 } + fadeOut())
                        }.using(SizeTransform(clip = false))
                    },
                    label = "page"
                ) { targetIndex ->
                    val page = state.pages[targetIndex]
                    PremiumOnboardingCard(page = page)
                }
            }

            Spacer(modifier = Modifier.height(32.dp))

            // Navigation Buttons (Reconciled with original logic)
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                if (state.currentPageIndex > 0) {
                    TextButton(
                        onClick = { vm.previousPage() },
                        modifier = Modifier.height(56.dp)
                    ) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, null)
                        Spacer(Modifier.width(8.dp))
                        Text("Back", fontSize = 18.sp)
                    }
                } else {
                    TextButton(
                        onClick = onFinished,
                        modifier = Modifier.height(56.dp)
                    ) {
                        Text("Skip", fontSize = 18.sp, color = TextSecondary)
                    }
                }

                PremiumButton(
                    text = if (state.isLastPage) "Get Started" else "Next",
                    onClick = { vm.nextPage(onFinished) },
                    modifier = Modifier.widthIn(min = 160.dp),
                    containerColor = if (state.isLastPage) Brush.verticalGradient(listOf(ActiveGreen, Color(0xFF1B5E20))) else null
                )
            }
        }
    }
}

@Composable
private fun PremiumOnboardingCard(page: OnboardingPageUiModel) {
    val infiniteTransition = rememberInfiniteTransition(label = "bounce")
    val emojiScale by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 1.15f,
        animationSpec = infiniteRepeatable(tween(1500, easing = FastOutSlowInEasing), RepeatMode.Reverse),
        label = "emoji"
    )

    PremiumCard(modifier = Modifier.fillMaxSize()) {
        Column(
            modifier = Modifier.fillMaxSize(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Box(
                modifier = Modifier
                    .size(180.dp)
                    .background(ElderBluePale, CircleShape),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = page.emoji,
                    fontSize = 80.sp,
                    modifier = Modifier.scale(emojiScale)
                )
            }

            Spacer(modifier = Modifier.height(48.dp))

            Text(
                text = page.title,
                style = MaterialTheme.typography.displayLarge,
                color = TextPrimary,
                textAlign = TextAlign.Center,
                lineHeight = 38.sp
            )

            Spacer(modifier = Modifier.height(24.dp))

            Text(
                text = page.body,
                style = MaterialTheme.typography.bodyLarge,
                color = TextSecondary,
                textAlign = TextAlign.Center,
                lineHeight = 32.sp
            )
        }
    }
}
