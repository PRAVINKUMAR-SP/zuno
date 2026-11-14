package com.zuno.backend.util;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Base64;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

public final class AuthUtil {

    private static final String SECRET_KEY = "ZUNO_ZERO_SUPER_SECRET_AUTHENTICATION_KEY_2026";
    private static final SecureRandom RANDOM = new SecureRandom();

    private AuthUtil() {}

    public static String generateSalt() {
        byte[] salt = new byte[16];
        RANDOM.nextBytes(salt);
        return Base64.getEncoder().encodeToString(salt);
    }

    public static String hashPassword(String password, String salt) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            digest.update(salt.getBytes(StandardCharsets.UTF_8));
            byte[] hash = digest.digest(password.getBytes(StandardCharsets.UTF_8));
            return Base64.getEncoder().encodeToString(hash);
        } catch (Exception ex) {
            throw new RuntimeException("Password hashing error", ex);
        }
    }

    public static boolean verifyPassword(String password, String salt, String expectedHash) {
        String calculated = hashPassword(password, salt);
        return calculated.equals(expectedHash);
    }

    /**
     * Generate a signed token: base64(userId:email:role:timestamp).signature
     */
    public static String generateToken(Long userId, String email, String role) {
        long ts = System.currentTimeMillis();
        String payload = userId + ":" + email + ":" + role + ":" + ts;
        String encodedPayload = Base64.getUrlEncoder().withoutPadding().encodeToString(payload.getBytes(StandardCharsets.UTF_8));
        String signature = sign(encodedPayload);
        return encodedPayload + "." + signature;
    }

    /**
     * Validate and extract token info.
     * Returns string array: [userId, email, role] or null if invalid.
     */
    public static TokenInfo validateToken(String token) {
        if (token == null || !token.contains(".")) {
            return null;
        }
        String[] parts = token.split("\\.");
        if (parts.length != 2) {
            return null;
        }
        String encodedPayload = parts[0];
        String expectedSignature = sign(encodedPayload);
        if (!expectedSignature.equals(parts[1])) {
            return null;
        }

        try {
            String payload = new String(Base64.getUrlDecoder().decode(encodedPayload), StandardCharsets.UTF_8);
            String[] fields = payload.split(":");
            if (fields.length < 3) {
                return null;
            }
            Long userId = Long.parseLong(fields[0]);
            String email = fields[1];
            String role = fields[2];
            return new TokenInfo(userId, email, role);
        } catch (Exception ex) {
            return null;
        }
    }

    private static String sign(String data) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(SECRET_KEY.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            byte[] signed = mac.doFinal(data.getBytes(StandardCharsets.UTF_8));
            return Base64.getUrlEncoder().withoutPadding().encodeToString(signed);
        } catch (Exception ex) {
            throw new RuntimeException("Signing error", ex);
        }
    }

    public record TokenInfo(Long userId, String email, String role) {}
}

