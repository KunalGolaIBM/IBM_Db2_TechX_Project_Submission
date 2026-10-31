// Command dbhaven is a database backup CLI: scheduled, encrypted backups
// of PostgreSQL, MySQL/MariaDB and MongoDB to local disk or S3 storage.
package main

import (
	"context"
	"flag"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"sort"
	"strings"
	"syscall"
	"time"

	"github.com/miriyaladhanwinn/dbhaven/internal/config"
	"github.com/miriyaladhanwinn/dbhaven/internal/crypto"
	"github.com/miriyaladhanwinn/dbhaven/internal/dump"
	"github.com/miriyaladhanwinn/dbhaven/internal/runner"
	"github.com/miriyaladhanwinn/dbhaven/internal/scheduler"
	"github.com/miriyaladhanwinn/dbhaven/internal/store"
)

// Version is overridden at build time: -ldflags "-X main.Version=x.y.z".
var Version = "0.1.0-dev"

func main() {
	os.Exit(run(os.Args[1:]))
}

func run(args []string) int {
	if len(args) == 0 || args[0] == "-h" || args[0] == "--help" || args[0] == "help" {
		usage()
		return 0
	}
	if args[0] == "version" || args[0] == "--version" {
		fmt.Println("dbhaven", Version)
		return 0
	}
	cmd, rest := args[0], args[1:]
	var err error
	switch cmd {
	case "backup":
		err = cmdBackup(rest)
	case "schedule":
		err = cmdSchedule(rest)
	case "list":
		err = cmdList(rest)
	case "restore":
		err = cmdRestore(rest)
	case "keygen":
		err = cmdKeygen(rest)
	default:
		fmt.Fprintf(os.Stderr, "unknown command %q\n\n", cmd)
		usage()
		return 2
	}
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		return 1
	}
	return 0
}

func usage() {
	fmt.Print(`dbhaven - scheduled, encrypted database backups

Usage:
  dbhaven [command] [flags]

Commands:
  backup    Run one backup job now
  schedule  Run the scheduler daemon (cron jobs from config)
  list      List existing backups for a job
  restore   Restore a backup into a target database
  keygen    Generate a new AES-256 encryption key file
  version   Print version

Flags:
  -h, --help  Show help

Run 'dbhaven <command> -h' for command flags.
`)
}

// newLogger builds a structured logger.
func newLogger(verbose bool) *slog.Logger {
	level := slog.LevelInfo
	if verbose {
		level = slog.LevelDebug
	}
	return slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: level}))
}

func loadConfig(path string) (*config.Config, error) {
	return config.Load(path)
}

// flagSet builds a FlagSet with the global flags pre-registered.
func flagSet(name string) (*flag.FlagSet, *string, *bool) {
	fs := flag.NewFlagSet(name, flag.ContinueOnError)
	cfgPath := fs.String("config", "dbhaven.yaml", "path to config file")
	verbose := fs.Bool("verbose", false, "debug logging")
	return fs, cfgPath, verbose
}

func cmdBackup(args []string) error {
	fs, cfgPath, verbose := flagSet("backup")
	jobName := fs.String("job", "", "job name to run (required)")
	dryRun := fs.Bool("dry-run", false, "print what would happen without doing it")
	if err := fs.Parse(args); err != nil {
		return err
	}
	log := newLogger(*verbose)
	if *jobName == "" {
		return fmt.Errorf("--job is required")
	}
	cfg, err := loadConfig(*cfgPath)
	if err != nil {
		return err
	}
	job, err := cfg.FindJob(*jobName)
	if err != nil {
		return err
	}
	if *dryRun {
		return printDryRun(cfg, job)
	}
	res, err := runner.RunJob(context.Background(), cfg, job, log)
	if err != nil {
		return err
	}
	fmt.Printf("backup %s stored (%d bytes) -> %s\n", res.FileName, res.Bytes, strings.Join(res.Dests, ", "))
	if len(res.Pruned) > 0 {
		fmt.Printf("pruned %d old backup(s)\n", len(res.Pruned))
	}
	return nil
}

func printDryRun(cfg *config.Config, job *config.Job) error {
	dumper, err := dump.ForType(job.Type)
	if err != nil {
		return err
	}
	dumpArgs, err := dumper.DumpArgs(job.DSN, job.ExtraArgs)
	if err != nil {
		return err
	}
	fmt.Printf("job:        %s (%s)\n", job.Name, job.Type)
	fmt.Printf("dump:       %s %s\n", dumper.ToolName(), strings.Join(dumpArgs, " "))
	fmt.Printf("compress:   %v\n", job.Type != config.TypePostgres)
	enc := "off"
	if cfg.Encryption.KeyFile != "" || cfg.Encryption.KeyEnv != "" {
		enc = "on (AES-256-GCM)"
	}
	fmt.Printf("encryption: %s\n", enc)
	fmt.Println("destinations:")
	for _, d := range job.Destinations {
		switch d.Type {
		case config.DestLocal:
			fmt.Printf("  - local %s\n", d.Path)
		case config.DestS3:
			fmt.Printf("  - s3://%s (endpoint %s, prefix %q)\n", d.Bucket, d.Endpoint, d.Prefix)
		}
	}
	fmt.Printf("retention:  %s\n", retentionString(job.Retention))
	fmt.Println("dry run: no changes made")
	return nil
}

