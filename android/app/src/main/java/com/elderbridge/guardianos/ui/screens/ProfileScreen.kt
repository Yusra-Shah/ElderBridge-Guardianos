package com.elderbridge.guardianos.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.viewmodel.compose.viewModel
import com.elderbridge.guardianos.ui.state.ProfileState
import com.elderbridge.guardianos.ui.theme.*
import com.elderbridge.guardianos.ui.viewmodel.ProfileViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProfileScreen(
    onBack: () -> Unit,
    vm: ProfileViewModel = viewModel()
) {
    val context = LocalContext.current
    val state by vm.state.collectAsState()

    // Initialize state from storage on first composition
    LaunchedEffect(Unit) {
        vm.init(context)
    }

    val locationPermLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) vm.fetchLocation(context)
    }

    // --- Animations ---
    val animatedProgress by animateFloatAsState(
        targetValue = state.progress,
        animationSpec = spring(stiffness = Spring.StiffnessLow),
        label = "progress"
    )

    val avatarScale by animateFloatAsState(
        targetValue = 1f,
        animationSpec = spring(dampingRatio = Spring.DampingRatioMediumBouncy),
        label = "avatar"
    )

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(BackgroundLight)
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 24.dp)
                .verticalScroll(rememberScrollState()),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(20.dp)
        ) {
            Spacer(modifier = Modifier.height(32.dp))

            // Screen Header
            Text(
                text = "My Profile",
                style = MaterialTheme.typography.headlineMedium,
                color = ElderBlue,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.fillMaxWidth()
            )

            // Avatar Section with Scale-in Animation
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Box(
                    modifier = Modifier
                        .size(90.dp)
                        .scale(avatarScale)
                        .background(ElderBlueLight, CircleShape),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = state.fullName.trim().firstOrNull()?.uppercaseChar()?.toString() ?: "E",
                        style = MaterialTheme.typography.displayMedium,
                        color = ElderBlue,
                        fontWeight = FontWeight.Bold
                    )
                }
                Spacer(modifier = Modifier.height(12.dp))
                Text(
                    text = state.fullName.ifBlank { "New User" },
                    style = MaterialTheme.typography.titleLarge,
                    color = TextPrimary,
                    fontWeight = FontWeight.SemiBold
                )
            }

            // Profile Completion Progress Card
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(24.dp),
                colors = CardDefaults.cardColors(containerColor = SurfaceLight)
            ) {
                Column(modifier = Modifier.padding(20.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            "Profile Progress",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = TextPrimary
                        )
                        Text(
                            "${state.completedFieldsCount} of ${state.totalFieldsCount} steps",
                            style = MaterialTheme.typography.bodyMedium,
                            color = TextSecondary
                        )
                    }
                    Spacer(modifier = Modifier.height(12.dp))
                    LinearProgressIndicator(
                        progress = { animatedProgress },
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(12.dp),
                        color = ElderBlue,
                        trackColor = ElderBlueLight,
                        strokeCap = StrokeCap.Round
                    )
                }
            }

            // Emergency Contact Status Card with Entrance Animation
            AnimatedVisibility(
                visible = true, // Entrance animation
                enter = fadeIn() + slideInVertically { it / 2 }
            ) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(24.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = if (state.hasEmergencyContact) ActiveGreenLight else ErrorRed.copy(alpha = 0.1f)
                    )
                ) {
                    Row(
                        modifier = Modifier.padding(20.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Surface(
                            modifier = Modifier.size(12.dp),
                            shape = CircleShape,
                            color = if (state.hasEmergencyContact) ActiveGreen else ErrorRed
                        ) {}
                        Spacer(modifier = Modifier.width(12.dp))
                        Text(
                            text = if (state.hasEmergencyContact) "Emergency Contact Configured" else "No Emergency Contact Set",
                            style = MaterialTheme.typography.bodyLarge,
                            fontWeight = FontWeight.SemiBold,
                            color = if (state.hasEmergencyContact) ActiveGreen else ErrorRed
                        )
                    }
                }
            }

            // 1. About Me Card
            ProfileSectionCard(title = "About Me") {
                ProfileTextField(
                    value = state.fullName,
                    onValueChange = vm::onFullNameChange,
                    label = "Full Name"
                )

                Row(verticalAlignment = Alignment.CenterVertically) {
                    ProfileTextField(
                        value = state.location,
                        onValueChange = vm::onLocationChange,
                        label = "Location",
                        modifier = Modifier.weight(1f),
                        trailingIcon = if (state.isLocating) {
                            {
                                val infiniteTransition = rememberInfiniteTransition(label = "loc_pulse")
                                val pulseAlpha by infiniteTransition.animateFloat(
                                    initialValue = 0.4f,
                                    targetValue = 1f,
                                    animationSpec = infiniteRepeatable(tween(800), RepeatMode.Reverse),
                                    label = "pulse"
                                )
                                CircularProgressIndicator(
                                    modifier = Modifier.size(20.dp),
                                    strokeWidth = 2.dp,
                                    color = ElderBlue.copy(alpha = pulseAlpha)
                                )
                            }
                        } else null
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Button(
                        onClick = {
                            val hasPermission = ContextCompat.checkSelfPermission(
                                context, Manifest.permission.ACCESS_FINE_LOCATION
                            ) == PackageManager.PERMISSION_GRANTED
                            if (hasPermission) vm.fetchLocation(context)
                            else locationPermLauncher.launch(Manifest.permission.ACCESS_FINE_LOCATION)
                        },
                        enabled = !state.isLocating,
                        modifier = Modifier.height(56.dp),
                        shape = RoundedCornerShape(12.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = ElderBlueLight, contentColor = ElderBlue)
                    ) {
                        Text("GPS")
                    }
                }
            }

            // 2. Emergency Contacts Card
            ProfileSectionCard(title = "Emergency Contacts") {
                Column {
                    ProfileTextField(
                        value = state.emergencyContact,
                        onValueChange = vm::onEmergencyContactChange,
                        label = "Emergency Number",
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone)
                    )
                    Text(
                        text = "We will use this number if a scam, fraud, or emergency is detected while using your phone.",
                        style = MaterialTheme.typography.bodySmall,
                        color = TextSecondary,
                        modifier = Modifier.padding(top = 4.dp, start = 4.dp)
                    )
                }

                ProfileTextField(
                    value = state.caregiverContact,
                    onValueChange = vm::onCaregiverContactChange,
                    label = "Caregiver Number (Optional)",
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone)
                )
            }

            // 3. Accessibility Card
            ProfileSectionCard(title = "Accessibility") {
                ExposedDropdownMenuBox(
                    expanded = state.languageExpanded,
                    onExpandedChange = { vm.setLanguageExpanded(it) }
                ) {
                    OutlinedTextField(
                        value = state.preferredLanguage,
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("App Language") },
                        trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = state.languageExpanded) },
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = ElderBlue,
                            unfocusedBorderColor = Divider,
                            focusedLabelColor = ElderBlue,
                            cursorColor = ElderBlue,
                            focusedContainerColor = SurfaceLight,
                            unfocusedContainerColor = SurfaceLight,
                            focusedTextColor = TextPrimary,
                            unfocusedTextColor = TextPrimary
                        ),
                        shape = RoundedCornerShape(12.dp),
                        modifier = Modifier
                            .menuAnchor()
                            .fillMaxWidth()
                    )
                    ExposedDropdownMenu(
                        expanded = state.languageExpanded,
                        onDismissRequest = { vm.setLanguageExpanded(false) }
                    ) {
                        listOf("English", "Urdu").forEach { lang ->
                            DropdownMenuItem(
                                text = { Text(lang, style = MaterialTheme.typography.bodyLarge) },
                                onClick = { vm.onLanguageChange(lang) }
                            )
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Action Buttons with Press Animation
            val interactionSource = remember { MutableInteractionSource() }
            val isPressed by interactionSource.collectIsPressedAsState()
            val saveButtonScale by animateFloatAsState(if (isPressed) 0.95f else 1f, label = "btn_press")

            Button(
                onClick = {
                    vm.saveProfile(context) {
                        Toast.makeText(context, "Profile Saved", Toast.LENGTH_SHORT).show()
                        onBack()
                    }
                },
                interactionSource = interactionSource,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(64.dp)
                    .scale(saveButtonScale),
                shape = RoundedCornerShape(16.dp),
                colors = ButtonDefaults.buttonColors(containerColor = ActiveGreen, contentColor = SurfaceLight)
            ) {
                Text("Save Profile", style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold)
            }

            OutlinedButton(
                onClick = onBack,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(64.dp),
                shape = RoundedCornerShape(16.dp),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = TextSecondary),
                border = ButtonDefaults.outlinedButtonBorder.copy(width = 1.dp)
            ) {
                Text("Cancel", style = MaterialTheme.typography.labelLarge)
            }

            Spacer(modifier = Modifier.height(40.dp))
        }
    }
}

