// Enter the game and crop-zoom on the player character to inspect it.
export default async function run(page, ui) {
  const menu = await ui.snapshot()
  const start = menu.match(/@(e\d+) button "Start a run[^"]*"/)
  if (!start) return { error: 'no start button found', menu }
  await ui.click(start[1])
  await page.waitForTimeout(2500)
  // Hide the DOM HUD so only the 3D scene is visible.
  await page.addStyleTag({ content: '.hud,.game-hud,.question-panel,.game-shell>header,.touch-controls,.top-hud{display:none!important}' })
  await page.waitForTimeout(400)
  return { ok: true }
}
