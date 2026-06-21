package com.elderbridge.guardianos.redaction

/**
 * Thread-safe in-memory store for the latest redacted screen snapshot.
 *
 * Only ever holds text that has already passed through RedactionEngine — callers must
 * never write raw text here. ScreenReaderService is the sole writer; OverlayService is
 * the sole reader. Both run on the main thread today, but the synchronization guards
 * against future threading changes.
 */
object ScreenContentHolder {

    data class ScreenSnapshot(
        val redactedText: String,
        val sourcePackage: String,
        val capturedAtMs: Long = System.currentTimeMillis()
    )

    @Volatile
    private var latest: ScreenSnapshot? = null

    /** Replace the stored snapshot. [redactedText] must already be redacted. */
    fun update(redactedText: String, sourcePackage: String) {
        synchronized(this) {
            latest = ScreenSnapshot(redactedText, sourcePackage)
        }
    }

    /** Returns the latest snapshot, or null if nothing has been captured yet. */
    fun get(): ScreenSnapshot? = synchronized(this) { latest }

    /** Wipe the snapshot, e.g. when the accessibility service disconnects. */
    fun clear() {
        synchronized(this) { latest = null }
    }
}
