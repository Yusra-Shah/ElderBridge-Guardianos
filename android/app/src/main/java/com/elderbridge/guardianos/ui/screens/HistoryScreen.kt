package com.elderbridge.guardianos.ui.screens

import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
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
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.elderbridge.guardianos.ui.state.HistoryEventUiModel
import com.elderbridge.guardianos.ui.state.HistoryFilter
import com.elderbridge.guardianos.ui.state.HistoryStats
import com.elderbridge.guardianos.ui.viewmodel.HistoryViewModel
import com.elderbridge.guardianos.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HistoryScreen(
    onBack: () -> Unit,
    onTryDemo: () -> Unit = {},
    vm: HistoryViewModel = viewModel()
) {
    val state by vm.uiState.collectAsState()
    val focusManager = LocalFocusManager.current

    Scaffold(
        topBar = {
            TopAppBar(
                title = { 
                    Text(
                        text = "Activity Log", 
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.Bold
                    ) 
                },
                navigationIcon = {
                    IconButton(onClick = onBack, modifier = Modifier.size(56.dp)) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack, 
                            contentDescription = "Back",
                            modifier = Modifier.size(32.dp)
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = SurfaceLight,
                    titleContentColor = TextPrimary,
                    navigationIconContentColor = ElderBlue
                )
            )
        },
        containerColor = BackgroundLight
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            // SEARCH & FILTER HEADER
            Surface(
                color = SurfaceLight,
                shadowElevation = 2.dp,
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(horizontal = 24.dp, vertical = 16.dp)) {
                    // Modern Search Bar
                    OutlinedTextField(
                        value = state.searchQuery,
                        onValueChange = { vm.onSearchQueryChanged(it) },
                        placeholder = { Text("Search logs...", color = TextSecondary) },
                        modifier = Modifier.fillMaxWidth(),
                        leadingIcon = { 
                            Icon(Icons.Default.Search, "Search", tint = ElderBlue, modifier = Modifier.size(24.dp)) 
                        },
                        trailingIcon = {
                            if (state.searchQuery.isNotEmpty()) {
                                IconButton(onClick = { vm.onSearchQueryChanged("") }) {
                                    Icon(Icons.Default.Close, "Clear", tint = TextSecondary)
                                }
                            }
                        },
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = ElderBlue,
                            unfocusedBorderColor = Divider,
                            focusedContainerColor = BackgroundLight,
                            unfocusedContainerColor = BackgroundLight
                        ),
                        shape = RoundedCornerShape(16.dp),
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                        keyboardActions = KeyboardActions(onSearch = { focusManager.clearFocus() }),
                        singleLine = true
                    )

                    Spacer(modifier = Modifier.height(16.dp))

                    // Premium Filter Chips
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        HistoryFilter.entries.forEach { filter ->
                            val isSelected = state.currentFilter == filter
                            FilterChip(
                                selected = isSelected,
                                onClick = { vm.onFilterChanged(filter) },
                                label = { 
                                    Text(
                                        text = filter.name.replace("_", " ").lowercase().replaceFirstChar { it.uppercase() }, 
                                        style = MaterialTheme.typography.labelLarge
                                    ) 
                                },
                                colors = FilterChipDefaults.filterChipColors(
                                    selectedContainerColor = ElderBlue,
                                    selectedLabelColor = Color.White,
                                    containerColor = SurfaceLight,
                                    labelColor = TextSecondary
                                ),
                                border = if (isSelected) null else FilterChipDefaults.filterChipBorder(
                                    enabled = true,
                                    borderColor = Divider,
                                    selected = false
                                ),
                                shape = RoundedCornerShape(12.dp)
                            )
                        }
                    }
                }
            }

            // CONTENT
            Box(modifier = Modifier.fillMaxSize()) {
                if (state.isLoading) {
                    CircularProgressIndicator(modifier = Modifier.align(Alignment.Center), color = ElderBlue)
                } else if (state.items.isEmpty()) {
                    EmptyHistoryState(onTryDemo)
                } else {
                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = PaddingValues(24.dp),
                        verticalArrangement = Arrangement.spacedBy(20.dp)
                    ) {
                        item {
                            SummaryStatsSection(state.stats)
                        }

                        itemsIndexed(state.items, key = { _, item -> item.id }) { index, item ->
                            HistoryLogItem(
                                item = item,
                                index = index,
                                onToggleExpand = { vm.toggleItemExpansion(item.id) }
                            )
                        }
                        
                        item { Spacer(modifier = Modifier.height(40.dp)) }
                    }
                }
            }
        }
    }
}

