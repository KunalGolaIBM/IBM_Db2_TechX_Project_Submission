// Package retention implements GFS (grandfather-father-son) pruning of backups.
//
// Backup file names produced by dbhaven look like:
//
//	<job>-<dbtype>-20060102-150405.<ext>[.enc]
//
// e.g. main-postgres-20261017-023000.dump.enc
package retention

import (
	"fmt"
	"path"
	"regexp"
	"sort"
	"strings"
	"time"

	"github.com/miriyaladhanwinn/dbhaven/internal/config"
)

// Backup is one existing backup artifact.
type Backup struct {
	Name string
	Time time.Time
	Size int64
}

// Layout embedded in file names.
const timeLayout = "20060102-150405"

var nameRe = regexp.MustCompile(`^.+-(\d{8}-\d{6})\.[^.]+(\.enc)?$`)

// ParseTime extracts the backup timestamp from a dbhaven file name.
func ParseTime(name string) (time.Time, error) {
	m := nameRe.FindStringSubmatch(path.Base(name))
	if m == nil {
		return time.Time{}, fmt.Errorf("cannot parse timestamp from %q", name)
	}
	ts, err := time.ParseInLocation(timeLayout, m[1], time.Local)
	if err != nil {
		return time.Time{}, fmt.Errorf("bad timestamp in %q: %w", name, err)
	}
	return ts, nil
}

// dayStart truncates t to local midnight for calendar-day comparisons.
func dayStart(t time.Time) time.Time {
	y, m, d := t.Date()
	return time.Date(y, m, d, 0, 0, 0, 0, t.Location())
}

// PlanPrune decides which backups to keep and which to delete according to r.
// If KeepLast is set it takes precedence over the GFS tiers.
// Tier boundaries are calendar days in the local timezone.
func PlanPrune(backups []Backup, r config.Retention, now time.Time) (keep, del []Backup) {
	sorted := append([]Backup(nil), backups...)
	sort.Slice(sorted, func(i, j int) bool { return sorted[i].Time.After(sorted[j].Time) })

	if r.KeepLast > 0 {
		if len(sorted) <= r.KeepLast {
			return sorted, nil
		}
		return sorted[:r.KeepLast], sorted[r.KeepLast:]
	}

	today := dayStart(now)
	keepSet := map[string]bool{}
	mark := func(b Backup) { keepSet[b.Name] = true }

	// Daily tier: newest backup of each of the last `daily` calendar days.
	if r.Daily > 0 {
		dailyDays := map[string]bool{}
		for _, b := range sorted {
			ddays := int(today.Sub(dayStart(b.Time)).Hours() / 24)
			if ddays < 0 {
				ddays = 0 // tolerate slight clock skew
			}
			if ddays >= r.Daily {
				continue
			}
			day := b.Time.Format("2006-01-02")
			if !dailyDays[day] {
				dailyDays[day] = true
				mark(b)
			}
		}
	}

	// Weekly tier: newest backup of each ISO week in the `weekly` weeks
	// following the daily window.
	if r.Weekly > 0 {
		weeklyWeeks := map[string]bool{}
		winStart := today.AddDate(0, 0, -r.Daily-7*r.Weekly)
		winEnd := today.AddDate(0, 0, -r.Daily)
		for _, b := range sorted {
			if keepSet[b.Name] {
				continue
			}
			if b.Time.Before(winStart) || !b.Time.Before(winEnd) {
				continue
			}
			y, w := b.Time.ISOWeek()
			key := fmt.Sprintf("%d-%02d", y, w)
			if !weeklyWeeks[key] {
				weeklyWeeks[key] = true
				mark(b)
			}
			if len(weeklyWeeks) >= r.Weekly {
				break
			}
		}
	}

	// Monthly tier: newest backup of each calendar month in the `monthly`
	// months following the weekly window.
	if r.Monthly > 0 {
		monthlyMonths := map[string]bool{}
		winStart := today.AddDate(0, -r.Monthly, -r.Daily-7*r.Weekly)
		winEnd := today.AddDate(0, 0, -r.Daily-7*r.Weekly)
		for _, b := range sorted {
			if keepSet[b.Name] {
				continue
			}
			if b.Time.Before(winStart) || !b.Time.Before(winEnd) {
				continue
			}
			key := b.Time.Format("2006-01")
			if !monthlyMonths[key] {
				monthlyMonths[key] = true
				mark(b)
			}
			if len(monthlyMonths) >= r.Monthly {
				break
			}
		}
	}

	for _, b := range sorted {
		if keepSet[b.Name] {
			keep = append(keep, b)
		} else {
			del = append(del, b)
		}
	}
	return keep, del
}

// Summarize renders a human-readable prune plan.
func Summarize(keep, del []Backup) string {
	var sb strings.Builder
	fmt.Fprintf(&sb, "keeping %d, deleting %d", len(keep), len(del))
	if len(del) > 0 {
		names := make([]string, 0, len(del))
		for _, b := range del {
			names = append(names, b.Name)
		}
		fmt.Fprintf(&sb, ": %s", strings.Join(names, ", "))
	}
	return sb.String()
}
