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
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.elderbridge.guardianos.ui.components.*
import com.elderbridge.guardianos.ui.state.HistoryEventUiModel
import com.elderbridge.guardianos.ui.viewmodel.HistoryViewModel
import com.elderbridge.guardianos.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HistoryScreen(
    onBack: () -> Unit,
    vm: HistoryViewModel = viewModel()
) {
    val state by vm.uiState.collectAsState()

    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = { 
                    Text(
                        "Activity Timeline",
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
            if (state.isLoading) {
                CircularProgressIndicator(modifier = Modifier.align(Alignment.Center), color = ElderBlue)
            } else if (state.items.isEmpty()) {
                AnimatedEmptyState(
                    title = "Your history is clear",
                    description = "We'll keep track of your security scans right here.",
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

                    itemsIndexed(
                        items = state.items,
                        key = { _, item -> item.id }
                    ) { index, item ->
                        TimelineHistoryItem(
                            item = item,
                            isFirst = index == 0,
                            isLast = index == state.items.lastIndex,
                            onToggleExpand = { vm.toggleItemExpansion(item.id) }
                        )
                    }

                    item { Spacer(modifier = Modifier.height(32.dp)) }
                }
            }
        }
    }
}

@Composable
private fun TimelineHistoryItem(
    item: HistoryEventUiModel,
    isFirst: Boolean,
    isLast: Boolean,
    onToggleExpand: () -> Unit
) {
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
                        .background(item.riskColor, CircleShape)
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
                onClick = onToggleExpand,
                modifier = Modifier.weight(1f)
            ) {
                Column {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = item.relativeTime,
                            style = MaterialTheme.typography.labelMedium,
                            color = TextSecondary,
                            fontWeight = FontWeight.Medium
                        )
                        RiskBadge(riskLevel = item.riskLabel)
                    }

                    Spacer(modifier = Modifier.height(16.dp))

                    Text(
                        text = if (item.isExpanded) item.response else item.response.take(120) + "...",
                        style = MaterialTheme.typography.bodyLarge,
                        color = TextPrimary,
                        lineHeight = 28.sp
                    )

                    AnimatedVisibility(
                        visible = item.isExpanded,
                        enter = expandVertically(animationSpec = spring(dampingRatio = Spring.DampingRatioLowBouncy)) + fadeIn(),
                        exit = shrinkVertically(animationSpec = spring(dampingRatio = Spring.DampingRatioLowBouncy)) + fadeOut()
                    ) {
                        Column {
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
                                    text = item.screenText,
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = TextSecondary,
                                    modifier = Modifier.padding(12.dp)
                                )
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(16.dp))

                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Icon(
                            imageVector = if (item.isExpanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                            contentDescription = null,
                            tint = ElderBlue,
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(
                            text = if (item.isExpanded) "Show Less" else "View Details",
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
