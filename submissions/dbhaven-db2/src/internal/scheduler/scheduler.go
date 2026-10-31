// Package scheduler runs backup jobs on their configured cron schedules.
package scheduler

import (
	"context"
	"fmt"
	"log/slog"

	"github.com/robfig/cron/v3"
	"github.com/miriyaladhanwinn/dbhaven/internal/config"
	"github.com/miriyaladhanwinn/dbhaven/internal/runner"
)

// Serve registers every job that has a schedule and blocks until ctx ends.
func Serve(ctx context.Context, cfg *config.Config, log *slog.Logger) error {
	c := cron.New()
	scheduled := 0
	for i := range cfg.Jobs {
		job := &cfg.Jobs[i]
		if job.Schedule == "" {
			log.Info("job has no schedule, skipping in daemon mode", "job", job.Name)
			continue
		}
		j := job // capture for closure
		if _, err := c.AddFunc(j.Schedule, func() {
			log.Info("scheduled run starting", "job", j.Name)
			if _, err := runner.RunJob(ctx, cfg, j, log); err != nil {
				log.Error("scheduled run failed", "job", j.Name, "err", err)
			}
		}); err != nil {
			return fmt.Errorf("job %q: bad schedule: %w", j.Name, err)
		}
		scheduled++
		log.Info("scheduled job", "job", job.Name, "cron", job.Schedule)
	}
	if scheduled == 0 {
		return fmt.Errorf("no jobs have a schedule; nothing to do")
	}
	c.Start()
	defer c.Stop()
	log.Info("scheduler running", "jobs", scheduled)
	<-ctx.Done()
	log.Info("scheduler stopping")
	return nil
}
