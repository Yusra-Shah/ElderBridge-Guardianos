package com.elderbridge.guardianos.ui.screens

import androidx.compose.foundation.Image
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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.elderbridge.guardianos.R
import com.elderbridge.guardianos.ui.theme.EbSage
import com.elderbridge.guardianos.ui.theme.EbSurface

private data class OnboardingPage(
    val title: String,
    val body: String
)

private val pages = listOf(
    OnboardingPage(
        title = "Welcome to ElderBridge",
        body = "We help you understand health forms, government letters, and benefits, right on your phone."
    ),
    OnboardingPage(
        title = "We Explain Things",
        body = "When you open a confusing form or letter, we show a simple explanation in plain language."
    ),
    OnboardingPage(
        title = "Your Privacy is Safe",
        body = "We never read your passwords or security codes. Your personal information never leaves your phone."
    ),
    OnboardingPage(
        title = "You are Always in Control",
        body = "You can turn off the assistant at any time with a single tap on your home screen."
    )
)

@Composable
fun OnboardingScreen(onFinished: () -> Unit) {
    var currentPage by remember { mutableIntStateOf(0) }
    val page = pages[currentPage]

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(horizontal = 28.dp, vertical = 56.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.SpaceBetween
    ) {
        // Progress dots
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            pages.indices.forEach { i ->
                Box(
                    modifier = Modifier
                        .size(if (i == currentPage) 14.dp else 8.dp)
                        .background(
                            color = if (i == currentPage) MaterialTheme.colorScheme.primary
                            else MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.3f),
                            shape = RoundedCornerShape(50)
                        )
                )
            }
        }

        // Main content
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.padding(vertical = 16.dp)
        ) {
            Image(
                painter = painterResource(R.drawable.ic_elderbridge_logo),
                contentDescription = "ElderBridge",
                modifier = Modifier
                    .size(80.dp)
                    .padding(bottom = 36.dp)
            )
            Text(
                text = page.title,
                style = MaterialTheme.typography.headlineLarge,
                color = MaterialTheme.colorScheme.onBackground,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(bottom = 24.dp)
            )
            Text(
                text = page.body,
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center
            )
        }

        // Navigation
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Button(
                onClick = {
                    if (currentPage < pages.lastIndex) currentPage++ else onFinished()
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(64.dp),
                shape = RoundedCornerShape(16.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = EbSage,
                    contentColor = EbSurface
                )
            ) {
                Text(
                    text = if (currentPage < pages.lastIndex) "Next" else "Get Started",
                    style = MaterialTheme.typography.labelLarge
                )
            }

            if (currentPage < pages.lastIndex) {
                Spacer(modifier = Modifier.height(16.dp))
                TextButton(
                    onClick = onFinished,
                    modifier = Modifier.height(56.dp)
                ) {
                    Text(
                        text = "Skip",
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }
    }
}
