package crypto

import (
	"bytes"
	"crypto/rand"
	"os"
	"path/filepath"
	"testing"
)

func testKey(t *testing.T) []byte {
	t.Helper()
	k := make([]byte, 32)
	if _, err := rand.Read(k); err != nil {
		t.Fatal(err)
	}
	return k
}

func TestRoundTripFile(t *testing.T) {
	dir := t.TempDir()
	// Multi-chunk payload: 2.5 MiB of pseudorandom data.
	plain := make([]byte, 2_500_000)
	if _, err := rand.Read(plain); err != nil {
		t.Fatal(err)
	}
	src := filepath.Join(dir, "plain.bin")
	enc := filepath.Join(dir, "plain.bin.enc")
	dec := filepath.Join(dir, "plain.bin.dec")
	if err := os.WriteFile(src, plain, 0o600); err != nil {
		t.Fatal(err)
	}
	key := testKey(t)
	if err := EncryptFile(key, src, enc); err != nil {
		t.Fatalf("EncryptFile: %v", err)
	}
	info, _ := os.Stat(enc)
	if info.Size() <= int64(len(plain)) {
		t.Fatalf("encrypted file suspiciously small: %d", info.Size())
	}
	if err := DecryptFile(key, enc, dec); err != nil {
		t.Fatalf("DecryptFile: %v", err)
	}
	got, err := os.ReadFile(dec)
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(got, plain) {
		t.Fatal("round trip mismatch")
	}
}

func TestWrongKeyFails(t *testing.T) {
	dir := t.TempDir()
	src := filepath.Join(dir, "a")
	enc := filepath.Join(dir, "a.enc")
	dec := filepath.Join(dir, "a.dec")
	if err := os.WriteFile(src, []byte("secret data here"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := EncryptFile(testKey(t), src, enc); err != nil {
		t.Fatal(err)
	}
	if err := DecryptFile(testKey(t), enc, dec); err == nil {
		t.Fatal("expected authentication failure with wrong key")
	}
}

func TestTamperedCiphertextFails(t *testing.T) {
	dir := t.TempDir()
	src := filepath.Join(dir, "a")
	enc := filepath.Join(dir, "a.enc")
	dec := filepath.Join(dir, "a.dec")
	if err := os.WriteFile(src, []byte("secret data here"), 0o600); err != nil {
		t.Fatal(err)
	}
	key := testKey(t)
	if err := EncryptFile(key, src, enc); err != nil {
		t.Fatal(err)
	}
	data, _ := os.ReadFile(enc)
	data[len(data)-1] ^= 0xff // flip a bit in the last frame
	if err := os.WriteFile(enc, data, 0o600); err != nil {
		t.Fatal(err)
	}
	if err := DecryptFile(key, enc, dec); err == nil {
		t.Fatal("expected authentication failure on tampered file")
	}
}

func TestDecryptGarbageFails(t *testing.T) {
	dir := t.TempDir()
	bad := filepath.Join(dir, "bad")
	dec := filepath.Join(dir, "bad.dec")
	if err := os.WriteFile(bad, []byte("definitely not encrypted"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := DecryptFile(testKey(t), bad, dec); err == nil {
		t.Fatal("expected error on non-encrypted input")
	}
}

func TestDeriveKey(t *testing.T) {
	raw := make([]byte, 32)
	for i := range raw {
		raw[i] = byte(i)
	}
	if got := DeriveKey(raw); !bytes.Equal(got, raw) {
		t.Fatal("32-byte key should pass through unchanged")
	}
	short := DeriveKey([]byte("short"))
	if len(short) != 32 {
		t.Fatalf("derived key must be 32 bytes, got %d", len(short))
	}
	if bytes.Equal(short, DeriveKey([]byte("different"))) {
		t.Fatal("different inputs must derive different keys")
	}
}

func TestParseKeyMaterial(t *testing.T) {
	hexKey := "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff"
	m, err := ParseKeyMaterial(hexKey)
	if err != nil {
		t.Fatal(err)
	}
	if len(m) != 32 {
		t.Fatalf("want 32 bytes, got %d", len(m))
	}
	m2, err := ParseKeyMaterial("  my-passphrase  ")
	if err != nil {
		t.Fatal(err)
	}
	if string(m2) != "my-passphrase" {
		t.Fatalf("raw passphrase not preserved: %q", m2)
	}
	if _, err := ParseKeyMaterial("   "); err == nil {
		t.Fatal("expected error on empty key")
	}
}

func TestGenerateKeyFile(t *testing.T) {
	p := filepath.Join(t.TempDir(), "key")
	if err := GenerateKeyFile(p); err != nil {
		t.Fatal(err)
	}
	info, err := os.Stat(p)
	if err != nil {
		t.Fatal(err)
	}
	if info.Mode().Perm() != 0o600 {
		t.Fatalf("key file must be 0600, got %o", info.Mode().Perm())
	}
	key, err := LoadKeyFile(p)
	if err != nil {
		t.Fatal(err)
	}
	if len(key) != 32 {
		t.Fatalf("want 32-byte key, got %d", len(key))
	}
}
