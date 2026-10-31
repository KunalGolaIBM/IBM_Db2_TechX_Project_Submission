// Package store abstracts backup destinations behind a Backend interface.
package store

import (
	"context"
	"fmt"
	"io"
	"os"
	"path"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
	"github.com/miriyaladhanwinn/dbhaven/internal/config"
	"github.com/miriyaladhanwinn/dbhaven/internal/retention"
)

// Object is a stored backup artifact.
type Object struct {
	Key     string
	Size    int64
	ModTime time.Time
}

// Backend stores and retrieves backup files.
type Backend interface {
	// Put stores r (size bytes) at key.
	Put(ctx context.Context, key string, r io.Reader, size int64) error
	// Get opens key for reading.
	Get(ctx context.Context, key string) (io.ReadCloser, int64, error)
	// List returns objects under prefix, sorted by key.
	List(ctx context.Context, prefix string) ([]Object, error)
	// Delete removes key.
	Delete(ctx context.Context, key string) error
	// Describe returns a human-readable label for logs.
	Describe() string
}

// New builds the backend for a destination and returns the key prefix
// under which this job's backups live.
func New(d config.Destination, jobName, dbType string) (Backend, string, error) {
	switch d.Type {
	case config.DestLocal:
		return &Local{root: d.Path}, path.Join(jobName, dbType) + "/", nil
	case config.DestS3:
		b, err := newS3(d)
		if err != nil {
			return nil, "", err
		}
		return b, S3Key(d.Prefix, jobName, dbType, ""), nil
	default:
		return nil, "", fmt.Errorf("unknown destination type %q", d.Type)
	}
}

// S3Key builds the object key for a backup file. The result is always a
// clean relative path (no leading slash, no double slashes).
func S3Key(prefix, job, dbType, filename string) string {
	return strings.TrimPrefix(path.Join(prefix, job, dbType, filename), "/")
}

// Backups lists objects under prefix and parses them into retention.Backups,
// skipping files whose names don't carry a timestamp.
func Backups(ctx context.Context, b Backend, prefix string) ([]retention.Backup, error) {
	objs, err := b.List(ctx, prefix)
	if err != nil {
		return nil, err
	}
	var out []retention.Backup
	for _, o := range objs {
		ts, err := retention.ParseTime(o.Key)
		if err != nil {
			continue // ignore foreign files
		}
		out = append(out, retention.Backup{
			Name: path.Base(o.Key),
			Time: ts,
			Size: o.Size,
		})
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Time.After(out[j].Time) })
	return out, nil
}

// Find locates an object by backup file name under prefix.
func Find(ctx context.Context, b Backend, prefix, filename string) (Object, error) {
	objs, err := b.List(ctx, prefix)
	if err != nil {
		return Object{}, err
	}
	for _, o := range objs {
		if path.Base(o.Key) == filename {
			return o, nil
		}
	}
	return Object{}, fmt.Errorf("backup %q not found under %q", filename, prefix)
}

// Prune deletes backups per the retention policy, returning deleted keys.
func Prune(ctx context.Context, b Backend, prefix string, r config.Retention, now time.Time) ([]string, error) {
	backups, err := Backups(ctx, b, prefix)
	if err != nil {
		return nil, err
	}
	_, del := retention.PlanPrune(backups, r, now)
	var deleted []string
	for _, d := range del {
		obj, err := Find(ctx, b, prefix, d.Name)
		if err != nil {
			continue
		}
		if err := b.Delete(ctx, obj.Key); err != nil {
			return deleted, fmt.Errorf("delete %q: %w", obj.Key, err)
		}
		deleted = append(deleted, obj.Key)
	}
	return deleted, nil
}

// Local stores backups on the local filesystem.
type Local struct{ root string }

func (l *Local) Describe() string { return "local:" + l.root }

func (l *Local) fullPath(key string) string {
	return filepath.Join(l.root, filepath.FromSlash(key))
}

