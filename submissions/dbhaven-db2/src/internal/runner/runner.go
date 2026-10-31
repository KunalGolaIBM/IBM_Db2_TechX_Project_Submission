// Package runner executes a backup job end to end:
// dump -> (gzip) -> (encrypt) -> store to every destination -> prune old backups.
package runner

import (
	"compress/gzip"
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"
	"strings"
	"time"

	"github.com/miriyaladhanwinn/dbhaven/internal/config"
	"github.com/miriyaladhanwinn/dbhaven/internal/crypto"
	"github.com/miriyaladhanwinn/dbhaven/internal/dump"
	"github.com/miriyaladhanwinn/dbhaven/internal/store"
)

// Result summarizes one completed job run.
type Result struct {
	Job      string
	FileName string
	Bytes    int64 // final stored size per destination (pre-encryption stream size varies)
	Dests    []string
	Pruned   []string
}

// fileName builds the backup file name: <job>-<type>-YYYYMMDD-HHMMSS.<ext>[.enc]
func fileName(job *config.Job, encrypted bool) string {
	ts := time.Now().Format("20060102-150405")
	var ext string
	switch job.Type {
	case config.TypePostgres:
		ext = "dump"
	case config.TypeMongo:
		ext = "archive.gz"
	default:
		ext = "sql.gz"
	}
	name := fmt.Sprintf("%s-%s-%s.%s", job.Name, job.Type, ts, ext)
	if encrypted {
		name += ".enc"
	}
	return name
}

// resolveKey loads the AES-256 key per the encryption config.
// Returns nil when encryption is not configured.
func resolveKey(ec config.EncryptionConfig) ([]byte, error) {
	switch {
	case ec.KeyFile != "":
		return crypto.LoadKeyFile(ec.KeyFile)
	case ec.KeyEnv != "":
		val, ok := os.LookupEnv(ec.KeyEnv)
		if !ok || val == "" {
			return nil, fmt.Errorf("encryption: env var %q not set", ec.KeyEnv)
		}
		material, err := crypto.ParseKeyMaterial(val)
		if err != nil {
			return nil, err
		}
		return crypto.DeriveKey(material), nil
	default:
		return nil, nil
	}
}

// RunJob executes one backup job.
func RunJob(ctx context.Context, cfg *config.Config, job *config.Job, log *slog.Logger) (*Result, error) {
	dumper, err := dump.ForType(job.Type)
	if err != nil {
		return nil, err
	}
	key, err := resolveKey(cfg.Encryption)
	if err != nil {
		return nil, err
	}
	encrypted := key != nil
	if !encrypted {
		log.Warn("encryption not configured; backups will be stored in plaintext")
	}

	name := fileName(job, encrypted)
	log.Info("starting backup", "job", job.Name, "file", name, "tool", dumper.ToolName())

	// Stage 1: dump to a temp file (gzip unless pg_dump -Fc, already compressed).
	raw, err := os.CreateTemp("", "dbhaven-dump-*")
	if err != nil {
		return nil, err
	}
	rawName := raw.Name()
	defer os.Remove(rawName)

	var dumpOut io.Writer = raw
	var gz *gzip.Writer
	if job.Type != config.TypePostgres {
		gz = gzip.NewWriter(raw)
		dumpOut = gz
	}
	log.Info("dumping database", "job", job.Name)
	if err := dumper.Dump(ctx, job.DSN, job.ExtraArgs, dumpOut); err != nil {
		raw.Close()
		return nil, fmt.Errorf("dump: %w", err)
	}
	if gz != nil {
		if err := gz.Close(); err != nil {
			raw.Close()
			return nil, fmt.Errorf("gzip: %w", err)
		}
	}
	if err := raw.Close(); err != nil {
		return nil, err
	}

	// Stage 2: encrypt (optional) into a second temp file.
	staged := rawName
	if encrypted {
		enc, err := os.CreateTemp("", "dbhaven-enc-*")
		if err != nil {
			return nil, err
		}
		encName := enc.Name()
		enc.Close()
		defer os.Remove(encName)
		log.Info("encrypting backup", "job", job.Name)
		if err := crypto.EncryptFile(key, rawName, encName); err != nil {
			return nil, fmt.Errorf("encrypt: %w", err)
		}
		staged = encName
	}

	st, err := os.Stat(staged)
	if err != nil {
		return nil, err
	}

	// Stage 3: upload to every destination.
	res := &Result{Job: job.Name, FileName: name, Bytes: st.Size()}
	for i := range job.Destinations {
		d := &job.Destinations[i]
		be, prefix, err := store.New(*d, job.Name, job.Type)
		if err != nil {
			return nil, err
		}
		f, err := os.Open(staged)
		if err != nil {
			return nil, err
		}
		objKey := joinKey(prefix, name)
		log.Info("uploading backup", "job", job.Name, "dest", be.Describe(), "key", objKey)
		if err := be.Put(ctx, objKey, f, st.Size()); err != nil {
			f.Close()
			return nil, fmt.Errorf("upload to %s: %w", be.Describe(), err)
		}
		f.Close()
		res.Dests = append(res.Dests, be.Describe())

		// Stage 4: prune old backups at this destination.
		deleted, err := store.Prune(ctx, be, prefix, job.Retention, time.Now())
		if err != nil {
			log.Warn("prune failed", "dest", be.Describe(), "err", err)
		} else if len(deleted) > 0 {
			log.Info("pruned old backups", "dest", be.Describe(), "count", len(deleted))
			res.Pruned = append(res.Pruned, deleted...)
		}
	}

	log.Info("backup complete", "job", job.Name, "file", name, "bytes", st.Size())
	return res, nil
}

