// Package dump shells out to the native database tools (pg_dump, mysqldump,
// mongodump) for backup and restore. The tools must be installed on PATH;
// dbhaven never reimplements their wire protocols.
package dump

import (
	"context"
	"fmt"
	"io"
	"net/url"
	"os"
	"os/exec"
	"strings"

	"github.com/miriyaladhanwinn/dbhaven/internal/config"
)

// Dumper dumps a database to w and restores one from r.
type Dumper interface {
	// Dump streams a logical backup to w.
	Dump(ctx context.Context, dsn string, extra []string, w io.Writer) error
	// Restore loads a backup from r into the database at dsn.
	Restore(ctx context.Context, dsn string, extra []string, r io.Reader) error
	// ToolName is the executable used for dumps (for --dry-run display).
	ToolName() string
	// DumpArgs returns the exact argv the dumper would run (for --dry-run).
	DumpArgs(dsn string, extra []string) ([]string, error)
}

// ForType returns the dumper for a configured database type.
func ForType(t string) (Dumper, error) {
	switch t {
	case config.TypePostgres:
		return postgres{}, nil
	case config.TypeMySQL, config.TypeMariaDB:
		return mysql{}, nil
	case config.TypeMongo:
		return mongo{}, nil
	case config.TypeDb2:
		return db2{}, nil
	default:
		return nil, fmt.Errorf("unsupported database type %q", t)
	}
}

func lookPath(tool string) error {
	if _, err := exec.LookPath(tool); err != nil {
		return fmt.Errorf("%s not found on PATH: install the database client tools first", tool)
	}
	return nil
}

func run(ctx context.Context, name string, args []string, stdin io.Reader, stdout io.Writer) error {
	if err := lookPath(name); err != nil {
		return err
	}
	cmd := exec.CommandContext(ctx, name, args...)
	cmd.Stdin = stdin
	cmd.Stdout = stdout
	var stderr strings.Builder
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		msg := strings.TrimSpace(stderr.String())
		if msg == "" {
			msg = err.Error()
		}
		return fmt.Errorf("%s failed: %s", name, firstLine(msg))
	}
	return nil
}

func firstLine(s string) string {
	if i := strings.IndexByte(s, '\n'); i >= 0 {
		return s[:i]
	}
	return s
}

// restoreViaTempFile materializes r into a temp file and runs tool with the
// file path appended to args. Needed by tools (like pg_restore) that cannot
// read custom-format archives from stdin.
func restoreViaTempFile(ctx context.Context, tool string, args []string, r io.Reader) error {
	tmp, err := os.CreateTemp("", "dbhaven-restore-*")
	if err != nil {
		return fmt.Errorf("temp file: %w", err)
	}
	tmpName := tmp.Name()
	if _, err := io.Copy(tmp, r); err != nil {
		tmp.Close()
		os.Remove(tmpName)
		return fmt.Errorf("stage restore file: %w", err)
	}
	if err := tmp.Close(); err != nil {
		os.Remove(tmpName)
		return err
	}
	defer os.Remove(tmpName)
	return run(ctx, tool, append(args, tmpName), nil, io.Discard)
}

// postgres uses pg_dump -Fc (compressed custom format) and pg_restore.
type postgres struct{}

func (postgres) ToolName() string { return "pg_dump" }

func (postgres) DumpArgs(dsn string, extra []string) ([]string, error) {
	args := append([]string{"--dbname=" + dsn, "--format=custom", "--no-owner"}, extra...)
	return args, nil
}

func (p postgres) Dump(ctx context.Context, dsn string, extra []string, w io.Writer) error {
	args, _ := p.DumpArgs(dsn, extra)
	return run(ctx, "pg_dump", args, nil, w)
}

func (postgres) Restore(ctx context.Context, dsn string, extra []string, r io.Reader) error {
	// pg_restore needs a seekable file for custom-format archives.
	return restoreViaTempFile(ctx, "pg_restore", append([]string{
		"--dbname=" + dsn, "--clean", "--if-exists", "--no-owner",
	}, extra...), r)
}

// mysql covers MySQL and MariaDB via mysqldump/mysql.
type mysql struct{}

func (mysql) ToolName() string { return "mysqldump" }

type mysqlConn struct {
	host, port, user, pass, db string
}

func parseMySQLDSN(dsn string) (mysqlConn, error) {
	u, err := url.Parse(dsn)
	if err != nil {
		return mysqlConn{}, fmt.Errorf("parse mysql dsn: %w", err)
	}
	if u.Scheme != "mysql" {
		return mysqlConn{}, fmt.Errorf("mysql dsn must look like mysql://user:pass@host:port/db")
	}
	c := mysqlConn{host: u.Hostname(), port: u.Port(), db: strings.TrimPrefix(u.Path, "/")}
	c.user = u.User.Username()
	c.pass, _ = u.User.Password()
	if c.host == "" {
		c.host = "127.0.0.1"
	}
	if c.port == "" {
		c.port = "3306"
	}
	if c.db == "" {
		return mysqlConn{}, fmt.Errorf("mysql dsn must include a database name")
	}
	return c, nil
}

func (c mysqlConn) flags() []string {
	return []string{
		"--host=" + c.host,
		"--port=" + c.port,
		"--user=" + c.user,
		"--password=" + c.pass,
		"--single-transaction",
		"--routines",
		"--events",
	}
}

func (mysql) DumpArgs(dsn string, extra []string) ([]string, error) {
	c, err := parseMySQLDSN(dsn)
	if err != nil {
		return nil, err
	}
	return append(append(c.flags(), "--databases", c.db), extra...), nil
}

func (m mysql) Dump(ctx context.Context, dsn string, extra []string, w io.Writer) error {
	args, err := m.DumpArgs(dsn, extra)
	if err != nil {
		return err
	}
	return run(ctx, "mysqldump", args, nil, w)
}

func (mysql) Restore(ctx context.Context, dsn string, extra []string, r io.Reader) error {
	c, err := parseMySQLDSN(dsn)
	if err != nil {
		return err
	}
	args := append(c.flags(), extra...)
	return run(ctx, "mysql", args, r, io.Discard)
}

// mongo uses mongodump/mongorestore --archive for streaming.
type mongo struct{}

func (mongo) ToolName() string { return "mongodump" }

func (mongo) DumpArgs(dsn string, extra []string) ([]string, error) {
	return append([]string{"--uri=" + dsn, "--archive"}, extra...), nil
}

func (m mongo) Dump(ctx context.Context, dsn string, extra []string, w io.Writer) error {
	args, _ := m.DumpArgs(dsn, extra)
	return run(ctx, "mongodump", args, nil, w)
}

func (mongo) Restore(ctx context.Context, dsn string, extra []string, r io.Reader) error {
	args := append([]string{"--uri=" + dsn, "--archive"}, extra...)
	return run(ctx, "mongorestore", args, r, io.Discard)
}
