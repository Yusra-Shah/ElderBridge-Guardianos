# ElderBridge GuardianOS — Android App

Android client for ElderBridge GuardianOS, an AI companion that helps older adults navigate healthcare benefits, government forms, and public support systems.

---

## Requirements

| Tool | Version |
|------|---------|
| Android Studio | Hedgehog (2023.1.1) or newer |
| Android SDK — compile | API 35 |
| Android SDK — minimum | API 26 (Android 8.0) |
| JDK | 11 or newer (bundled with Android Studio) |
| Gradle | 8.7 (downloaded automatically by the wrapper) |

---

## First-time setup

1. **Open in Android Studio**
   - Launch Android Studio → **Open** → select the `android/` folder (this directory).
   - Android Studio will detect the Gradle project automatically.

2. **Download the Gradle wrapper JAR**
   The `gradle-wrapper.jar` binary is not committed to source control. Android Studio downloads it automatically on first sync. Alternatively, run:
   ```
   gradle wrapper --gradle-version 8.7
   ```
   from inside the `android/` directory if you have Gradle installed system-wide.

3. **Install SDK components**
   Android Studio will prompt to install missing SDK components (API 35 platform, build tools). Accept and let it install.

4. **Sync the project**
   Click **Sync Now** in the notification bar, or go to **File → Sync Project with Gradle Files**.

---

## Running on a physical device

1. Enable **Developer Options** on your Android phone:
   - Go to **Settings → About phone** and tap **Build number** seven times.

2. Enable **USB debugging** inside Developer Options.

3. Plug your phone into your computer via USB and accept the debugging prompt on the phone.

4. In Android Studio, select your device from the device dropdown and click **Run ▶**.

> **Tip:** The overlay bubble and notification listener features require granting special permissions that can only be enabled via system Settings — the app walks you through this on the Permissions screen.

---

## Running on an emulator

1. Open **Device Manager** in Android Studio and create an AVD with API 26 or higher.
2. Start the emulator, select it in the device dropdown, and click **Run ▶**.

> Note: The floating `OverlayService` bubble requires `SYSTEM_ALERT_WINDOW` permission. On the emulator, go to **Settings → Apps → ElderBridge → Display over other apps** and enable it manually.

---

## Building a debug APK from the command line

```bash
# From the android/ directory:
./gradlew assembleDebug          # macOS / Linux
gradlew.bat assembleDebug        # Windows

# Output:
# app/build/outputs/apk/debug/app-debug.apk
```

---

## Project structure

```
app/src/main/java/com/elderbridge/guardianos/
├── MainActivity.kt              — entry point, Compose NavHost
├── ui/
│   ├── theme/
│   │   ├── Color.kt             — high-contrast color palette
│   │   ├── Theme.kt             — MaterialTheme wrapper
│   │   └── Type.kt              — enlarged typography for elderly users
│   └── screens/
│       ├── OnboardingScreen.kt  — 4-page welcome flow
│       ├── PermissionsScreen.kt — accessibility / notification / overlay grants
│       ├── HomeScreen.kt        — status dashboard + monitoring toggle
│       └── OverlayPreviewScreen.kt — interactive demo of the bubble UI
├── services/
│   ├── OverlayService.kt        — draggable floating bubble (WindowManager)
│   └── NotificationListener.kt — NotificationListenerService skeleton
└── redaction/
    └── RedactionEngine.kt       — on-device regex redaction (OTP, phone, email)
```

---

## Security notes

- `RedactionEngine` runs synchronously on every notification before any text is logged.
- No network calls, API keys, or backend URLs exist anywhere in this codebase.
- OTPs (4–8 digit codes) are replaced with `[OTP]` before any downstream processing.

---

## What's not implemented yet

- Real accessibility-service screen reading
- Backend / AI inference integration
- User preferences persistence
- Dark mode (light-only currently — high contrast for elderly users)