@Composable
private fun SummaryStatsSection(stats: HistoryStats) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(containerColor = SurfaceLight),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
        border = CardDefaults.outlinedCardBorder()
    ) {
        Row(
            modifier = Modifier.padding(20.dp).fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            StatBox("Total", stats.totalScans.toString(), ElderBlue)
            VerticalDivider(modifier = Modifier.height(40.dp), thickness = 1.dp, color = Divider)
            StatBox("Safe", stats.safeCount.toString(), ActiveGreen)
            VerticalDivider(modifier = Modifier.height(40.dp), thickness = 1.dp, color = Divider)
            StatBox("Alerts", stats.scamCount.toString(), ErrorRed)
        }
    }
}

@Composable
private fun StatBox(label: String, value: String, color: Color) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(value, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Black, color = color)
        Text(label, style = MaterialTheme.typography.labelMedium, color = TextSecondary)
    }
}

@Composable
private fun HistoryLogItem(
    item: HistoryEventUiModel,
    index: Int,
    onToggleExpand: () -> Unit
) {
    val interactionSource = remember { androidx.compose.foundation.interaction.MutableInteractionSource() }
    val isPressed by interactionSource.collectIsPressedAsState()
    val scale by animateFloatAsState(if (isPressed) 0.98f else 1f, label = "press")

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .scale(scale)
            .clickable(
                interactionSource = interactionSource,
                indication = null,
                onClick = onToggleExpand
            )
            .animateContentSize(),
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (item.isExpanded) SurfaceLight else SurfaceLight.copy(alpha = 0.7f)
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = if (item.isExpanded) 4.dp else 0.dp),
        border = if (!item.isExpanded) CardDefaults.outlinedCardBorder() else null
    ) {
        Column(modifier = Modifier.padding(20.dp)) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(modifier = Modifier.size(10.dp).background(item.riskColor, CircleShape))
                    Spacer(modifier = Modifier.width(12.dp))
                    Text(text = item.relativeTime, style = MaterialTheme.typography.labelMedium, color = TextSecondary)
                }
                
                Surface(
                    color = item.riskColor.copy(alpha = 0.1f),
                    shape = RoundedCornerShape(8.dp)
                ) {
                    Text(
                        text = item.riskLabel,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = item.riskColor
                    )
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            Text(
                text = if (item.isExpanded) item.response else item.response.take(100) + "...",
                style = MaterialTheme.typography.bodyLarge,
                color = TextPrimary,
                lineHeight = 26.sp
            )

            if (item.isExpanded) {
                Spacer(modifier = Modifier.height(20.dp))
                
                Surface(
                    color = BackgroundLight,
                    shape = RoundedCornerShape(16.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text("Captured Text", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold, color = ElderBlue)
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(text = item.screenText, style = MaterialTheme.typography.bodyMedium, color = TextSecondary)
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))
            
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    imageVector = if (item.isExpanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
                    contentDescription = null,
                    tint = ElderBlue,
                    modifier = Modifier.size(24.dp)
                )
                Spacer(modifier = Modifier.width(4.dp))
                Text(
                    text = if (item.isExpanded) "Show Less" else "View Full Analysis",
                    style = MaterialTheme.typography.labelLarge,
                    color = ElderBlue,
                    fontWeight = FontWeight.Bold
                )
            }
        }
    }
}

@Composable
private fun EmptyHistoryState(onTryDemo: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().padding(40.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Surface(
            modifier = Modifier.size(120.dp),
            color = ElderBlueLight,
            shape = CircleShape
        ) {
            Box(contentAlignment = Alignment.Center) {
                Icon(Icons.Default.History, null, tint = ElderBlue, modifier = Modifier.size(64.dp))
            }
        }
        Spacer(modifier = Modifier.height(32.dp))
        Text("No activity yet", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Text(
            "Your protection logs will appear here.",
            style = MaterialTheme.typography.bodyLarge,
            color = TextSecondary,
            textAlign = TextAlign.Center
        )
        Spacer(modifier = Modifier.height(32.dp))
        Button(
            onClick = onTryDemo,
            modifier = Modifier.fillMaxWidth().height(64.dp),
            shape = RoundedCornerShape(16.dp),
            colors = ButtonDefaults.buttonColors(containerColor = ElderBlue)
        ) {
            Text("Try Interactive Demo")
        }
    }
}

