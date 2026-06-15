package com.elderbridge.guardianos.redaction

/**
 * On-device redaction of sensitive patterns before any text is logged or processed.
 * Per the security model, OTPs, phone numbers, and email addresses must never leave the device
 * in plaintext — this engine strips them before any downstream handling.
 */
object RedactionEngine {

    // Matches common North American phone formats:
    //   (555) 867-5309  |  555-867-5309  |  555.867.5309  |  +1 555 867 5309  |  5558675309
    private val PHONE_REGEX = Regex(
        """(\+?1[\s.\-]?)?(\(?\d{3}\)?[\s.\-]?)\d{3}[\s.\-]\d{4}"""
    )

    // Matches standard email addresses
    private val EMAIL_REGEX = Regex(
        """[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"""
    )

    // Matches standalone 4–8 digit sequences (OTPs, PINs, verification codes).
    // Applied after phone redaction so phone digits are already masked.
    // Uses negative lookahead/lookbehind to avoid matching substrings of longer numbers.
    private val OTP_REGEX = Regex("""(?<!\d)\d{4,8}(?!\d)""")

    /**
     * Returns a copy of [text] with sensitive patterns replaced by placeholder tokens.
     * Order matters: email → phone → OTP, so phone digits removed before OTP pass.
     */
    fun redact(text: String): String {
        var result = text
        result = EMAIL_REGEX.replace(result, "[EMAIL]")
        result = PHONE_REGEX.replace(result, "[PHONE]")
        result = OTP_REGEX.replace(result, "[OTP]")
        return result
    }
}
