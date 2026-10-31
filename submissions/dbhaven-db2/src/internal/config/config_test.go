package config

import (
	"os"
	"path/filepath"
	"testing"
)

const validYAML = `
encryption:
  key_env: DBHAVEN_KEY
jobs:
  - name: main-postgres
    type: postgres
    dsn: "postgres://u:p@localhost:5432/db?sslmode=disable"
    schedule: "0 2 * * *"
    destinations:
      - type: local
        path: /var/backups/dbhaven
      - type: s3
        endpoint: minio.local:9000
        bucket: dbhaven
        prefix: prod/
        access_key: minio
        secret_key: minio123
        use_ssl: false
    retention:
      daily: 7
      weekly: 4
      monthly: 6
  - name: legacy-mysql
    type: mysql
    dsn: "mysql://u:p@localhost:3306/app"
    destinations:
      - type: local
        path: /var/backups/dbhaven
`

func writeTemp(t *testing.T, content string) string {
	t.Helper()
	p := filepath.Join(t.TempDir(), "dbhaven.yaml")
	if err := os.WriteFile(p, []byte(content), 0o600); err != nil {
		t.Fatal(err)
	}
	return p
}

func TestLoadValid(t *testing.T) {
	c, err := Load(writeTemp(t, validYAML))
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if len(c.Jobs) != 2 {
		t.Fatalf("want 2 jobs, got %d", len(c.Jobs))
	}
	j := c.Jobs[0]
	if j.Name != "main-postgres" || j.Type != "postgres" {
		t.Fatalf("unexpected job: %+v", j)
	}
	if len(j.Destinations) != 2 {
		t.Fatalf("want 2 destinations, got %d", len(j.Destinations))
	}
	s3 := j.Destinations[1]
	if s3.UseSSLOrDefault() {
		t.Fatal("use_ssl: false should disable TLS")
	}
	if j.Retention.Daily != 7 || j.Retention.Weekly != 4 || j.Retention.Monthly != 6 {
		t.Fatalf("unexpected retention: %+v", j.Retention)
	}
	// Second job has no retention: default keep_last=10 applies.
	if c.Jobs[1].Retention.KeepLast != 10 {
		t.Fatalf("want default keep_last=10, got %+v", c.Jobs[1].Retention)
	}
	// S3 default is TLS on.
	if (&Destination{Type: "s3"}).UseSSLOrDefault() != true {
		t.Fatal("s3 default should use TLS")
	}
}

func TestLoadFailures(t *testing.T) {
	cases := []struct {
		name string
		yaml string
	}{
		{"both key sources", "encryption:\n  key_file: a\n  key_env: b\njobs:\n  - name: j\n    type: postgres\n    dsn: x\n    destinations:\n      - {type: local, path: /tmp}\n"},
		{"no jobs", "jobs: []\n"},
		{"unknown type", "jobs:\n  - name: j\n    type: oracle\n    dsn: x\n    destinations:\n      - {type: local, path: /tmp}\n"},
		{"bad cron", "jobs:\n  - name: j\n    type: postgres\n    dsn: x\n    schedule: not-a-cron\n    destinations:\n      - {type: local, path: /tmp}\n"},
		{"no destinations", "jobs:\n  - name: j\n    type: postgres\n    dsn: x\n    destinations: []\n"},
		{"local without path", "jobs:\n  - name: j\n    type: postgres\n    dsn: x\n    destinations:\n      - {type: local}\n"},
		{"s3 without bucket", "jobs:\n  - name: j\n    type: postgres\n    dsn: x\n    destinations:\n      - {type: s3, endpoint: e}\n"},
		{"duplicate names", "jobs:\n  - name: j\n    type: postgres\n    dsn: x\n    destinations:\n      - {type: local, path: /tmp}\n  - name: j\n    type: mysql\n    dsn: y\n    destinations:\n      - {type: local, path: /tmp}\n"},
		{"missing dsn", "jobs:\n  - name: j\n    type: postgres\n    destinations:\n      - {type: local, path: /tmp}\n"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if _, err := Load(writeTemp(t, tc.yaml)); err == nil {
				t.Fatalf("expected error for %s", tc.name)
			}
		})
	}
}

func TestLoadMissingFile(t *testing.T) {
	if _, err := Load("/nonexistent/dbhaven.yaml"); err == nil {
		t.Fatal("expected error for missing file")
	}
}

func TestFindJob(t *testing.T) {
	c, err := Load(writeTemp(t, validYAML))
	if err != nil {
		t.Fatal(err)
	}
	if _, err := c.FindJob("main-postgres"); err != nil {
		t.Fatalf("FindJob: %v", err)
	}
	if _, err := c.FindJob("nope"); err == nil {
		t.Fatal("expected error for unknown job")
	}
}
