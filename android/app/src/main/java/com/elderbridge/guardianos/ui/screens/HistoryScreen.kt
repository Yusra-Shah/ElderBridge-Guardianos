package com.elderbridge.guardianos.ui.screens

import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.elderbridge.guardianos.data.HistoryEntry
import com.elderbridge.guardianos.data.HistoryStore
import com.elderbridge.guardianos.ui.components.*
import com.elderbridge.guardianos.ui.theme.*
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HistoryScreen(onBack: () -> Unit) {
    val entries = remember { HistoryStore.getEntries() }

    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = { 
                    Text(
                        text = "Response History",
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.Bold
                    ) 
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back", tint = ElderBlue)
                    }
                },
                colors = TopAppBarDefaults.centerAlignedTopAppBarColors(
                    containerColor = Color.Transparent
                )
            )
        },
        containerColor = BackgroundLight
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            if (entries.isEmpty()) {
                AnimatedEmptyState(
                    title = "No history yet",
                    description = "Use the assistant to see responses here.",
                    emoji = "🛡️",
                    modifier = Modifier.fillMaxSize()
                )
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(horizontal = 24.dp, vertical = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(24.dp)
                ) {
                    item {
                        PremiumSectionHeader(
                            title = "Recent Activity",
                            subtitle = "Detailed logs of your screen protection"
                        )
                    }

                    itemsIndexed(entries, key = { _, it -> it.id }) { index, entry ->
                        HistoryEntryTimelineItem(
                            entry = entry,
                            isFirst = index == 0,
                            isLast = index == entries.lastIndex
                        )
                    }

                    item { Spacer(modifier = Modifier.height(32.dp)) }
                }
            }
        }
    }
}

@Composable
private fun HistoryEntryTimelineItem(
    entry: HistoryEntry,
    isFirst: Boolean,
    isLast: Boolean
) {
    var expanded by remember { mutableStateOf(false) }
    val isLong = entry.response.length > 100
    val hasScreen = entry.screenText.isNotBlank()

    // Entrance animation
    val visible = remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { visible.value = true }

    AnimatedVisibility(
        visible = visible.value,
        enter = slideInVertically(
            initialOffsetY = { 50 },
            animationSpec = spring(dampingRatio = Spring.DampingRatioMediumBouncy)
        ) + fadeIn(animationSpec = tween(500))
    ) {
        Row(modifier = Modifier.fillMaxWidth()) {
            // Timeline Rail
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                modifier = Modifier.width(32.dp)
            ) {
                Box(
                    modifier = Modifier
                        .width(2.dp)
                        .weight(if (isFirst) 0.1f else 1f)
                        .background(if (isFirst) Color.Transparent else Divider)
                )
                
                Box(
                    modifier = Modifier
                        .size(12.dp)
                        .background(getRiskColor(entry.riskLevel), CircleShape)
                )

                Box(
                    modifier = Modifier
                        .width(2.dp)
                        .weight(if (isLast) 0.1f else 1f)
                        .background(if (isLast) Color.Transparent else Divider)
                )
            }

            Spacer(modifier = Modifier.width(16.dp))

            // Premium Content Card
            PremiumCard(
                onClick = { expanded = !expanded },
                modifier = Modifier.weight(1f)
            ) {
                Column {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = formatTimestamp(entry.timestamp),
                            style = MaterialTheme.typography.labelMedium,
                            color = TextSecondary,
                            fontWeight = FontWeight.Medium
                        )
                        RiskBadge(riskLevel = entry.riskLevel)
                    }

                    Spacer(modifier = Modifier.height(16.dp))

                    Text(
                        text = if (expanded) entry.response
                               else if (isLong) entry.response.take(100) + "…"
                               else entry.response,
                        style = MaterialTheme.typography.bodyLarge,
                        color = TextPrimary,
                        lineHeight = 28.sp
                    )

                    AnimatedVisibility(
                        visible = expanded,
                        enter = expandVertically(animationSpec = spring(dampingRatio = Spring.DampingRatioLowBouncy)) + fadeIn(),
                        exit = shrinkVertically(animationSpec = spring(dampingRatio = Spring.DampingRatioLowBouncy)) + fadeOut()
                    ) {
                        Column {
                            if (hasScreen) {
                                Spacer(modifier = Modifier.height(20.dp))
                                HorizontalDivider(color = Divider.copy(alpha = 0.5f))
                                Spacer(modifier = Modifier.height(20.dp))
                                
                                Text(
                                    "CAPTURED TEXT",
                                    style = MaterialTheme.typography.labelSmall,
                                    fontWeight = FontWeight.Bold,
                                    color = ElderBlue,
                                    letterSpacing = 1.sp
                                )
                                Spacer(modifier = Modifier.height(8.dp))
                                Surface(
                                    color = BackgroundLight.copy(alpha = 0.5f),
                                    shape = RoundedCornerShape(12.dp),
                                    modifier = Modifier.fillMaxWidth()
                                ) {
                                    Text(
                                        text = entry.screenText,
                                        style = MaterialTheme.typography.bodyMedium,
                                        color = TextSecondary,
                                        modifier = Modifier.padding(12.dp)
                                    )
                                }
                            }
                        }
                    }

                    if (isLong || hasScreen) {
                        Spacer(modifier = Modifier.height(16.dp))

                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Icon(
                                imageVector = if (expanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                                contentDescription = null,
                                tint = ElderBlue,
                                modifier = Modifier.size(20.dp)
                            )
                            Spacer(modifier = Modifier.width(4.dp))
                            Text(
                                text = if (expanded) "Show Less" else "View Details",
                                style = MaterialTheme.typography.labelLarge,
                                color = ElderBlue,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                }
            }
        }
    }
}

private fun getRiskColor(riskLevel: String): Color {
    return when (riskLevel.lowercase()) {
        "stop_and_verify" -> ErrorRed
        "caution"         -> WarningAmber
        else              -> ActiveGreen
    }
}

private fun formatTimestamp(iso: String): String = runCatching {
    DateTimeFormatter
        .ofPattern("MMM d, h:mm a")
        .withZone(ZoneId.systemDefault())
        .format(Instant.parse(iso))
}.getOrDefault(iso)