func (l *Local) Put(ctx context.Context, key string, r io.Reader, size int64) error {
	p := l.fullPath(key)
	if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
		return err
	}
	tmp := p + ".tmp"
	f, err := os.OpenFile(tmp, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0o600)
	if err != nil {
		return err
	}
	if _, err := io.Copy(f, r); err != nil {
		f.Close()
		os.Remove(tmp)
		return err
	}
	if err := f.Close(); err != nil {
		os.Remove(tmp)
		return err
	}
	return os.Rename(tmp, p)
}

func (l *Local) Get(ctx context.Context, key string) (io.ReadCloser, int64, error) {
	p := l.fullPath(key)
	f, err := os.Open(p)
	if err != nil {
		return nil, 0, err
	}
	info, err := f.Stat()
	if err != nil {
		f.Close()
		return nil, 0, err
	}
	return f, info.Size(), nil
}

func (l *Local) List(ctx context.Context, prefix string) ([]Object, error) {
	dir := l.fullPath(prefix)
	var out []Object
	err := filepath.Walk(dir, func(p string, info os.FileInfo, err error) error {
		if err != nil {
			if os.IsNotExist(err) {
				return nil
			}
			return err
		}
		if info.IsDir() || strings.HasSuffix(p, ".tmp") {
			return nil
		}
		rel, err := filepath.Rel(l.root, p)
		if err != nil {
			return err
		}
		out = append(out, Object{
			Key:     filepath.ToSlash(rel),
			Size:    info.Size(),
			ModTime: info.ModTime(),
		})
		return nil
	})
	if err != nil {
		return nil, err
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Key < out[j].Key })
	return out, nil
}

func (l *Local) Delete(ctx context.Context, key string) error {
	return os.Remove(l.fullPath(key))
}

// S3 stores backups in an S3-compatible bucket via minio-go.
type S3 struct {
	client *minio.Client
	bucket string
}

func newS3(d config.Destination) (*S3, error) {
	client, err := minio.New(d.Endpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(d.AccessKey, d.SecretKey, ""),
		Secure: d.UseSSLOrDefault(),
		Region: d.Region,
	})
	if err != nil {
		return nil, fmt.Errorf("s3 client: %w", err)
	}
	return &S3{client: client, bucket: d.Bucket}, nil
}

func (s *S3) Describe() string { return "s3://" + s.bucket }

func (s *S3) ensureBucket(ctx context.Context) error {
	exists, err := s.client.BucketExists(ctx, s.bucket)
	if err != nil {
		return err
	}
	if !exists {
		if err := s.client.MakeBucket(ctx, s.bucket, minio.MakeBucketOptions{}); err != nil {
			return fmt.Errorf("create bucket %q: %w", s.bucket, err)
		}
	}
	return nil
}

func (s *S3) Put(ctx context.Context, key string, r io.Reader, size int64) error {
	if err := s.ensureBucket(ctx); err != nil {
		return err
	}
	_, err := s.client.PutObject(ctx, s.bucket, key, r, size, minio.PutObjectOptions{
		ContentType: "application/octet-stream",
	})
	return err
}

func (s *S3) Get(ctx context.Context, key string) (io.ReadCloser, int64, error) {
	obj, err := s.client.GetObject(ctx, s.bucket, key, minio.GetObjectOptions{})
	if err != nil {
		return nil, 0, err
	}
	info, err := obj.Stat()
	if err != nil {
		obj.Close()
		return nil, 0, err
	}
	return obj, info.Size, nil
}

func (s *S3) List(ctx context.Context, prefix string) ([]Object, error) {
	var out []Object
	for info := range s.client.ListObjects(ctx, s.bucket, minio.ListObjectsOptions{Prefix: prefix, Recursive: true}) {
		if info.Err != nil {
			return nil, info.Err
		}
		out = append(out, Object{Key: info.Key, Size: info.Size, ModTime: info.LastModified})
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Key < out[j].Key })
	return out, nil
}

func (s *S3) Delete(ctx context.Context, key string) error {
	return s.client.RemoveObject(ctx, s.bucket, key, minio.RemoveObjectOptions{})
}
