// Package crypto provides AES-256-GCM file encryption for backups.
// Files are encrypted in 1 MiB chunks so multi-gigabyte dumps stream
// without loading everything into memory. Format:
//
//	"DBH1" magic || frames...
//	each frame: 12-byte nonce || 4-byte big-endian ciphertext length || ciphertext
package crypto

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"fmt"
	"io"
	"os"
	"strings"
)

var magic = []byte("DBH1")

const chunkSize = 1 << 20 // 1 MiB

// DeriveKey turns arbitrary key material into a 32-byte AES key.
// 32-byte input is used as-is; anything else is hashed with SHA-256.
func DeriveKey(material []byte) []byte {
	if len(material) == 32 {
		out := make([]byte, 32)
		copy(out, material)
		return out
	}
	sum := sha256.Sum256(material)
	return sum[:]
}

// ParseKeyMaterial accepts a hex-encoded key or raw bytes.
func ParseKeyMaterial(s string) ([]byte, error) {
	s = strings.TrimSpace(s)
	if decoded, err := hex.DecodeString(s); err == nil && len(decoded) > 0 {
		return decoded, nil
	}
	if s == "" {
		return nil, fmt.Errorf("empty key material")
	}
	return []byte(s), nil
}

// LoadKeyFile reads a key file (hex or raw) and derives the AES-256 key.
func LoadKeyFile(path string) ([]byte, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read key file: %w", err)
	}
	material, err := ParseKeyMaterial(string(data))
	if err != nil {
		return nil, err
	}
	return DeriveKey(material), nil
}

// GenerateKeyFile writes a fresh random 32-byte key (hex-encoded, 0600) to path.
func GenerateKeyFile(path string) error {
	key := make([]byte, 32)
	if _, err := rand.Read(key); err != nil {
		return fmt.Errorf("random key: %w", err)
	}
	if err := os.WriteFile(path, []byte(hex.EncodeToString(key)+"\n"), 0o600); err != nil {
		return fmt.Errorf("write key file: %w", err)
	}
	return nil
}

func newGCM(key []byte) (cipher.AEAD, error) {
	if len(key) != 32 {
		return nil, fmt.Errorf("key must be 32 bytes, got %d", len(key))
	}
	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, err
	}
	return cipher.NewGCM(block)
}

// EncryptFile encrypts src into dst with AES-256-GCM.
func EncryptFile(key []byte, src, dst string) error {
	gcm, err := newGCM(key)
	if err != nil {
		return err
	}
	in, err := os.Open(src)
	if err != nil {
		return fmt.Errorf("open source: %w", err)
	}
	defer in.Close()
	out, err := os.OpenFile(dst, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0o600)
	if err != nil {
		return fmt.Errorf("open destination: %w", err)
	}
	defer out.Close()
	if err := EncryptStream(gcm, in, out); err != nil {
		return err
	}
	return out.Close()
}

// DecryptFile decrypts src into dst, failing if authentication fails.
func DecryptFile(key []byte, src, dst string) error {
	gcm, err := newGCM(key)
	if err != nil {
		return err
	}
	in, err := os.Open(src)
	if err != nil {
		return fmt.Errorf("open source: %w", err)
	}
	defer in.Close()
	out, err := os.OpenFile(dst, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0o600)
	if err != nil {
		return fmt.Errorf("open destination: %w", err)
	}
	defer out.Close()
	if err := DecryptStream(gcm, in, out); err != nil {
		return err
	}
	return out.Close()
}

// EncryptStream encrypts r into w using an already-built GCM.
func EncryptStream(gcm cipher.AEAD, r io.Reader, w io.Writer) error {
	if _, err := w.Write(magic); err != nil {
		return err
	}
	buf := make([]byte, chunkSize)
	nonce := make([]byte, gcm.NonceSize())
	for {
		n, rerr := io.ReadFull(r, buf)
		if n > 0 {
			if _, err := rand.Read(nonce); err != nil {
				return err
			}
			ct := gcm.Seal(nil, nonce, buf[:n], nil)
			if _, err := w.Write(nonce); err != nil {
				return err
			}
			var ln [4]byte
			binary.BigEndian.PutUint32(ln[:], uint32(len(ct)))
			if _, err := w.Write(ln[:]); err != nil {
				return err
			}
			if _, err := w.Write(ct); err != nil {
				return err
			}
		}
		if rerr == io.EOF || rerr == io.ErrUnexpectedEOF {
			return nil
		}
		if rerr != nil {
			return rerr
		}
	}
}

// DecryptStream decrypts r into w, verifying every chunk.
func DecryptStream(gcm cipher.AEAD, r io.Reader, w io.Writer) error {
	head := make([]byte, len(magic))
	if _, err := io.ReadFull(r, head); err != nil {
		return fmt.Errorf("read header: %w", err)
	}
	if string(head) != string(magic) {
		return fmt.Errorf("not a dbhaven-encrypted file (bad magic)")
	}
	nonce := make([]byte, gcm.NonceSize())
	var ln [4]byte
	for {
		_, err := io.ReadFull(r, nonce)
		if err == io.EOF {
			return nil // clean end
		}
		if err != nil {
			return fmt.Errorf("read frame: %w", err)
		}
		if _, err := io.ReadFull(r, ln[:]); err != nil {
			return fmt.Errorf("read frame length: %w", err)
		}
		size := binary.BigEndian.Uint32(ln[:])
		if size > uint32(chunkSize+gcm.Overhead()+1024) {
			return fmt.Errorf("frame too large (%d bytes), file corrupt?", size)
		}
		ct := make([]byte, size)
		if _, err := io.ReadFull(r, ct); err != nil {
			return fmt.Errorf("read frame body: %w", err)
		}
		pt, err := gcm.Open(nil, nonce, ct, nil)
		if err != nil {
			return fmt.Errorf("authentication failed: %w", err)
		}
		if _, err := w.Write(pt); err != nil {
			return err
		}
	}
}
