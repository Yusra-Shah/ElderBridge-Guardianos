package com.elderbridge.guardianos.ui.theme

import android.app.Activity
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

@Immutable
data class PremiumThemeData(
    val gradientPrimary: Brush,
    val gradientSurface: Brush,
    val gradientSuccess: Brush,
    val shadowSoft: Color,
    val shadowStrong: Color,
    val glassBase: Color
)

val LocalPremiumTheme = staticCompositionLocalOf {
    PremiumThemeData(
        gradientPrimary = Brush.verticalGradient(listOf(Color.Blue, Color.Black)),
        gradientSurface = Brush.verticalGradient(listOf(Color.White, Color.Gray)),
        gradientSuccess = Brush.verticalGradient(listOf(Color.Green, Color.Black)),
        shadowSoft = Color.Black.copy(alpha = 0.1f),
        shadowStrong = Color.Black.copy(alpha = 0.3f),
        glassBase = Color.White.copy(alpha = 0.5f)
    )
}

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
    onError = TextOnPrimary
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
            window.statusBarColor = colorScheme.background.toArgb()
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = true
        }
    }

    val premiumData = PremiumThemeData(
        gradientPrimary = Brush.verticalGradient(listOf(ElderBlue, ElderBlueDark)),
        gradientSurface = Brush.verticalGradient(listOf(SurfaceLight, Color(0xFFF1F5F9))),
        gradientSuccess = Brush.verticalGradient(listOf(ActiveGreen, Color(0xFF047857))),
        shadowSoft = Color(0x0D000000),
        shadowStrong = Color(0x26000000),
        glassBase = Color(0xB3FFFFFF)
    )

    CompositionLocalProvider(LocalPremiumTheme provides premiumData) {
        MaterialTheme(
            colorScheme = colorScheme,
            typography = ElderTypography,
            content = content
        )
    }
}
