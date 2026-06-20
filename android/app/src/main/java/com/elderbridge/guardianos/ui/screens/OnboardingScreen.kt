package com.elderbridge.guardianos.ui.screens

import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.interaction.collectIsPressedAsState
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.elderbridge.guardianos.speech.SpeechManager
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
            .background(BackgroundLight)
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 24.dp, vertical = 32.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // Top Progress Section
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.fillMaxWidth()
            ) {
                LinearProgressIndicator(
                    progress = { state.progress },
                    modifier = Modifier
                        .weight(1f)
                        .height(12.dp)
                        .clip(CircleShape),
                    color = ElderBlue,
                    trackColor = ElderBlueLight,
                    strokeCap = StrokeCap.Round
                )
                Spacer(modifier = Modifier.width(16.dp))
                Text(
                    text = "${state.currentPageIndex + 1}/${state.pages.size}",
                    style = MaterialTheme.typography.labelLarge,
                    color = TextSecondary,
                    fontWeight = FontWeight.Bold
                )
            }

            Spacer(modifier = Modifier.height(24.dp))

            // TTS Hint / Accessibility Button
            Surface(
                onClick = { 
                    currentPage?.let { 
                        SpeechManager.speak("${it.title}. ${it.description}") 
                    }
                },
                shape = RoundedCornerShape(16.dp),
                color = ElderBlueLight.copy(alpha = 0.5f),
                modifier = Modifier.align(Alignment.Start)
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(Icons.Default.VolumeUp, contentDescription = null, tint = ElderBlue, modifier = Modifier.size(20.dp))
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Read Aloud", style = MaterialTheme.typography.labelMedium, color = ElderBlue)
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Main Content Area with Animations
            Box(modifier = Modifier.weight(1f)) {
                AnimatedContent(
                    targetState = state.currentPageIndex,
                    transitionSpec = {
                        if (targetState > initialState) {
                            (slideInHorizontally { width -> width } + fadeIn()).togetherWith(slideOutHorizontally { width -> -width } + fadeOut())
                        } else {
                            (slideInHorizontally { width -> -width } + fadeIn()).togetherWith(slideOutHorizontally { width -> width } + fadeOut())
                        }.using(SizeTransform(clip = false))
                    },
                    label = "pageTransition"
                ) { targetIndex ->
                    val page = state.pages[targetIndex]
                    OnboardingCard(page = page)
                }
            }

            Spacer(modifier = Modifier.height(32.dp))

            // Navigation Controls
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Back/Skip
                if (state.currentPageIndex > 0) {
                    TextButton(
                        onClick = { vm.previousPage() },
                        modifier = Modifier.height(56.dp)
                    ) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = null)
                        Spacer(modifier = Modifier.width(8.dp))
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

                // Next / Get Started
                val interactionSource = remember { androidx.compose.foundation.interaction.MutableInteractionSource() }
                val isPressed by interactionSource.collectIsPressedAsState()
                val buttonScale by animateFloatAsState(if (isPressed) 0.95f else 1f, label = "buttonScale")

                Button(
                    onClick = { vm.nextPage(onFinished) },
                    interactionSource = interactionSource,
                    modifier = Modifier
                        .height(64.dp)
                        .widthIn(min = 160.dp)
                        .scale(buttonScale),
                    shape = RoundedCornerShape(20.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (state.isLastPage) ActiveGreen else ElderBlue
                    ),
                    elevation = ButtonDefaults.buttonElevation(defaultElevation = 4.dp)
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            text = if (state.isLastPage) "Get Started" else "Next",
                            style = MaterialTheme.typography.labelLarge,
                            fontWeight = FontWeight.Bold,
                            fontSize = 20.sp
                        )
                        if (!state.isLastPage) {
                            Spacer(modifier = Modifier.width(8.dp))
                            Icon(Icons.AutoMirrored.Filled.ArrowForward, contentDescription = null)
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun OnboardingCard(page: OnboardingPageUiModel) {
    Card(
        modifier = Modifier.fillMaxSize(),
        shape = RoundedCornerShape(32.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceLight),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(32.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            // Large Illustration Placeholder
            Box(
                modifier = Modifier
                    .size(180.dp)
                    .background(ElderBlueLight, CircleShape),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = page.illustrationEmoji,
                    fontSize = 80.sp
                )
            }

            Spacer(modifier = Modifier.height(48.dp))

            Text(
                text = page.title,
                style = MaterialTheme.typography.headlineLarge,
                fontWeight = FontWeight.ExtraBold,
                color = TextPrimary,
                textAlign = TextAlign.Center,
                lineHeight = 40.sp
            )

            Spacer(modifier = Modifier.height(24.dp))

            Text(
                text = page.description,
                style = MaterialTheme.typography.bodyLarge,
                color = TextSecondary,
                textAlign = TextAlign.Center,
                lineHeight = 32.sp,
                fontSize = 20.sp
            )
        }
    }
}
