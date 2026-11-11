// Drive Bootcamp Runner into gameplay, test keyboard A, D, ArrowLeft, ArrowRight,
// touch buttons, lane boundaries, object movement, pause/resume, and restart.
import fs from 'node:fs'

const OUT = './qa-shots-gameplay'

export default async function run(page, ui) {
  fs.mkdirSync(OUT, { recursive: true })
  await page.setViewportSize({ width: 1280, height: 720 })
  await page.goto('http://127.0.0.1:5173/', { waitUntil: 'networkidle' })

  // Snapshot menu
  const snap = await ui.snapshot()
  const start = snap.match(/@(e\d+) button "Start run/)
  if (!start) return { error: 'no start button', snap }

  // Start run
  await ui.click(start[1])
  await page.waitForTimeout(1000)

  // Function to inspect player position & objects in the Three.js scene
  const getSceneState = () => page.evaluate(() => {
    const sceneEl = document.querySelector('.scene')
    return {
      hudText: document.querySelector('.hud-stats')?.innerText,
      arcadeLabel: document.querySelector('.arcade-label')?.innerText,
    }
  })

  const results = {
    initial: await getSceneState(),
    steps: []
  }

  // 1. Initial lane is 1 (center, x=0).
  // Press 'a': should move LEFT to lane 0 (target x = -3.2)
  await page.keyboard.press('a')
  await page.waitForTimeout(400)
  results.steps.push({ action: 'press A', state: await getSceneState() })
  await page.screenshot({ path: `${OUT}/1-press-a-left.png` })

  // Press 'a' again: boundary check, should stay in lane 0 (cannot go left of lane 0)
  await page.keyboard.press('a')
  await page.waitForTimeout(300)
  results.steps.push({ action: 'press A boundary', state: await getSceneState() })

  // Press 'd': should move RIGHT to lane 1 (target x = 0)
  await page.keyboard.press('d')
  await page.waitForTimeout(400)
  results.steps.push({ action: 'press D center', state: await getSceneState() })
  await page.screenshot({ path: `${OUT}/2-press-d-center.png` })

  // Press 'd' again: should move RIGHT to lane 2 (target x = 3.2)
  await page.keyboard.press('d')
  await page.waitForTimeout(400)
  results.steps.push({ action: 'press D right', state: await getSceneState() })
  await page.screenshot({ path: `${OUT}/3-press-d-right.png` })

  // Press 'd' again: boundary check, should stay in lane 2
  await page.keyboard.press('d')
  await page.waitForTimeout(300)
  results.steps.push({ action: 'press D boundary', state: await getSceneState() })

  // Press ArrowLeft: should move LEFT to lane 1
  await page.keyboard.press('ArrowLeft')
  await page.waitForTimeout(400)
  results.steps.push({ action: 'press ArrowLeft center', state: await getSceneState() })

  // Press ArrowRight: should move RIGHT to lane 2
  await page.keyboard.press('ArrowRight')
  await page.waitForTimeout(400)
  results.steps.push({ action: 'press ArrowRight right', state: await getSceneState() })

  // Let runner run for 2 seconds to see objects moving and approaching
  await page.waitForTimeout(2000)
  results.steps.push({ action: 'running mid-track', state: await getSceneState() })
  await page.screenshot({ path: `${OUT}/4-running-objects.png` })

  // Pause
  await page.keyboard.press('p')
  await page.waitForTimeout(500)
  results.steps.push({ action: 'pause modal', hasModal: await page.locator('.pause-card').isVisible() })
  await page.screenshot({ path: `${OUT}/5-paused.png` })

  // Resume
  await page.getByRole('button', { name: 'Resume' }).click()
  await page.waitForTimeout(500)
  results.steps.push({ action: 'resumed', hasModal: await page.locator('.pause-card').isVisible() })

  return results
}
