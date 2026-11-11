// Move a few lanes so the runner changes position, then capture a frame.
export default async function run(page, ui) {
  const menu = await ui.snapshot()
  const start = menu.match(/@(e\d+) button "Start a run[^"]*"/)
  if (!start) return { error: 'no start button found', menu }
  await ui.click(start[1])
  await page.waitForTimeout(1200)

  // Drive the runner a bit so the scene is not in its initial pose.
  for (const key of ['ArrowRight', 'ArrowLeft', 'ArrowLeft']) {
    await page.keyboard.press(key)
    await page.waitForTimeout(900)
  }
  await page.waitForTimeout(600)
  return { ok: true }
}
