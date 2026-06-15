package com.elderbridge.guardianos.ui.theme

import android.app.Activity
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

private val ElderLightColorScheme = lightColorScheme(
    primary = ElderBlue,
    onPrimary = TextOnPrimary,
    primaryContainer = ElderBlueLight,
    onPrimaryContainer = ElderBlueDark,
    secondary = ActiveGreen,
    onSecondary = TextOnPrimary,
    secondaryContainer = ActiveGreenLight,
    onSecondaryContainer = ActiveGreen,
    background = BackgroundLight,
    onBackground = TextPrimary,
    surface = SurfaceLight,
    onSurface = TextPrimary,
    onSurfaceVariant = TextSecondary,
    error = ErrorRed,
    onError = TextOnPrimary,
)

@Composable
fun ElderBridgeGuardianosTheme(
    content: @Composable () -> Unit
) {
    val colorScheme = ElderLightColorScheme
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = colorScheme.primary.toArgb()
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = false
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = ElderTypography,
        content = content
    )
}
