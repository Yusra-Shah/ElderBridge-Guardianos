package com.elderbridge.guardianos.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.elderbridge.guardianos.ui.theme.ElderBlue
import com.elderbridge.guardianos.ui.theme.ElderBlueDark
import com.elderbridge.guardianos.ui.theme.ElderBlueLight
import com.elderbridge.guardianos.ui.theme.TextOnPrimary

private data class MockField(val label: String, val explanation: String)

private val mockFields = listOf(
    MockField(
        label = "Monthly Income",
        explanation = "This field is asking for your total monthly income — the money you receive each month from all sources, such as Social Security, a pension, or part-time work."
    ),
    MockField(
        label = "Medicare Number",
        explanation = "This is your unique Medicare ID. You can find it printed on your red, white, and blue Medicare card — it is usually 11 characters long."
    ),
    MockField(
        label = "Proof of Residence",
        explanation = "This means they need a document that shows where you live, such as a utility bill, a bank statement, or a lease agreement with your address on it."
    )
)

@Composable
fun OverlayPreviewScreen(onBack: () -> Unit) {
    var expandedIndex by remember { mutableIntStateOf(-1) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .verticalScroll(rememberScrollState())
    ) {
        // Header bar
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(MaterialTheme.colorScheme.primary)
                .padding(horizontal = 16.dp, vertical = 20.dp)
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                TextButton(onClick = onBack) {
                    Text(
                        text = "← Back",
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onPrimary
                    )
                }
                Spacer(modifier = Modifier.width(4.dp))
                Text(
                    text = "Demo: How It Works",
                    style = MaterialTheme.typography.titleLarge,
                    color = MaterialTheme.colorScheme.onPrimary
                )
            }
        }

        Column(modifier = Modifier.padding(horizontal = 24.dp, vertical = 28.dp)) {
            Text(
                text = "Tap any field below to see how the assistant explains it.",
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onBackground,
                textAlign = TextAlign.Center,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 28.dp)
            )

            mockFields.forEachIndexed { index, field ->
                MockFormField(
                    field = field,
                    isExpanded = expandedIndex == index,
                    onTap = { expandedIndex = if (expandedIndex == index) -1 else index }
                )
                Spacer(modifier = Modifier.height(20.dp))
            }

            Spacer(modifier = Modifier.height(8.dp))
            HorizontalDivider()
            Spacer(modifier = Modifier.height(28.dp))

            Text(
                text = "The assistant bubble looks like this:",
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onBackground,
                modifier = Modifier.padding(bottom = 20.dp)
            )
            BubbleMockup()
        }
    }
}

@Composable
private fun MockFormField(field: MockField, isExpanded: Boolean, onTap: () -> Unit) {
    Column {
        Card(
            modifier = Modifier
                .fillMaxWidth()
                .clickable(onClick = onTap),
            shape = if (isExpanded)
                RoundedCornerShape(topStart = 12.dp, topEnd = 12.dp)
            else
                RoundedCornerShape(12.dp),
            colors = CardDefaults.cardColors(
                containerColor = if (isExpanded)
                    ElderBlueLight.copy(alpha = 0.12f)
                else
                    MaterialTheme.colorScheme.surface
            ),
            elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
        ) {
            Row(
                modifier = Modifier.padding(horizontal = 20.dp, vertical = 20.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = field.label,
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onBackground,
                    modifier = Modifier.weight(1f)
                )
                // The "?" bubble that mirrors the real floating bubble
                Box(
                    contentAlignment = Alignment.Center,
                    modifier = Modifier
                        .size(40.dp)
                        .clip(CircleShape)
                        .background(MaterialTheme.colorScheme.primary)
                ) {
                    Text(
                        text = if (isExpanded) "✕" else "?",
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onPrimary
                    )
                }
            }
        }

        AnimatedVisibility(
            visible = isExpanded,
            enter = expandVertically(),
            exit = shrinkVertically()
        ) {
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(bottomStart = 16.dp, bottomEnd = 16.dp),
                colors = CardDefaults.cardColors(containerColor = ElderBlueDark)
            ) {
                Column(modifier = Modifier.padding(20.dp)) {
                    Text(
                        text = "ElderBridge says:",
                        style = MaterialTheme.typography.bodyMedium,
                        color = ElderBlueLight,
                        modifier = Modifier.padding(bottom = 10.dp)
                    )
                    Text(
                        text = field.explanation,
                        style = MaterialTheme.typography.bodyLarge,
                        color = TextOnPrimary
                    )
                }
            }
        }
    }
}

@Composable
private fun BubbleMockup() {
    Row(
        horizontalArrangement = Arrangement.spacedBy(16.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Box(
            contentAlignment = Alignment.Center,
            modifier = Modifier
                .size(64.dp)
                .clip(CircleShape)
                .background(ElderBlue)
        ) {
            Text(text = "EB", style = MaterialTheme.typography.titleLarge, color = TextOnPrimary)
        }
        Column {
            Text(
                text = "Tap to get help",
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onBackground
            )
            Text(
                text = "This bubble floats on top of any app",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 4.dp)
            )
        }
    }
}
