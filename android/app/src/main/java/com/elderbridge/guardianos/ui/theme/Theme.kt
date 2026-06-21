package com.elderbridge.guardianos.ui.theme

import android.app.Activity
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

private val ElderLightColorScheme = lightColorScheme(
    primary = EbSage,
    onPrimary = EbSurface,
    primaryContainer = EbSurfaceAlt,
    onPrimaryContainer = EbSage,
    secondary = EbNavy,
    onSecondary = EbSurface,
    secondaryContainer = EbSurfaceAlt,
    onSecondaryContainer = EbNavy,
    tertiary = EbClay,
    onTertiary = EbSurface,
    tertiaryContainer = EbSurfaceAlt,
    onTertiaryContainer = EbClay,
    background = EbGround,
    onBackground = EbInk,
    surface = EbSurface,
    onSurface = EbInk,
    surfaceVariant = EbSurfaceAlt,
    onSurfaceVariant = EbInkSoft,
    error = EbClayStrong,
    onError = EbSurface,
    outline = EbLine,
    outlineVariant = EbLine,
)

private val ElderDarkColorScheme = darkColorScheme(
    primary = EbSageDark,
    onPrimary = EbGroundDark,
    primaryContainer = EbSurfaceAltDark,
    onPrimaryContainer = EbSageDark,
    secondary = EbNavyDark,
    onSecondary = EbGroundDark,
    secondaryContainer = EbSurfaceAltDark,
    onSecondaryContainer = EbNavyDark,
    tertiary = EbClayDark,
    onTertiary = EbGroundDark,
    tertiaryContainer = EbSurfaceAltDark,
    onTertiaryContainer = EbClayDark,
    background = EbGroundDark,
    onBackground = EbInkDark,
    surface = EbSurfaceDark,
    onSurface = EbInkDark,
    surfaceVariant = EbSurfaceAltDark,
    onSurfaceVariant = EbInkSoftDark,
    error = EbClayStrongDark,
    onError = EbGroundDark,
    outline = EbLineDark,
    outlineVariant = EbLineDark,
)

@Composable
fun ElderBridgeGuardianosTheme(
    darkTheme: Boolean = false,
    content: @Composable () -> Unit
) {
    val colorScheme = if (darkTheme) ElderDarkColorScheme else ElderLightColorScheme
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = colorScheme.background.toArgb()
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = !darkTheme
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = ElderTypography,
        content = content
    )
}
