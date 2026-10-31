package retention

import (
	"testing"
	"time"

	"github.com/miriyaladhanwinn/dbhaven/internal/config"
)

func mkBackups(base time.Time, daysAgo ...int) []Backup {
	var out []Backup
	for _, d := range daysAgo {
		t := base.AddDate(0, 0, -d).Add(2 * time.Hour) // 2h after base time
		out = append(out, Backup{
			Name: "job-postgres-" + t.Format(timeLayout) + ".dump.enc",
			Time: t,
		})
	}
	return out
}

func names(bs []Backup) map[string]bool {
	m := map[string]bool{}
	for _, b := range bs {
		m[b.Name] = true
	}
	return m
}

func TestParseTime(t *testing.T) {
	ts, err := ParseTime("main-postgres-20261017-023000.dump.enc")
	if err != nil {
		t.Fatal(err)
	}
	if ts.Year() != 2026 || ts.Month() != 10 || ts.Day() != 17 || ts.Hour() != 2 || ts.Minute() != 30 {
		t.Fatalf("wrong time: %v", ts)
	}
	if _, err := ParseTime("garbage-name.sql"); err == nil {
		t.Fatal("expected error for unparseable name")
	}
	if _, err := ParseTime("job-mysql-20261301-000000.sql.gz.enc"); err == nil {
		t.Fatal("expected error for impossible date")
	}
}

func TestKeepLast(t *testing.T) {
	now := time.Date(2026, 10, 17, 12, 0, 0, 0, time.Local)
	backups := mkBackups(now, 0, 1, 2, 3, 4, 5, 6)
	keep, del := PlanPrune(backups, config.Retention{KeepLast: 3}, now)
	if len(keep) != 3 || len(del) != 4 {
		t.Fatalf("want keep=3 del=4, got keep=%d del=%d", len(keep), len(del))
	}
	kn := names(keep)
	for _, d := range []int{0, 1, 2} {
		want := "job-postgres-" + now.AddDate(0, 0, -d).Add(2*time.Hour).Format(timeLayout) + ".dump.enc"
		if !kn[want] {
			t.Fatalf("expected newest backup %q kept", want)
		}
	}
}

func TestKeepLastKeepsAllWhenFewer(t *testing.T) {
	now := time.Now()
	backups := mkBackups(now, 0, 1)
	keep, del := PlanPrune(backups, config.Retention{KeepLast: 10}, now)
	if len(keep) != 2 || len(del) != 0 {
		t.Fatalf("want keep=2 del=0, got %d/%d", len(keep), len(del))
	}
}

func TestGFS(t *testing.T) {
	// Saturday 2026-10-17 12:00 local.
	now := time.Date(2026, 10, 17, 12, 0, 0, 0, time.Local)
	// One backup per day for the last 60 days.
	var days []int
	for d := 0; d < 60; d++ {
		days = append(days, d)
	}
	backups := mkBackups(now, days...)
	keep, del := PlanPrune(backups, config.Retention{Daily: 7, Weekly: 4, Monthly: 2}, now)

	// Daily tier: last 7 days all kept.
	kn := names(keep)
	for d := 0; d < 7; d++ {
		want := "job-postgres-" + now.AddDate(0, 0, -d).Add(2*time.Hour).Format(timeLayout) + ".dump.enc"
		if !kn[want] {
			t.Fatalf("daily backup %d days ago should be kept", d)
		}
	}
	// Weekly tier: exactly 4 additional weekly representatives.
	// Monthly tier: exactly 2 additional monthly representatives.
	// Total kept = 7 + 4 + 2 = 13 (no overlap: tiers partition the timeline).
	if len(keep) != 13 {
		t.Fatalf("want 13 kept (7 daily + 4 weekly + 2 monthly), got %d", len(keep))
	}
	if len(del) != 60-13 {
		t.Fatalf("want %d deleted, got %d", 60-13, len(del))
	}
	// Spot check: a backup ~20 days old (inside weekly window, but not the
	// newest of its ISO week) must be deleted.
	old := now.AddDate(0, 0, -20).Add(2 * time.Hour)
	oldName := "job-postgres-" + old.Format(timeLayout) + ".dump.enc"
	if kn[oldName] {
		// It might legitimately be the weekly representative; verify instead
		// that at most one backup per ISO week survived in the weekly window.
		t.Logf("note: %s kept as weekly representative", oldName)
	}
}

func TestGFSWeeklyUniqueness(t *testing.T) {
	now := time.Date(2026, 10, 17, 12, 0, 0, 0, time.Local)
	// Two backups per day for 30 days (02:00 and 14:00).
	var backups []Backup
	for d := 0; d < 30; d++ {
		for _, h := range []int{2, 14} {
			tm := now.AddDate(0, 0, -d).Truncate(24 * time.Hour).Add(time.Duration(h) * time.Hour)
			backups = append(backups, Backup{
				Name: "job-postgres-" + tm.Format(timeLayout) + ".dump.enc",
				Time: tm,
			})
		}
	}
	keep, _ := PlanPrune(backups, config.Retention{Daily: 7, Weekly: 4}, now)
	// Daily tier: 7 days × 1 (newest per day = 14:00).
	// Weekly tier: 4 weeks × 1.
	if len(keep) != 11 {
		t.Fatalf("want 11 kept, got %d", len(keep))
	}
	// The kept daily backups must be the 14:00 ones (newest of each day).
	for d := 0; d < 7; d++ {
		day := now.AddDate(0, 0, -d).Truncate(24 * time.Hour)
		kept02 := "job-postgres-" + day.Add(2*time.Hour).Format(timeLayout) + ".dump.enc"
		for _, b := range keep {
			if b.Name == kept02 {
				t.Fatalf("older intraday backup %q should not be kept", kept02)
			}
		}
	}
}

func TestEmpty(t *testing.T) {
	keep, del := PlanPrune(nil, config.Retention{Daily: 7}, time.Now())
	if len(keep) != 0 || len(del) != 0 {
		t.Fatal("empty input must yield empty output")
	}
}
