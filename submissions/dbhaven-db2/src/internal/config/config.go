// Package config loads and validates dbhaven's YAML configuration file.
package config

import (
	"fmt"
	"os"
	"strings"

	"github.com/robfig/cron/v3"
	"gopkg.in/yaml.v3"
)

// Supported database types.
const (
	TypePostgres = "postgres"
	TypeMySQL    = "mysql"
	TypeMariaDB  = "mariadb"
	TypeMongo    = "mongo"
	TypeDb2      = "db2"
)

// Supported destination types.
const (
	DestLocal = "local"
	DestS3    = "s3"
)

// Config is the root of dbhaven.yaml.
type Config struct {
	Encryption EncryptionConfig `yaml:"encryption"`
	Jobs       []Job             `yaml:"jobs"`
}

// EncryptionConfig selects where the AES-256 key comes from.
// Exactly one of KeyFile or KeyEnv may be set; if neither is set,
// backups are stored unencrypted (with a warning at runtime).
type EncryptionConfig struct {
	KeyFile string `yaml:"key_file"`
	KeyEnv  string `yaml:"key_env"`
}

// Job is a single named backup job.
type Job struct {
	Name         string        `yaml:"name"`
	Type         string        `yaml:"type"`
	DSN          string        `yaml:"dsn"`
	Schedule     string        `yaml:"schedule,omitempty"`
	Destinations []Destination `yaml:"destinations"`
	Retention    Retention     `yaml:"retention"`
	ExtraArgs    []string      `yaml:"extra_args,omitempty"`
}

// Destination is one place a backup is stored.
type Destination struct {
	Type      string `yaml:"type"`
	Path      string `yaml:"path,omitempty"`       // local
	Endpoint  string `yaml:"endpoint,omitempty"`   // s3
	Bucket    string `yaml:"bucket,omitempty"`     // s3
	Prefix    string `yaml:"prefix,omitempty"`     // s3
	AccessKey string `yaml:"access_key,omitempty"` // s3
	SecretKey string `yaml:"secret_key,omitempty"` // s3
	Region    string `yaml:"region,omitempty"`     // s3
	UseSSL    *bool  `yaml:"use_ssl,omitempty"`    // s3, default true
}

// UseSSLOrDefault reports whether the S3 endpoint should use TLS.
func (d Destination) UseSSLOrDefault() bool {
	if d.UseSSL == nil {
		return true
	}
	return *d.UseSSL
}

// Retention controls GFS pruning. KeepLast is a simple alternative to the
// daily/weekly/monthly tiers; when set it takes precedence.
type Retention struct {
	KeepLast int `yaml:"keep_last,omitempty"`
	Daily    int `yaml:"daily,omitempty"`
	Weekly   int `yaml:"weekly,omitempty"`
	Monthly  int `yaml:"monthly,omitempty"`
}

// HasPolicy reports whether any retention knob is set.
func (r Retention) HasPolicy() bool {
	return r.KeepLast > 0 || r.Daily > 0 || r.Weekly > 0 || r.Monthly > 0
}

// Load reads, parses and validates the config file at path.
func Load(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read config %q: %w", path, err)
	}
	var c Config
	if err := yaml.Unmarshal(data, &c); err != nil {
		return nil, fmt.Errorf("parse config %q: %w", path, err)
	}
	if err := c.Validate(); err != nil {
		return nil, err
	}
	return &c, nil
}

// Validate checks the config for structural errors.
func (c *Config) Validate() error {
	if c.Encryption.KeyFile != "" && c.Encryption.KeyEnv != "" {
		return fmt.Errorf("encryption: set only one of key_file or key_env")
	}
	if len(c.Jobs) == 0 {
		return fmt.Errorf("no backup jobs defined")
	}
	seen := map[string]bool{}
	for i := range c.Jobs {
		j := &c.Jobs[i]
		if strings.TrimSpace(j.Name) == "" {
			return fmt.Errorf("job %d: name is required", i)
		}
		if seen[j.Name] {
			return fmt.Errorf("job %q: duplicate name", j.Name)
		}
		seen[j.Name] = true
		switch j.Type {
		case TypePostgres, TypeMySQL, TypeMariaDB, TypeMongo, TypeDb2:
		default:
			return fmt.Errorf("job %q: unknown type %q (want postgres, mysql, mariadb, mongo or db2)", j.Name, j.Type)
		}
		if strings.TrimSpace(j.DSN) == "" {
			return fmt.Errorf("job %q: dsn is required", j.Name)
		}
		if j.Schedule != "" {
			if _, err := cron.ParseStandard(j.Schedule); err != nil {
				return fmt.Errorf("job %q: invalid cron schedule %q: %w", j.Name, j.Schedule, err)
			}
		}
		if len(j.Destinations) == 0 {
			return fmt.Errorf("job %q: at least one destination is required", j.Name)
		}
		for k := range j.Destinations {
			if err := validateDestination(j.Name, &j.Destinations[k]); err != nil {
				return err
			}
		}
		if !j.Retention.HasPolicy() {
			// Sensible default: keep the 10 most recent backups.
			j.Retention.KeepLast = 10
		}
		if j.Retention.KeepLast < 0 || j.Retention.Daily < 0 || j.Retention.Weekly < 0 || j.Retention.Monthly < 0 {
			return fmt.Errorf("job %q: retention values must not be negative", j.Name)
		}
	}
	return nil
}

func validateDestination(job string, d *Destination) error {
	switch d.Type {
	case DestLocal:
		if strings.TrimSpace(d.Path) == "" {
			return fmt.Errorf("job %q: local destination requires path", job)
		}
	case DestS3:
		if strings.TrimSpace(d.Endpoint) == "" {
			return fmt.Errorf("job %q: s3 destination requires endpoint", job)
		}
		if strings.TrimSpace(d.Bucket) == "" {
			return fmt.Errorf("job %q: s3 destination requires bucket", job)
		}
	default:
		return fmt.Errorf("job %q: unknown destination type %q (want local or s3)", job, d.Type)
	}
	return nil
}

// FindJob returns the job with the given name.
func (c *Config) FindJob(name string) (*Job, error) {
	for i := range c.Jobs {
		if c.Jobs[i].Name == name {
			return &c.Jobs[i], nil
		}
	}
	return nil, fmt.Errorf("no job named %q", name)
}
