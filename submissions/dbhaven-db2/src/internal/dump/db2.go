package dump

import (
	"context"
	"fmt"
	"io"
	"net/url"
	"strings"
)

// db2 covers IBM Db2 via the db2 command-line client.
type db2 struct{}

func (db2) ToolName() string { return "db2" }

type db2Conn struct {
	host, port, user, pass, db string
}

func parseDb2DSN(dsn string) (db2Conn, error) {
	u, err := url.Parse(dsn)
	if err != nil {
		return db2Conn{}, fmt.Errorf("parse db2 dsn: %w", err)
	}
	if u.Scheme != "db2" {
		return db2Conn{}, fmt.Errorf("db2 dsn must look like db2://user:pass@host:port/db")
	}
	c := db2Conn{host: u.Hostname(), port: u.Port(), db: strings.TrimPrefix(u.Path, "/")}
	if u.User != nil {
		c.user = u.User.Username()
		c.pass, _ = u.User.Password()
	}
	if c.host == "" {
		c.host = "127.0.0.1"
	}
	if c.port == "" {
		c.port = "50000"
	}
	if c.db == "" {
		return db2Conn{}, fmt.Errorf("db2 dsn must include a database name")
	}
	return c, nil
}

func (db2) DumpArgs(dsn string, extra []string) ([]string, error) {
	c, err := parseDb2DSN(dsn)
	if err != nil {
		return nil, err
	}
	backupCmd := fmt.Sprintf("backup database %s to -", c.db)
	if len(extra) > 0 {
		backupCmd = fmt.Sprintf("backup database %s %s to -", c.db, strings.Join(extra, " "))
	}
	return []string{"-v", backupCmd}, nil
}

func (d db2) Dump(ctx context.Context, dsn string, extra []string, w io.Writer) error {
	args, err := d.DumpArgs(dsn, extra)
	if err != nil {
		return err
	}
	return run(ctx, "db2", args, nil, w)
}

func (db2) Restore(ctx context.Context, dsn string, extra []string, r io.Reader) error {
	c, err := parseDb2DSN(dsn)
	if err != nil {
		return err
	}
	restoreCmd := fmt.Sprintf("restore database %s from - without prompting", c.db)
	if len(extra) > 0 {
		restoreCmd = fmt.Sprintf("restore database %s %s from - without prompting", c.db, strings.Join(extra, " "))
	}
	return run(ctx, "db2", []string{"-v", restoreCmd}, r, io.Discard)
}
