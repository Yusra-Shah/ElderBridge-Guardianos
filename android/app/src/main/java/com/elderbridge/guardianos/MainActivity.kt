package com.elderbridge.guardianos

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.elderbridge.guardianos.speech.SpeechManager
import com.elderbridge.guardianos.ui.screens.HistoryScreen
import com.elderbridge.guardianos.ui.screens.HomeScreen
import com.elderbridge.guardianos.ui.screens.OnboardingScreen
import com.elderbridge.guardianos.ui.screens.OverlayPreviewScreen
import com.elderbridge.guardianos.ui.screens.PermissionsScreen
import com.elderbridge.guardianos.ui.screens.ProfileScreen
import com.elderbridge.guardianos.ui.theme.ElderBridgeGuardianosTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        SpeechManager.init(this)
        enableEdgeToEdge()
        setContent {
            ElderBridgeGuardianosTheme {
                val navController = rememberNavController()
                NavHost(navController = navController, startDestination = "onboarding") {
                    composable("onboarding") {
                        OnboardingScreen(onFinished = {
                            navController.navigate("permissions") {
                                popUpTo("onboarding") { inclusive = true }
                            }
                        })
                    }
                    composable("permissions") {
                        PermissionsScreen(onContinue = {
                            navController.navigate("home") {
                                popUpTo("permissions") { inclusive = true }
                            }
                        })
                    }
                    composable("home") {
                        HomeScreen(
                            onTryDemo = { navController.navigate("overlay_preview") },
                            onHistory = { navController.navigate("history") },
                            onProfile = { navController.navigate("profile") }
                        )
                    }
                    composable("overlay_preview") {
                        OverlayPreviewScreen(onBack = { navController.popBackStack() })
                    }
                    composable("history") {
                        HistoryScreen(onBack = { navController.popBackStack() })
                    }
                    composable("profile") {
                        ProfileScreen(onBack = { navController.popBackStack() })
                    }
                }
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        SpeechManager.shutdown()
    }
}