@Composable
fun ProfileTextField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    modifier: Modifier = Modifier,
    keyboardOptions: KeyboardOptions = KeyboardOptions.Default,
    trailingIcon: @Composable (() -> Unit)? = null
) {
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        label = { Text(label) },
        modifier = modifier.fillMaxWidth(),
        singleLine = true,
        colors = OutlinedTextFieldDefaults.colors(
            focusedBorderColor = ElderBlue,
            unfocusedBorderColor = Divider,
            focusedLabelColor = ElderBlue,
            cursorColor = ElderBlue,
            focusedContainerColor = SurfaceLight,
            unfocusedContainerColor = SurfaceLight,
            focusedTextColor = TextPrimary,
            unfocusedTextColor = TextPrimary
        ),
        shape = RoundedCornerShape(12.dp),
        keyboardOptions = keyboardOptions,
        trailingIcon = trailingIcon
    )
}

@Composable
fun ProfileSectionCard(
    title: String,
    content: @Composable ColumnScope.() -> Unit
) {
    // Section entrance animation
    var visible by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { visible = true }
    
    AnimatedVisibility(
        visible = visible,
        enter = fadeIn(animationSpec = tween(600)) + slideInVertically(
            initialOffsetY = { 40 },
            animationSpec = tween(600)
        )
    ) {
        Column(modifier = Modifier.fillMaxWidth()) {
            Text(
                text = title,
                style = MaterialTheme.typography.titleSmall,
                color = TextSecondary,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.padding(start = 4.dp, bottom = 8.dp)
            )
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(24.dp),
                colors = CardDefaults.cardColors(containerColor = SurfaceLight),
                elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
            ) {
                Column(
                    modifier = Modifier.padding(20.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    content()
                }
            }
        }
    }
}
