import type { Task } from '../types/database';
import { safeMissionDuration } from './missionDuration';

export interface DerivedMission {
  title: string;
  objective: string;
  next_action: string;
  planned_minutes: number;
}

/**
 * Intelligently derives a focused mission (title, objective, next physical action, time)
 * from a user's task without lazy repetition or trivial "Complete: <title>" prepending.
 */
export function deriveMissionFromTask(task: Task | { title: string; description?: string | null; deadline?: string | null; priority?: string; estimated_minutes?: number | null }): DerivedMission {
  const rawTitle = task.title.trim();
  const desc = task.description?.trim() || '';
  const lower = rawTitle.toLowerCase();

  // Format deadline if present
  let deadlineStr = '';
  if (task.deadline) {
    try {
      const d = new Date(task.deadline);
      if (!isNaN(d.getTime())) {
        deadlineStr = `before ${d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}`;
      }
    } catch {}
  }

  let title = rawTitle;
  let objective = '';
  let nextAction = '';
  const minutes = safeMissionDuration(task.estimated_minutes ?? (task.priority === 'urgent' ? 50 : task.priority === 'high' ? 45 : 25));

  // 1. Study / Exam / Revision / Academic prep
  if (/^(prepare for|study for|revise for|exam|test|quiz)/i.test(rawTitle) || lower.includes('exam') || lower.includes('revision') || lower.includes('study')) {
    const subject = rawTitle.replace(/^(prepare for|study for|revise for|study|revise)\s*/i, '').trim();
    title = subject ? `Review & practice for ${subject}` : `Key concepts review & practice`;
    objective = desc
      ? `Cover ${desc} and solidify key concepts ${deadlineStr}`.trim()
      : `Master the core topics, identify weak spots, and work through practice questions ${deadlineStr}`.trim();
    nextAction = subject
      ? `Open the syllabus or reference material for ${subject} and complete the first 2 problem sets.`
      : `Open the reference material and complete the first 2 practice problem sets.`;
  }
  // 2. Writing / Drafting / Essay / Report / Presentation
  else if (/^(write|draft|essay|report|paper|article|blog|presentation|slides)/i.test(rawTitle) || lower.includes('report') || lower.includes('essay') || lower.includes('draft')) {
    const topic = rawTitle.replace(/^(write|draft|work on|prepare|create)\s*/i, '').trim();
    title = topic ? `Draft core section of ${topic}` : `Draft core outline & sections`;
    objective = desc
      ? `Deliver on ${desc} and get the primary draft down ${deadlineStr}`.trim()
      : `Complete the structure, outline, and opening sections to eliminate the blank-page barrier ${deadlineStr}`.trim();
    nextAction = `Open a blank document and write out the outline and opening paragraph.`;
  }
  // 3. Coding / Implementation / Development / Debugging
  else if (/^(practice|code|implement|build|develop|program|debug|fix|solve)/i.test(rawTitle) || lower.includes('problems') || lower.includes('code') || lower.includes('bug')) {
    const component = rawTitle.replace(/^(practice|code|implement|build|develop|program|debug|fix|solve)\s*/i, '').trim();
    title = component ? `Build & verify ${component}` : `Implement core logic & tests`;
    objective = desc
      ? `Implement ${desc} and verify functional correctness ${deadlineStr}`.trim()
      : `Complete the initial implementation and ensure primary test cases pass ${deadlineStr}`.trim();
    nextAction = `Open the codebase or IDE, outline the component, and write the first function.`;
  }
  // 4. Reading / Research / Exploration
  else if (/^(read|research|investigate|explore|learn)/i.test(rawTitle) || lower.includes('read') || lower.includes('research')) {
    const subject = rawTitle.replace(/^(read|research|investigate|explore|learn)\s*/i, '').trim();
    title = subject ? `Deep dive & notes on ${subject}` : `Research & key takeaways`;
    objective = desc
      ? `Synthesize ${desc} and capture actionable takeaways ${deadlineStr}`.trim()
      : `Extract key insights, document main principles, and summarize findings ${deadlineStr}`.trim();
    nextAction = `Open the primary source material or article and take concise bullet notes.`;
  }
  // 5. Consistency goals / Habits / Routines
  else if (/^(maintain|keep|daily|habit|consistent|routine)/i.test(rawTitle) || lower.includes('daily') || lower.includes('consistency')) {
    const habit = rawTitle.replace(/^(maintain consistency in|maintain|keep up with|daily)\s*/i, '').trim();
    title = habit ? `Daily focus sprint: ${habit}` : `Daily focus session`;
    objective = desc
      ? `Dedicate focused time to ${desc} and maintain steady momentum.`
      : `Complete today's dedicated session to keep your consistency streak uninterrupted.`;
    nextAction = `Clear notifications, set a 25-minute timer, and begin the routine.`;
  }
  // 6. Finishing / Completing / Finalizing
  else if (/^(finish|complete|submit|wrap up|finalize)/i.test(rawTitle)) {
    const work = rawTitle.replace(/^(finish|complete|submit|wrap up|finalize)\s*/i, '').trim();
    title = work ? `Final sprint on ${work}` : `Final completion sprint`;
    objective = desc
      ? `Address ${desc} and finalize all remaining deliverables ${deadlineStr}`.trim()
      : `Resolve the final checklist items and prepare ${work || 'this task'} for completion ${deadlineStr}`.trim();
    nextAction = work
      ? `Check the remaining requirements for ${work} and finish the first outstanding item.`
      : `Check the remaining requirements and finish the first outstanding item.`;
  }
  // 7. General Fallback
  else {
    title = `Sprint: ${rawTitle}`;
    objective = desc
      ? `Focus on ${desc} to make clear, verifiable headway ${deadlineStr}`.trim()
      : `Make tangible, verifiable progress on ${rawTitle} and clear the primary hurdle ${deadlineStr}`.trim();
    nextAction = `Open the required tools or workspace for ${rawTitle} and execute the first immediate step.`;
  }

  return {
    title,
    objective,
    next_action: nextAction,
    planned_minutes: minutes,
  };
}
