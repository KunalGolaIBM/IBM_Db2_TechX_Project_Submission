package store

import (
	"bytes"
	"context"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/miriyaladhanwinn/dbhaven/internal/config"
)

func TestS3Key(t *testing.T) {
	cases := []struct {
		prefix, job, typ, file, want string
	}{
		{"backups/", "main", "postgres", "f.enc", "backups/main/postgres/f.enc"},
		{"", "main", "mysql", "f.gz.enc", "main/mysql/f.gz.enc"},
		{"prod", "j", "mongo", "", "prod/j/mongo"},
		{"/a//b/", "j", "t", "f", "a/b/j/t/f"},
	}
	for _, c := range cases {
		if got := S3Key(c.prefix, c.job, c.typ, c.file); got != c.want {
			t.Fatalf("S3Key(%q,%q,%q,%q) = %q, want %q", c.prefix, c.job, c.typ, c.file, got, c.want)
		}
	}
}

func TestLocalRoundTrip(t *testing.T) {
	ctx := context.Background()
	root := t.TempDir()
	l := &Local{root: root}
	data := []byte("backup-bytes-123")
	if err := l.Put(ctx, "main/postgres/f.dump.enc", bytes.NewReader(data), int64(len(data))); err != nil {
		t.Fatalf("Put: %v", err)
	}
	// Partial upload residue must not leak into listings.
	if err := os.WriteFile(filepath.Join(root, "main", "postgres", "x.tmp"), []byte("x"), 0o600); err != nil {
		t.Fatal(err)
	}
	rc, size, err := l.Get(ctx, "main/postgres/f.dump.enc")
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	buf := new(bytes.Buffer)
	if _, err := buf.ReadFrom(rc); err != nil {
		t.Fatal(err)
	}
	rc.Close()
	if !bytes.Equal(buf.Bytes(), data) || size != int64(len(data)) {
		t.Fatal("round trip mismatch")
	}
	objs, err := l.List(ctx, "main/postgres/")
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(objs) != 1 || objs[0].Key != "main/postgres/f.dump.enc" {
		t.Fatalf("unexpected list: %+v", objs)
	}
	if err := l.Delete(ctx, "main/postgres/f.dump.enc"); err != nil {
		t.Fatalf("Delete: %v", err)
	}
	objs, _ = l.List(ctx, "main/postgres/")
	if len(objs) != 0 {
		t.Fatalf("expected empty after delete, got %+v", objs)
	}
}

func TestLocalListMissingDir(t *testing.T) {
	l := &Local{root: t.TempDir()}
	objs, err := l.List(context.Background(), "nope/")
	if err != nil {
		t.Fatalf("List on missing dir should not error: %v", err)
	}
	if len(objs) != 0 {
		t.Fatalf("want empty, got %+v", objs)
	}
}

func TestNewBackendLocal(t *testing.T) {
	b, prefix, err := New(config.Destination{Type: "local", Path: t.TempDir()}, "job", "postgres")
	if err != nil {
		t.Fatal(err)
	}
	if prefix != "job/postgres/" {
		t.Fatalf("unexpected prefix %q", prefix)
	}
	if b.Describe() == "" {
		t.Fatal("empty Describe")
	}
}

func TestNewBackendUnknown(t *testing.T) {
	if _, _, err := New(config.Destination{Type: "ftp"}, "j", "t"); err == nil {
		t.Fatal("expected error for unknown destination type")
	}
}

func TestPrune(t *testing.T) {
	ctx := context.Background()
	root := t.TempDir()
	l := &Local{root: root}
	now := time.Now()
	// 12 daily backups, keep_last=5 -> 7 deleted.
	for d := 0; d < 12; d++ {
		ts := now.AddDate(0, 0, -d)
		name := "j-postgres-" + ts.Format("20060102-150405") + ".dump.enc"
		if err := l.Put(ctx, "j/postgres/"+name, bytes.NewReader([]byte("x")), 1); err != nil {
			t.Fatal(err)
		}
	}
	deleted, err := Prune(ctx, l, "j/postgres/", config.Retention{KeepLast: 5}, now)
	if err != nil {
		t.Fatal(err)
	}
	if len(deleted) != 7 {
		t.Fatalf("want 7 pruned, got %d", len(deleted))
	}
	remaining, err := Backups(ctx, l, "j/postgres/")
	if err != nil {
		t.Fatal(err)
	}
	if len(remaining) != 5 {
		t.Fatalf("want 5 remaining, got %d", len(remaining))
	}
}

func TestBackupsSkipsForeignFiles(t *testing.T) {
	ctx := context.Background()
	root := t.TempDir()
	l := &Local{root: root}
	files := map[string]string{
		"j/postgres/j-postgres-20261017-020000.dump.enc": "a",
		"j/postgres/j-postgres-20261016-020000.dump.enc": "b",
		"j/postgres/notes.txt":                          "c",
	}
	for k, v := range files {
		if err := l.Put(ctx, k, bytes.NewReader([]byte(v)), int64(len(v))); err != nil {
			t.Fatal(err)
		}
	}
	backups, err := Backups(ctx, l, "j/postgres/")
	if err != nil {
		t.Fatal(err)
	}
	if len(backups) != 2 {
		t.Fatalf("want 2 parsed backups, got %d", len(backups))
	}
	if !backups[0].Time.After(backups[1].Time) {
		t.Fatal("backups should be newest-first")
	}
}
