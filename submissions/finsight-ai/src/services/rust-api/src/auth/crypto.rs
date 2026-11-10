use crate::errors::AppError;
use argon2::{
    password_hash::{rand_core::OsRng, PasswordHash, PasswordHasher, PasswordVerifier, SaltString},
    Algorithm, Argon2, Params, Version,
};
use hmac::{Hmac, Mac};
use rand::RngCore;
use sha2::{Digest, Sha256};
use subtle::ConstantTimeEq;

type HmacSha256 = Hmac<Sha256>;

pub struct Crypto;

impl Crypto {
    /// Hashes a password using Argon2id with OWASP parameters (m=19456 KiB, t=2, p=1, len=32).
    pub fn hash_password(password: &str) -> Result<String, AppError> {
        let salt = SaltString::generate(&mut OsRng);
        // OWASP recommended: m_cost = 19456 KiB (19 MiB), t_cost = 2, p_cost = 1, output_len = 32
        let params = Params::new(19456, 2, 1, Some(32))
            .map_err(|e| AppError::Internal(format!("Argon2 params configuration error: {e}")))?;

        let argon2 = Argon2::new(Algorithm::Argon2id, Version::V0x13, params);

        let password_hash = argon2
            .hash_password(password.as_bytes(), &salt)
            .map_err(|e| AppError::Internal(format!("Password hashing failed: {e}")))?
            .to_string();

        Ok(password_hash)
    }

    /// Verifies a password against an Argon2id hash.
    pub fn verify_password(password: &str, hash_str: &str) -> Result<bool, AppError> {
        let parsed_hash = match PasswordHash::new(hash_str) {
            Ok(h) => h,
            Err(e) => {
                tracing::warn!("Failed to parse password hash: {e}");
                return Ok(false);
            }
        };

        let argon2 = Argon2::default();
        Ok(argon2.verify_password(password.as_bytes(), &parsed_hash).is_ok())
    }

    /// Generates a cryptographically secure random token (32 bytes = 256 bits entropy) as hex string.
    pub fn generate_secure_token() -> String {
        let mut bytes = [0u8; 32];
        OsRng.fill_bytes(&mut bytes);
        hex::encode(bytes)
    }

    /// Computes the SHA-256 hash of a token string as lowercase hex string.
    pub fn sha256_hex(token: &str) -> String {
        let mut hasher = Sha256::new();
        hasher.update(token.as_bytes());
        hex::encode(hasher.finalize())
    }

    /// Derives a cryptographically secure, deterministic CSRF token using HMAC-SHA-256
    /// with strict domain separation ("finsight:csrf:v1:"), bound to session token and CSRF secret.
    pub fn derive_csrf_token(csrf_secret: &str, raw_session_token: &str) -> Result<String, AppError> {
        let mut mac = HmacSha256::new_from_slice(csrf_secret.as_bytes())
            .map_err(|e| AppError::Internal(format!("HMAC-SHA256 initialization error: {e}")))?;
        mac.update(b"finsight:csrf:v1:");
        mac.update(raw_session_token.as_bytes());
        let result = mac.finalize();
        Ok(hex::encode(result.into_bytes()))
    }

    /// Performs constant-time equality check between two hex strings to eliminate timing attacks.
    pub fn constant_time_eq_hex(a: &str, b: &str) -> bool {
        if a.len() != b.len() {
            return false;
        }
        a.as_bytes().ct_eq(b.as_bytes()).into()
    }
}
