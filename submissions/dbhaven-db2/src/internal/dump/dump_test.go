package dump

import (
	"strings"
	"testing"
)

func TestForType(t *testing.T) {
	for _, typ := range []string{"postgres", "mysql", "mariadb", "mongo", "db2"} {
		if _, err := ForType(typ); err != nil {
			t.Fatalf("ForType(%q): %v", typ, err)
		}
	}
	if _, err := ForType("oracle"); err == nil {
		t.Fatal("expected error for unknown type")
	}
}

func TestPostgresDumpArgs(t *testing.T) {
	d, _ := ForType("postgres")
	args, err := d.DumpArgs("postgres://u:p@h/db", []string{"--table=t"})
	if err != nil {
		t.Fatal(err)
	}
	joined := strings.Join(args, " ")
	for _, want := range []string{"--dbname=postgres://u:p@h/db", "--format=custom", "--table=t"} {
		if !strings.Contains(joined, want) {
			t.Fatalf("args %q missing %q", joined, want)
		}
	}
	if d.ToolName() != "pg_dump" {
		t.Fatalf("wrong tool: %s", d.ToolName())
	}
}

func TestMySQLDSNParsing(t *testing.T) {
	d, _ := ForType("mysql")
	args, err := d.DumpArgs("mysql://bob:s3cret@db.local:3307/shop", nil)
	if err != nil {
		t.Fatal(err)
	}
	joined := strings.Join(args, " ")
	for _, want := range []string{"--host=db.local", "--port=3307", "--user=bob", "--password=s3cret", "--databases", "shop"} {
		if !strings.Contains(joined, want) {
			t.Fatalf("args %q missing %q", joined, want)
		}
	}
	// Defaults: host and port.
	args2, err := d.DumpArgs("mysql://bob@h/db", nil)
	if err != nil {
		t.Fatal(err)
	}
	joined2 := strings.Join(args2, " ")
	if !strings.Contains(joined2, "--host=h") || !strings.Contains(joined2, "--port=3306") {
		t.Fatalf("defaults not applied: %q", joined2)
	}
}

func TestMySQLDSNBad(t *testing.T) {
	d, _ := ForType("mysql")
	for _, bad := range []string{
		"mysql://bob@h",      // no database
		"postgres://bob@h/d", // wrong scheme
		"://broken",
	} {
		if _, err := d.DumpArgs(bad, nil); err == nil {
			t.Fatalf("expected error for dsn %q", bad)
		}
	}
}

func TestMongoDumpArgs(t *testing.T) {
	d, _ := ForType("mongo")
	args, err := d.DumpArgs("mongodb://h:27017/db", nil)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Join(args, " ") != "--uri=mongodb://h:27017/db --archive" {
		t.Fatalf("unexpected args: %q", args)
	}
}

func TestMissingToolError(t *testing.T) {
	d, _ := ForType("postgres")
	// pg_dump is almost certainly absent in this environment; either way the
	// call must not panic and must surface a usable error or succeed.
	_ = d
	if err := lookPath("definitely-not-a-real-tool-xyz"); err == nil {
		t.Fatal("expected error for missing tool")
	} else if !strings.Contains(err.Error(), "not found on PATH") {
		t.Fatalf("error should name the missing tool: %v", err)
	}
}

func TestDb2DumpArgs(t *testing.T) {
	d, err := ForType("db2")
	if err != nil {
		t.Fatal(err)
	}
	if d.ToolName() != "db2" {
		t.Fatalf("expected tool 'db2', got %s", d.ToolName())
	}
	args, err := d.DumpArgs("db2://db2inst1:password@127.0.0.1:50000/sample", []string{"online"})
	if err != nil {
		t.Fatal(err)
	}
	joined := strings.Join(args, " ")
	if !strings.Contains(joined, "backup database sample online to -") {
		t.Fatalf("unexpected db2 dump args: %s", joined)
	}
}