// joinKey appends the file name to a backend prefix. Both backends use
// slash-separated keys, so this is uniform.
func joinKey(prefix, name string) string {
	if prefix == "" {
		return name
	}
	if prefix[len(prefix)-1] == '/' {
		return prefix + name
	}
	return prefix + "/" + name
}

// Restore downloads filename from the first destination that has it,
// decrypts/decompresses as needed, and loads it into targetDSN.
func Restore(ctx context.Context, cfg *config.Config, job *config.Job, filename, targetDSN string, log *slog.Logger) error {
	dumper, err := dump.ForType(job.Type)
	if err != nil {
		return err
	}
	key, err := resolveKey(cfg.Encryption)
	if err != nil {
		return err
	}
	encryptedName := strings.HasSuffix(filename, ".enc")
	if encryptedName && key == nil {
		return fmt.Errorf("backup is encrypted but no encryption key is configured")
	}

	var src io.ReadCloser
	var srcSize int64
	for i := range job.Destinations {
		d := &job.Destinations[i]
		be, prefix, err := store.New(*d, job.Name, job.Type)
		if err != nil {
			return err
		}
		obj, err := store.Find(ctx, be, prefix, filename)
		if err != nil {
			log.Info("backup not at destination, trying next", "dest", be.Describe())
			continue
		}
		log.Info("downloading backup", "dest", be.Describe(), "key", obj.Key)
		rc, size, err := be.Get(ctx, obj.Key)
		if err != nil {
			return fmt.Errorf("download: %w", err)
		}
		src, srcSize = rc, size
		break
	}
	if src == nil {
		return fmt.Errorf("backup %q not found in any destination", filename)
	}
	defer src.Close()

	// Stage to a temp file, decrypting if needed.
	staged, err := os.CreateTemp("", "dbhaven-restore-*")
	if err != nil {
		return err
	}
	stagedName := staged.Name()
	defer os.Remove(stagedName)
	if encryptedName {
		staged.Close()
		tmp, err := os.CreateTemp("", "dbhaven-restore-enc-*")
		if err != nil {
			return err
		}
		tmpName := tmp.Name()
		tmp.Close()
		defer os.Remove(tmpName)
		out, err := os.Create(tmpName)
		if err != nil {
			return err
		}
		if _, err := io.Copy(out, src); err != nil {
			out.Close()
			return fmt.Errorf("stage download: %w", err)
		}
		out.Close()
		log.Info("decrypting backup")
		if err := crypto.DecryptFile(key, tmpName, stagedName); err != nil {
			return fmt.Errorf("decrypt: %w", err)
		}
	} else {
		if _, err := io.Copy(staged, src); err != nil {
			staged.Close()
			return fmt.Errorf("stage download: %w", err)
		}
		staged.Close()
	}

	// Decompress unless this is a pg_dump custom-format archive.
	var in io.Reader
	f, err := os.Open(stagedName)
	if err != nil {
		return err
	}
	defer f.Close()
	in = f
	if job.Type != config.TypePostgres {
		log.Info("decompressing backup")
		gz, err := gzip.NewReader(f)
		if err != nil {
			return fmt.Errorf("gunzip: %w", err)
		}
		defer gz.Close()
		in = gz
	}

	log.Info("restoring database", "job", job.Name, "target", redactDSN(targetDSN), "bytes", srcSize)
	if err := dumper.Restore(ctx, targetDSN, job.ExtraArgs, in); err != nil {
		return fmt.Errorf("restore: %w", err)
	}
	log.Info("restore complete", "job", job.Name)
	return nil
}

// redactDSN hides the password in a DSN for logs.
func redactDSN(dsn string) string {
	if i := strings.Index(dsn, "@"); i >= 0 {
		if j := strings.LastIndex(dsn[:i], ":"); j >= 0 {
			if k := strings.Index(dsn, "://"); k >= 0 && k < j {
				return dsn[:j+1] + "***" + dsn[i:]
			}
		}
	}
	return dsn
}