func retentionString(r config.Retention) string {
	if r.KeepLast > 0 {
		return fmt.Sprintf("keep_last=%d", r.KeepLast)
	}
	return fmt.Sprintf("daily=%d weekly=%d monthly=%d", r.Daily, r.Weekly, r.Monthly)
}

func cmdSchedule(args []string) error {
	fs, cfgPath, verbose := flagSet("schedule")
	if err := fs.Parse(args); err != nil {
		return err
	}
	log := newLogger(*verbose)
	cfg, err := loadConfig(*cfgPath)
	if err != nil {
		return err
	}
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()
	return scheduler.Serve(ctx, cfg, log)
}

func cmdList(args []string) error {
	fs, cfgPath, verbose := flagSet("list")
	jobName := fs.String("job", "", "job name (required)")
	if err := fs.Parse(args); err != nil {
		return err
	}
	log := newLogger(*verbose)
	if *jobName == "" {
		return fmt.Errorf("--job is required")
	}
	cfg, err := loadConfig(*cfgPath)
	if err != nil {
		return err
	}
	job, err := cfg.FindJob(*jobName)
	if err != nil {
		return err
	}
	ctx := context.Background()
	type row struct {
		dest, name string
		size       int64
		when       time.Time
	}
	var rows []row
	for i := range job.Destinations {
		d := &job.Destinations[i]
		be, prefix, err := store.New(*d, job.Name, job.Type)
		if err != nil {
			return err
		}
		backups, err := store.Backups(ctx, be, prefix)
		if err != nil {
			log.Warn("list failed", "dest", be.Describe(), "err", err)
			continue
		}
		for _, b := range backups {
			rows = append(rows, row{be.Describe(), b.Name, b.Size, b.Time})
		}
	}
	sort.Slice(rows, func(i, j int) bool { return rows[i].when.After(rows[j].when) })
	if len(rows) == 0 {
		fmt.Println("no backups found")
		return nil
	}
	fmt.Printf("%-28s %-46s %12s  %s\n", "DESTINATION", "FILE", "SIZE", "TAKEN")
	for _, r := range rows {
		fmt.Printf("%-28s %-46s %12s  %s\n",
			trunc(r.dest, 28), r.name, humanSize(r.size), r.when.Format("2006-01-02 15:04:05"))
	}
	return nil
}

func cmdRestore(args []string) error {
	fs, cfgPath, verbose := flagSet("restore")
	jobName := fs.String("job", "", "job name (required)")
	file := fs.String("file", "", "backup file name, see 'list' (required)")
	target := fs.String("target", "", "target database DSN (defaults to the job's dsn)")
	yes := fs.Bool("yes", false, "confirm the restore (required)")
	if err := fs.Parse(args); err != nil {
		return err
	}
	log := newLogger(*verbose)
	if *jobName == "" || *file == "" {
		return fmt.Errorf("--job and --file are required")
	}
	if !*yes {
		return fmt.Errorf("refusing to restore without --yes (this overwrites the target database)")
	}
	cfg, err := loadConfig(*cfgPath)
	if err != nil {
		return err
	}
	job, err := cfg.FindJob(*jobName)
	if err != nil {
		return err
	}
	dsn := *target
	if dsn == "" {
		dsn = job.DSN
	}
	return runner.Restore(context.Background(), cfg, job, *file, dsn, log)
}

func cmdKeygen(args []string) error {
	fs := flag.NewFlagSet("keygen", flag.ContinueOnError)
	out := fs.String("out", "", "output path for the key file (required)")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if *out == "" {
		return fmt.Errorf("--out is required")
	}
	if err := crypto.GenerateKeyFile(*out); err != nil {
		return err
	}
	fmt.Printf("wrote new AES-256 key to %s (mode 0600)\n", *out)
	fmt.Println("point your config at it: encryption: {key_file: " + *out + "}")
	return nil
}

func trunc(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n-1] + "…"
}

func humanSize(b int64) string {
	const unit = 1024
	if b < unit {
		return fmt.Sprintf("%d B", b)
	}
	div, exp := int64(unit), 0
	for n := b / unit; n >= unit; n /= unit {
		div *= unit
		exp++
	}
	return fmt.Sprintf("%.1f %ciB", float64(b)/float64(div), "KMGTPE"[exp])
}
